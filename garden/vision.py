import json
import re
import time
from pathlib import Path
import cv2
import numpy as np
from .core import Observation
from .cn_login import classify, RECOVERY, account_name, open_account_list
from .identity import read_uid
from .weekly import classify_guide


class VisionDriver:
    """Profile-driven observations. No source-project assets or coordinates."""
    def __init__(self, window, profile_path, control, evidence_dir):
        self.window, self.control = window, control
        self.base = Path(profile_path).parent
        self.profile = json.loads(Path(profile_path).read_text(encoding='utf-8'))
        self.profile.setdefault('templates',{}).setdefault('garden_new_stage',{
            'file':str(Path(__file__).resolve().parent/'assets'/'stage-advance.png'),
            'region':[.48,.58,.76,.74], 'threshold':.94, 'reference_size':[2560,1440]})
        self.profile['templates'].setdefault('garden_shop_close',{
            'file':str(Path(__file__).resolve().parent/'assets'/'shop-close.png'),
            'region':[.77,.025,.87,.10], 'threshold':.94, 'reference_size':[2560,1440]})
        self.profile['templates'].setdefault('guide_close',{
            'file':str(Path(__file__).resolve().parent/'assets'/'guide-close.png'),
            'region':[.91,.01,.98,.11], 'threshold':.94, 'reference_size':[2560,1440]})
        self.evidence_dir = Path(evidence_dir)
        self.templates = {}
        self.frame = None
        self.ocr = None

    def report(self, message):
        callback = getattr(self,'progress_callback',None)
        if callback:
            callback(message)

    def validate(self):
        required = {'login','home','weekly','result','playing'}
        if not self.profile.get('validated'):
            raise RuntimeError('配置已加载；完整周常流程尚未验证。请在“连接与校准”中查看后台输入诊断状态')
        if not required.issubset(self.profile.get('states', {})):
            raise RuntimeError('识别配置缺少必要页面')
        for state in self.profile['states'].values():
            if not state.get('anchors'):
                raise RuntimeError('每个页面必须有独立识别锚点')

    def image(self):
        self.control.check()
        self.frame = self.window.capture()
        return self.frame

    def texts(self, region=None):
        if self.ocr is None:
            from rapidocr import RapidOCR
            self.ocr = RapidOCR(params={'EngineConfig.onnxruntime.intra_op_num_threads':2,
                                       'EngineConfig.onnxruntime.inter_op_num_threads':2})
        image = self.frame or self.image()
        w,h = image.size
        x,y,right,bottom = region or [0,0,1,1]
        result = self.ocr(np.array(image.crop((int(x*w),int(y*h),int(right*w),int(bottom*h)))))
        if result.boxes is None or result.txts is None or result.scores is None:
            return []
        return [(text, float(score), ((float(box[0][0])+float(box[2][0]))/2+x*w,
                                    (float(box[0][1])+float(box[2][1]))/2+y*h))
                for box,text,score in zip(result.boxes, result.txts, result.scores)]

    def locate(self, name):
        spec = self.profile['templates'][name]
        if name not in self.templates:
            self.templates[name] = cv2.imdecode(np.fromfile(str(self.base/spec['file']),dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
        template = self.templates[name]
        image = np.array(self.frame.convert('L'))
        x,y,r,b = spec.get('region',[0,0,1,1])
        h,w = image.shape
        image = image[int(y*h):int(b*h),int(x*w):int(r*w)]
        reference = spec.get('reference_size',self.profile.get('reference_size',[1920,1080]))
        template = cv2.resize(template,None,fx=w/reference[0],fy=h/reference[1])
        if image.shape[0] < template.shape[0] or image.shape[1] < template.shape[1]:
            return None
        _,score,_,pos = cv2.minMaxLoc(cv2.matchTemplate(image,template,cv2.TM_CCOEFF_NORMED))
        if score < spec.get('threshold', .92):
            return None
        return pos[0]+x*w+template.shape[1]/2, pos[1]+y*h+template.shape[0]/2

    def observe(self):
        self.image()
        if self.profile.get('cn_login'):
            rows = self.texts()
            self.login_view = classify(rows, *self.frame.size)
            if self.login_view.state != 'unknown':
                return Observation(self.login_view.state,{})
            weekly = classify_guide(rows,*self.frame.size)
            if weekly.page == 'weekly':
                self.weekly_view = weekly
                return Observation('weekly',{'current':weekly.current,'target':6000})
        matches = [name for name,spec in self.profile['states'].items()
                   if all(self.locate(anchor) for anchor in spec['anchors'])]
        if len(matches) != 1:
            return Observation('unknown', {})
        state = matches[0]
        values = {}
        if state == 'weekly':
            text = ' '.join(t[0] for t in self.texts(self.profile['progress_region']) if t[1] >= .9)
            match = re.search(r'(\d+)\s*[/／]\s*(\d+)', text.replace(',',''))
            if match:
                values.update(current=int(match[1]), target=int(match[2]))
            values['all_claimed'] = bool(self.locate('all_claimed'))
        return Observation(state,values)

    def act(self, action):
        self.control.check()
        if action in ('claim','enter') and self.profile.get('cn_login'):
            if self.observe().state != 'weekly':
                raise RuntimeError('当前不是周度游历页面，停止操作')
            view = self.weekly_view
            if view.current is None:
                raise RuntimeError('未读到实际游历值，停止操作')
            if action == 'claim' and view.current < 6000:
                raise RuntimeError('未达到周目标，不能按满分流程结束')
            x,y = view.targets[action]
            w,h = self.frame.size
            repeats = 2 if action == 'claim' else 1
            for _ in range(repeats):
                self.control.check()
                self.window.click(x*w,y*h)
                self.control.wait(1.5)
            return
        if self.profile.get('cn_login'):
            self.observe()
            point = self.login_view.targets.get(action)
            if point:
                w,h = self.frame.size
                self.window.click(point[0]*w,point[1]*h)
                self.control.wait(1)
                return
        spec = self.profile['actions'].get(action)
        if not spec:
            raise RuntimeError(f'缺少动作配置：{action}')
        obs = self.observe()
        if obs.state not in spec['from']:
            raise RuntimeError(f'页面 {obs.state} 不允许动作 {action}')
        if 'template' in spec:
            point = self.locate(spec['template'])
            if not point:
                raise RuntimeError(f'动作目标无法确认：{action}')
            self.window.click(*point)
        else:
            self.window.key(int(spec['key']))
        self.control.wait(spec.get('settle',1))

    def step(self, obs):
        if obs.state == 'unknown':
            self.control.wait(1)
            return
        action = self.profile['states'][obs.state].get('action')
        if not action:
            raise RuntimeError(f'当前页面需要处理：{obs.state}')
        self.act(action)

    def read_accounts(self):
        if self.profile.get('cn_login'):
            return self.read_visible_cn_accounts()
        self.validate()
        if not self.recover_login():
            raise RuntimeError('请先回到游戏登录页')
        self.act('account_list')
        pattern = self.profile.get('account_pattern',r'(?:\*{2,}|@)')
        names = []
        previous = None
        for _ in range(40):
            rows = self.account_rows()
            page = [text for text,score,_ in rows if score >= .95 and re.search(pattern,text)]
            if len(page) != len(set(page)):
                raise RuntimeError('账号列表存在相同脱敏名称，需要校准身份定位')
            for name in page:
                if name not in names:
                    names.append(name)
            if self.locate('account_list_end'):
                self.act('close_account_list')
                return names
            if page == previous:
                raise RuntimeError('列表翻页未生效，未确认完整账号列表')
            previous = page
            self.act('account_scroll')
        raise RuntimeError('账号列表超过遍历上限')

    def read_visible_cn_accounts(self):
        # Mainland SDK exposes a native ComboBox even when its dropdown is
        # absent from WGC. Read it directly before attempting visual expansion.
        for _ in range(6):
            native = self.window.saved_accounts()
            if native is not None:
                self.control.wait(.2)
                if native != self.window.saved_accounts():
                    raise RuntimeError('账号控件连续读取结果不一致')
                self.account_list_complete = True
                return native
            obs = self.observe()
            if obs.state in ('login','account_list'):
                break
            action = RECOVERY.get(obs.state)
            if action is None:
                raise RuntimeError(f'无法从 {obs.state} 找到账号控件')
            self.act(action)
            self.control.wait(.5)
        open_account_list(self)
        previous = None
        for _ in range(5):
            rows = self.account_rows()
            names = [row[0] for row in rows]
            if names and names == previous:
                self.evidence_dir.mkdir(parents=True,exist_ok=True)
                self.frame.save(self.evidence_dir/'account-list-latest.png')
                self.account_list_complete = False
                return names
            previous = names
            self.control.wait(.5)
        raise RuntimeError('账号列表识别不稳定，未更新队列')

    def account_rows(self):
        if self.profile.get('cn_login'):
            if self.observe().state != 'account_list':
                raise RuntimeError('账号下拉列表未展开，停止读取或选择')
            w,h = self.frame.size
            return [(name,1.0,(x*w,y*h)) for name,(x,y) in self.login_view.accounts]
        self.image()
        return self.texts(self.profile['account_region'])

    def login(self, account):
        self.report('正在定位登录窗口')
        if not self.recover_login():
            raise RuntimeError('无法回到登录页')
        if self.profile.get('cn_login') and self.window.account_control() is not None:
            self.report('正在选择账号并核对登录栏')
            self.window.select_saved_account(account)
            if self.window.selected_saved_account() != account:
                raise RuntimeError('原生账号控件读回值不匹配，未点击登录')
            self.control.wait(4)
            self.submit_account_login(account)
            return self.wait_identity()
        self.act('account_list')
        self.act('account_top')
        rows = []
        for _ in range(40):
            rows = [row for row in self.account_rows() if row[0] == account and row[1] >= .95]
            if rows or self.locate('account_list_end'):
                break
            self.act('account_scroll')
        if len(rows) != 1:
            raise RuntimeError('无法唯一定位目标账号')
        self.window.click(*rows[0][2])
        self.control.wait(1)
        if self.profile.get('cn_login'):
            if self.observe().state != 'login':
                raise RuntimeError('选择后没有回到登录弹窗')
            selected = [self.login_view.selected]
        else:
            self.image()
            selected = [t[0] for t in self.texts(self.profile['selected_account_region']) if t[1] >= .95]
        if account not in selected:
            raise RuntimeError('选择后的账号校验失败')
        self.act('login')
        return self.wait_identity()

    def submit_account_login(self, account):
        for attempt in range(3):
            self.observe()
            if self.window.selected_saved_account() != account:
                raise RuntimeError('登录前账号发生变化，停止登录')
            point = self.login_view.targets.get('login')
            if not point:
                raise RuntimeError('账号已选中，但未定位到登录按钮')
            self.report(f'正在点击登录并确认页面变化（{attempt+1}/3）')
            w,h = self.frame.size
            if attempt == 0:
                self.window.click(point[0]*w,point[1]*h)
            else:
                self.window.click_login_dialog(point[0]*w,point[1]*h)
            for _ in range(6):
                self.control.wait(1)
                state = self.observe().state
                if hasattr(self,'evidence_dir'):
                    self.evidence_dir.mkdir(parents=True,exist_ok=True)
                    with (self.evidence_dir/'account-switch.jsonl').open('a',encoding='utf-8') as log:
                        log.write(json.dumps({'time':time.time(),'requested':account,
                            'state':state,'attempt':attempt+1,
                            'input':getattr(self.window,'last_input',None)},ensure_ascii=False)+'\n')
                if state == 'connected_title' or (state not in ('login','account_list')
                        and self.window.account_control() is None):
                    return
        raise RuntimeError('登录点击三次后页面仍未离开登录框，停止等待')

    def login_next(self, first=False):
        if first and self.observe().state == 'home':
            return self.wait_identity()
        if not self.recover_login():
            raise RuntimeError('无法回到登录页')
        if not first:
            self.act('account_list')
            # Profile must select the successor of the selected row, with explicit wrap.
            self.act('account_next')
            self.act('close_account_list')
        self.act('login')
        return self.wait_identity()

    def wait_identity(self):
        previous_uid = None
        stable = 0
        connected = False
        deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            state = self.observe().state
            if state == 'connected_title' and not connected:
                self.report('登录已通过，正在点击连接进入游戏')
                stable = 0
                self.act('connect')
                connected = True
            elif state not in ('login','account_list','logout_confirm','signed_out','connected_title'):
                uid = read_uid(self.texts([.65,.85,1,1]),*self.frame.size)
                stable = stable+1 if uid and uid == previous_uid else (1 if uid else 0)
                previous_uid = uid
                self.report(f'正在核验角色标识（UID / 特征码）：{stable}/3')
                if stable >= 3:
                    return uid
            else:
                self.report(f'等待进入游戏，当前页面：{state}')
                stable = 0
                previous_uid = None
            self.control.wait(1)
        self.evidence()
        raise RuntimeError('180 秒内未能连续确认角色标识（UID / 特征码），已保存截图')

    def collect_weekly_entry(self):
        self.evidence_dir.mkdir(parents=True,exist_ok=True)
        opened = False
        pending = None
        pending_at = 0
        deadline = time.monotonic()+45
        previous = None
        stable = 0
        while time.monotonic() < deadline:
            self.control.check()
            self.image()
            rows = self.texts()
            view = classify_guide(rows,*self.frame.size)
            labels = [text for text,score,_ in rows if score >= .9]
            self.frame.save(self.evidence_dir/'guide-after-login.png')
            (self.evidence_dir/'guide-text.json').write_text(json.dumps(labels,ensure_ascii=False,indent=2),encoding='utf-8')
            signature = (view.page,view.current,view.target,view.rewards)
            stable = stable+1 if signature == previous else 1
            previous = signature
            self.report(f'周常入口：{view.page}；{view.status}')
            if view.page == 'weekly' and stable >= 2:
                self.weekly_view = view
                summary = {'page':view.page,'current':view.current,'target':view.target,
                           'rewards':view.rewards,'status':view.status}
                (self.evidence_dir/'weekly-status.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
                self.report(f'周度游历已打开：{view.status}（{view.current}/{view.target}）')
                return self.evidence_dir/'guide-after-login.png'
            if pending:
                if view.page != pending and view.page != 'unknown':
                    pending = None
                elif time.monotonic()-pending_at > 10:
                    raise RuntimeError(f'从 {pending} 导航后未确认页面变化，已保存截图')
            if not pending and stable >= 2:
                action = {'materials':'activity_category','activity':'weekly_tab'}.get(view.page)
                if action and action in view.targets:
                    x,y = view.targets[action]
                    self.window.click(x*self.frame.width,y*self.frame.height)
                    pending,pending_at = view.page,time.monotonic()
                elif view.page == 'unknown' and not opened:
                    # UID/feature-code required before attempting F2 from an unknown UI.
                    uid = read_uid(self.texts([.65,.85,1,1]),*self.frame.size)
                    if uid:
                        self.report('正在按 F2 打开指南')
                        self.window.key(0x71)
                        opened = True
                        pending,pending_at = 'unknown',time.monotonic()
            self.control.wait(.6)
        raise RuntimeError('未能导航到周度游历，已保存当前页面；不会重复按 F2 开关指南')

    def recover_login(self):
        for _ in range(8):
            if self.profile.get('cn_login') and self.window.account_control() is not None:
                return True
            obs = self.observe()
            if obs.state == 'login':
                return True
            action = self.profile['states'].get(obs.state,{}).get('recover')
            if self.profile.get('cn_login'):
                action = RECOVERY.get(obs.state, action)
            if not action:
                return False
            self.act(action)
        return False

    def probe_garden_entry(self):
        """Enter once and record stable destination frames for local calibration."""
        self.collect_weekly_entry()
        if self.weekly_view.current is None:
            raise RuntimeError('游历值未确认，不能进入乐园')
        if self.weekly_view.current >= 6000:
            self.act('claim')
            self.evidence()
            return '本周积分已满，已执行两次领取点击'
        folder = self.evidence_dir / ('garden-entry-' + str(time.time_ns()))
        folder.mkdir(parents=True)
        self.frame.save(folder/'before.png')
        self.report('正在进入幻梦游园')
        self.act('enter')
        previous = None
        stable = 0
        deadline = time.monotonic()+45
        sample = 0
        while time.monotonic() < deadline:
            self.control.wait(1)
            self.image()
            rows = self.texts()
            view = classify_guide(rows,*self.frame.size)
            # Preserve positions and scores for independent button recognition.
            sample += 1
            self.frame.save(folder/'latest.png')
            (folder/'latest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
            labels = tuple(sorted(text for text,score,_ in rows if score >= .94))
            signature = labels
            stable = stable+1 if signature == previous else 1
            previous = signature
            self.report(f'等待乐园页面稳定：{stable}/3；采样 {sample}')
            # A loading screen, empty frame or lingering weekly page is not success.
            garden_title = any('幻梦游园' in text for text in labels)
            start_button = any(text.replace(' ','') in ('开始游戏','开始挑战','继续挑战') for text in labels)
            if view.page == 'unknown' and garden_title and start_button and stable >= 3:
                return f'已进入乐园准备页，局内样本已保存：{folder}'
        raise RuntimeError(f'未确认乐园准备页，已保存页面与识别结果：{folder}；不会重复点击入口')

    def evidence(self):
        try:
            self.evidence_dir.mkdir(parents=True,exist_ok=True)
            self.window.capture().save(self.evidence_dir/f'{time.time_ns()}.png')
        except Exception:
            pass

    def run_garden(self):
        """Bounded current-character run, recording every decision for calibration."""
        from .play import GardenPolicy, reward_candidates, garden_page, encounter_confirmation_ready
        from copy import deepcopy
        policy = GardenPolicy()
        folder = self.evidence_dir / ('garden-run-' + str(time.time_ns()))
        folder.mkdir(parents=True)
        deadline = time.monotonic()+1800
        last_change = time.monotonic()
        last_action = None
        last_labels = None
        sequence = 0
        weekly_signature = None
        weekly_stable = 0
        entered_at = None
        unknown_since = None
        candidate_key = None
        candidate_at = 0
        last_action_at = 0
        started = False
        self.report('开始当前角色乐园流程；按停止可随时中断')
        while time.monotonic() < deadline:
            self.image()
            rows = self.texts()
            labels = tuple(sorted(text for text,score,_ in rows if score >= .94))
            if labels != last_labels:
                last_labels = labels
                last_change = time.monotonic()
                sequence += 1
                self.frame.save(folder/f'{sequence:04}.png')
                (folder/f'{sequence:04}.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
            weekly = classify_guide(rows,*self.frame.size)
            page = garden_page(rows,*self.frame.size)
            if not started:
                if weekly.page != 'weekly' and page == 'unknown':
                    raise RuntimeError('请从周度游历、乐园准备页、棋盘、商店、奖励选择或结算页继续')
                started = True
            if weekly.page == 'weekly':
                if entered_at is not None:
                    if time.monotonic()-entered_at > 15:
                        raise RuntimeError('点击乐园入口后未离开周度游历，停止重试')
                    self.control.wait(1)
                    continue
                signature = weekly.current
                weekly_stable = weekly_stable+1 if signature == weekly_signature else 1
                weekly_signature = signature
                if weekly.current is None:
                    raise RuntimeError('返回周度游历后未读到进度')
                if weekly_stable < 2:
                    self.control.wait(.7)
                    continue
                if weekly.current >= 6000:
                    self.act('claim')
                    self.evidence()
                    self.return_to_login()
                    return '游历值已满，已执行两次领取点击，并返回账号登录页'
                policy = GardenPolicy()
                self.report(f'当前 {weekly.current}/6000，进入乐园继续')
                self.act('enter')
                entered_at = time.monotonic()
                last_action = None
                weekly_stable = 0
                self.control.wait(2)
                continue
            weekly_stable = 0
            if any('幻梦游园' in text for text in labels):
                entered_at = None
            features = {}
            for name in ('new_stage','next_day','confirm','get_skip','get_confirm_gray',
                         'not_interested_confirm','shop_buy','shop_close','tip_close',
                         'unpause','continue_game','back','restart'):
                key = 'garden_'+name
                if key in self.profile.get('templates',{}):
                    point = self.locate(key)
                    if point:
                        features[name] = (point[0]/self.frame.width,point[1]/self.frame.height)
            # Do not advance the policy until a stable decision is actually sent.
            pending_policy = deepcopy(policy)
            decision = pending_policy.decide(rows,*self.frame.size,reward_candidates(self.frame),features,
                                             encounter_confirmation_ready(self.frame,rows) if page == 'encounter' else False)
            if decision.name == 'unknown':
                candidate_key = None
                if unknown_since is None:
                    unknown_since = time.monotonic()
                self.report('等待局内页面或动画；识别样本已自动保存')
                if time.monotonic()-unknown_since > 25:
                    raise RuntimeError(f'局内页面未识别，已停止并保存样本：{folder}')
                self.control.wait(1)
                continue
            unknown_since = None
            context = tuple(t for t in labels if t.startswith(('阶段','第','剩余')))
            point_key = tuple(round(v,2) for v in decision.point) if decision.point else None
            signature = (decision.name,point_key,context)
            if signature == last_action:
                if time.monotonic()-last_action_at > 15:
                    raise RuntimeError(f'{decision.name} 后页面没有变化，已保存样本：{folder}')
                self.control.wait(1)
                continue
            if signature != candidate_key:
                candidate_key,candidate_at = signature,time.monotonic()
                self.control.wait(.7)
                continue
            # Cards animate even while their skip/confirm buttons are visible.
            if time.monotonic()-candidate_at < (2 if page == 'reward' else .7):
                self.control.wait(.5)
                continue
            self.report(decision.name)
            with (folder/'actions.jsonl').open('a',encoding='utf-8') as log:
                log.write(json.dumps({'sample':sequence,'action':decision.name,'point':decision.point},ensure_ascii=False)+'\n')
            if decision.name == '退出乐园准备页':
                self.window.key(0x1B)
                self.control.wait(2)
                self.collect_weekly_entry()
            else:
                x,y = decision.point
                self.window.click(x*self.frame.width,y*self.frame.height)
            policy = pending_policy
            last_action = signature
            last_action_at = time.monotonic()
            candidate_key = None
            self.control.wait(1.5)
        raise RuntimeError(f'当前角色运行超过 30 分钟，样本保存在：{folder}')

    def return_to_login(self):
        from .return_login import menu_visible, return_confirmation
        from .play import garden_page
        deadline = time.monotonic()+90
        pending = None
        pending_at = 0
        guide_closed = False
        guide_fallback_used = False
        self.evidence_dir.mkdir(parents=True,exist_ok=True)
        while time.monotonic()<deadline:
            self.image()
            rows=self.texts()
            self.frame.save(self.evidence_dir/'return-login-latest.png')
            (self.evidence_dir/'return-login-latest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
            login=classify(rows,*self.frame.size)
            if login.state == 'login' or self.window.account_control() is not None:
                self.report('已返回账号登录页')
                return
            guide=classify_guide(rows,*self.frame.size)
            page=garden_page(rows,*self.frame.size)
            confirm=return_confirmation(rows,*self.frame.size)
            state = login.state if login.state!='unknown' else (
                'return_confirm' if confirm else 'guide' if guide.page!='unknown' else
                'preparation' if page=='entrance' else 'menu' if menu_visible(rows) else 'world_or_loading')
            if pending == state:
                if state == 'guide' and not guide_fallback_used and time.monotonic()-pending_at>=3:
                    # Esc may have dismissed a reward overlay instead of the guide.
                    # Re-observe the guide, then locate its actual close icon once.
                    point = self.locate('guide_close') if 'guide_close' in getattr(self,'profile',{}).get('templates',{}) else None
                    if point:
                        self.report('指南仍打开，改点右上角关闭按钮')
                        self.window.click(*point)
                        guide_fallback_used=True
                        pending_at=time.monotonic()
                        self.control.wait(2)
                        continue
                if time.monotonic()-pending_at>20:
                    raise RuntimeError(f'返回登录：{state} 操作后页面未变化，已保存截图')
                self.control.wait(1)
                continue
            action=None
            if state in RECOVERY:
                action=('click',login.targets[RECOVERY[state]])
            elif state=='return_confirm':
                action=('click',confirm)
            elif state in ('guide','preparation'):
                action=('key',0x1B)
                guide_closed = state=='guide'
            elif state=='menu':
                # Same menu exit entry as the reference; only after menu anchors.
                action=('click',(.04,.96))
            elif guide_closed and read_uid(rows,*self.frame.size):
                action=('key',0x1B)
                guide_closed=False
            if action:
                self.report(f'返回登录：{state}')
                if action[0]=='key':
                    self.window.key(action[1])
                else:
                    x,y=action[1]
                    self.window.click(x*self.frame.width,y*self.frame.height)
                pending,pending_at=state,time.monotonic()
                with (self.evidence_dir/'return-login-actions.jsonl').open('a',encoding='utf-8') as log:
                    log.write(json.dumps({'state':state,'action':action,'at':time.time()},ensure_ascii=False)+'\n')
                self.control.wait(2)
            else:
                self.report('等待返回登录流程的下一页面')
                self.control.wait(1)
        raise RuntimeError('90 秒内未返回账号登录页，已保存 return-login-latest 截图与识别记录')
