"""Original OCR-driven Garden policy; decisions are separate from window input."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    name: str
    point: tuple | None = None


def is_garden_board(rows, width, height):
    """Require independent board anchors; do not rely on a generic next button."""
    labels = [re.sub(r'\s+', '', text) for text,score,(x,y) in rows
              if score >= .94 and 0 < x/width < .3 and 0 < y/height < .3]
    return ('本周游园' in labels and '乐园详情' in labels
            and any(re.fullmatch(r'阶段[:：]\d+/\d+', text) for text in labels))


def garden_page(rows, width, height):
    words = [re.sub(r'\s+', '', text) for text,score,_ in rows if score >= .94]
    if any(text == '奇缘异遇' and score >= .94 and .4<x/width<.85 and .1<y/height<.3
           for text,score,(x,y) in rows):
        return 'encounter'
    if any(re.sub(r'\s+','',text) == '乐园商店' and score >= .94
           and .1 < x/width < .4 and y/height < .15 for text,score,(x,y) in rows):
        return 'shop'
    if any(re.fullmatch(r'第\d+阶段收益结算', text) for text in words) and '本阶段乐园收益目标' in words:
        return 'stage_result'
    if '返回主页' in words and any(t in words for t in ('重新挑战','重新开始','再来一次','无尽挑战')):
        return 'result'
    if '跳过' in words and '确认' in words and '刷新' in words:
        return 'reward'
    if any('幻梦游园' in text for text in words) and '开始游戏' in words:
        return 'entrance'
    if is_garden_board(rows,width,height):
        return 'board'
    return 'unknown'


def choose_reward(candidates):
    """Candidates are (rarity, normalized point); keep spatial order on ties."""
    rank = {'gold': 0, 'purple': 1}
    eligible = [(rank[kind], point) for kind, point in candidates if kind in rank]
    return min(eligible, key=lambda item: (item[0], item[1][0]))[1] if eligible else (.5, .2)


class GardenPolicy:
    def __init__(self):
        self.pending = None
        self.blessed = False
        self.returning = False

    def decide(self, rows, width, height, rewards=(), features=None, confirmation_ready=False):
        features = features or {}
        words = [(re.sub(r'\s+', '', text), (x/width, y/height))
                 for text, score, (x,y) in rows if score >= .94]
        def exact(*labels):
            return [p for text,p in words if text in labels]
        def single(*labels):
            points = exact(*labels)
            return points[0] if len(points) == 1 else None
        start = single('开始游戏')
        title = any('幻梦游园' in text and p[1] < .2 for text,p in words)
        confirm = single('确认', '确定')
        confirm = confirm or features.get('confirm') or features.get('get_confirm_gray')
        back = single('返回主页')
        restart = single('重新挑战', '重新开始', '再来一次', '无尽挑战')
        back = back or features.get('back')
        restart = restart or features.get('restart')
        if garden_page(rows,width,height) == 'encounter':
            # This modal's grey confirm is visible before any option is selected.
            # Never fall through to the generic confirm-button handler.
            if self.pending == 'encounter_confirm':
                if confirm and confirmation_ready:
                    self.pending = 'encounter_submitted'
                    return Decision('确认奇缘选项',confirm)
                return Decision('unknown')
            if self.pending == 'encounter_submitted':
                return Decision('unknown')
            declines = [p for text,p in words
                        if re.fullmatch(r'(?:你)?(?:对此)?不感兴趣[。.!！]?',text)
                        and .35<p[0]<.85 and .25<p[1]<.59]
            if declines:
                self.pending = 'encounter_confirm'
                return Decision('选择最下面的不感兴趣',max(declines,key=lambda p:p[1]))
            return Decision('unknown')
        if self.pending in ('encounter_confirm','encounter_submitted'):
            self.pending = None
        if garden_page(rows,width,height) == 'shop':
            closes = [p for text,p in words if text in ('关闭','关闭商店','离开商店')
                      and .72<p[0]<.9 and p[1]<.15]
            close = closes[0] if len(closes)==1 else features.get('shop_close')
            unavailable = any(text in ('已售罄','售罄','已售完','余额不足','货币不足')
                              for text,_ in words)
            buys = [p for text,p in words if text == '购买' and .65<p[0]<.88 and .55<p[1]<.78]
            buy = buys[0] if len(buys)==1 else features.get('shop_buy')
            if buy and not unavailable:
                return Decision('商店购买',buy)
            if close:
                self.pending = None
                return Decision('离开商店',close)
            return Decision('unknown')
        # Intermediate success, failed stage and final stage have different buttons.
        if garden_page(rows,width,height) == 'stage_result':
            terminal = any('目标未完成' in text for text,_ in words) or any(
                re.fullmatch(r'第7阶段收益结算',text) for text,_ in words)
            if terminal and confirm:
                self.blessed = False
                self.pending = None
                self.returning = True
                return Decision('确认阶段结束',confirm)
            point = single('进入新阶段','进入下一阶段','下一阶段') or features.get('new_stage')
            return Decision('进入新阶段',point) if point else Decision('unknown')
        if back and restart:
            # Return is navigation only. Check the explicit weekly counter at home.
            self.blessed = False
            self.pending = None
            self.returning = True
            return Decision('返回并复查周进度', back)
        if title and start:
            counters = [re.fullmatch(r'(\d{1,5})[/／]6000',text) for text,(x,y) in words
                        if .03<x<.25 and .15<y<.25]
            counters = [int(match[1]) for match in counters if match]
            weekly_label = any(text == '本周游历值' and .02<x<.25 and .1<y<.18
                               for text,(x,y) in words)
            capped = weekly_label and any(text == '已达到上限' and .03<x<.25 and .18<y<.25
                                           for text,(x,y) in words)
            # Applies on fresh resume as well as after returning from a result.
            # Never let a saved policy flag decide whether a full week starts again.
            if capped and counters and any(value < 6000 for value in counters):
                return Decision('unknown')
            if capped or (len(counters)==1 and counters[0]>=6000):
                return Decision('退出乐园准备页')
            if self.returning:
                if len(counters) != 1:
                    return Decision('unknown')
                self.returning = False
                self.blessed = False
            if self.blessed:
                return Decision('开始游戏', start)
            blessing = [p for text,p in words if text.startswith('祝福') and .3<p[0]<.6 and p[1]>.65]
            if len(blessing) == 1:
                self.pending = 'blessing'
                return Decision('打开祝福选择', blessing[0])
        if self.pending == 'blessing' and confirm and any('祝福' in text for text,_ in words):
            self.pending = 'blessing_confirm'
            # First option in the reference's three-option blessing layout.
            return Decision('选择第一个祝福', (.365,.617))
        if self.pending == 'blessing_confirm' and confirm:
            self.pending = None
            self.blessed = True
            return Decision('确认祝福', confirm)
        if self.pending in ('reward_confirm', 'decline_confirm') and confirm:
            self.pending = None
            return Decision('确认选择', confirm)
        if (single('跳过') or features.get('get_skip')) and (confirm or features.get('get_confirm_gray')):
            if confirm is None:
                confirm = features.get('get_confirm_gray')
            self.pending = 'reward_confirm'
            return Decision('选择奖励（金色优先）', choose_reward(rewards))
        declines = exact('不感兴趣')
        if declines:
            self.pending = 'decline_confirm'
            return Decision('选择最下面的不感兴趣', max(declines, key=lambda p:p[1]))
        for labels, name in [
            (('下一天','进入下一天'), '下一天'), (('下一阶段','进入下一阶段','进入新阶段'), '下一阶段'),
            (('继续游戏','继续挑战'), '继续游戏'), (('恢复游戏',), '恢复游戏'),
            (('购买',), '商店购买'), (('离开商店','关闭商店'), '离开商店'),
            (('知道了','我知道了'), '关闭提示'), (('确认','确定'), '确认')]:
            point = single(*labels)
            if point:
                return Decision(name, point)
        # Optional templates must be calibrated from this installation's captures.
        for feature,name in [('not_interested_confirm','确认选择'),('tip_close','关闭提示'),
                             ('unpause','恢复游戏'),('continue_game','继续游戏'),
                             ('shop_buy','商店购买'),('shop_close','离开商店'),
                             ('new_stage','进入新阶段'),('next_day','下一天')]:
            if feature in features:
                return Decision(name,features[feature])
        return Decision('unknown')


def reward_candidates(image):
    """Read rarity from card headers, not gold text in item descriptions."""
    import cv2
    import numpy as np
    hsv = cv2.cvtColor(np.array(image.convert('RGB')), cv2.COLOR_RGB2HSV)
    h,w = hsv.shape[:2]
    result = []
    # Header geometry measured on the user's fully opened three-card screenshots.
    for center in (.27,.505,.74):
        patch = hsv[int(.17*h):int(.21*h),int((center-.07)*w):int((center+.07)*w)]
        for kind,low,high in [('gold',(16,65,100),(38,255,255)),
                              ('purple',(125,45,90),(165,255,255))]:
            mask = cv2.inRange(patch,np.array(low),np.array(high))
            if np.count_nonzero(mask)/mask.size > .28:
                result.append((kind,(center,.2)))
                break
    return result


def encounter_confirmation_ready(image, rows):
    """The encounter confirm becomes orange after selection; grey is disabled."""
    import cv2
    import numpy as np
    w,h = image.size
    points = [(x/w,y/h) for text,score,(x,y) in rows
              if text.strip() == '确认' and score>=.94 and .65<x/w<.85 and .58<y/h<.72]
    if len(points) != 1:
        return False
    x,y = points[0]
    patch = image.crop((int((x-.075)*w),int((y-.023)*h),int((x+.075)*w),int((y+.023)*h)))
    hsv = cv2.cvtColor(np.array(patch.convert('RGB')),cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv,np.array((10,75,130)),np.array((40,255,255)))
    return np.count_nonzero(mask)/mask.size > .3
