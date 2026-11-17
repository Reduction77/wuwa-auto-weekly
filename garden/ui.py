import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from .core import Control, Store, Runner, Halt
from .widgets import RoundButton, Card, BLUE, BG, INK


class App(tk.Tk):
    def __init__(self, root):
        super().__init__()
        self.root = root
        self.title('周常乐园 · 多账号助手')
        self.geometry('1120x790')
        self.minsize(980,700)
        self.configure(bg=BG)
        self.data = root/'data'
        self.data.mkdir(exist_ok=True)
        profile = self.data/'profile.json'
        if not profile.exists():
            import shutil
            shutil.copyfile(root/'profiles'/'cn.json',profile)
        self.store = Store(self.data/'history.db')
        self.events = queue.Queue()
        self.control = Control()
        self.busy = False
        self.driver = None
        self.build_ui()
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.after(100,self.drain)
        self.refresh_history()
        self.restore_accounts()

    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.',font=('Microsoft YaHei UI',10),background='white',foreground=INK)
        style.configure('Treeview',background='white',fieldbackground='white',foreground=INK,
                        rowheight=42,borderwidth=0,relief='flat')
        style.configure('Treeview.Heading',background='#F0F6FD',foreground='#59718E',
                        font=('Microsoft YaHei UI',10,'bold'),padding=(10,12),relief='flat')
        style.map('Treeview',background=[('selected','#DCEEFF')],foreground=[('selected','#005A9E')])
        style.map('Treeview.Heading',background=[('active','#E8F1FB')])
        style.configure('TCheckbutton',background='white',padding=6)
        style.map('TCheckbutton',background=[('active','white')])
        style.configure('Vertical.TScrollbar',background='#CEE0F2',troughcolor='white',borderwidth=0)

        header = tk.Frame(self,bg=BG)
        header.pack(fill='x',padx=28,pady=(24,16))
        tk.Label(header,text='周常乐园',font=('Microsoft YaHei UI',26,'bold'),fg=INK,bg=BG).pack(anchor='w')
        tk.Label(header,text='把重复的周常，交给助手。',font=('Microsoft YaHei UI',11),fg='#647B95',bg=BG).pack(anchor='w',pady=(5,0))
        navigation = tk.Frame(self,bg=BG)
        navigation.pack(fill='x',padx=28,pady=(0,14))
        self.nav = {}
        self.pages = {}
        self.page_host = tk.Frame(self,bg=BG)
        self.page_host.pack(fill='both',expand=True,padx=28,pady=(0,14))
        for key,title in [('run','账号队列'),('history','运行历史'),('help','使用说明')]:
            button = RoundButton(navigation,title,lambda k=key:self.show_page(k),width=112)
            button.pack(side='left',padx=(0,8))
            self.nav[key] = button
            card = Card(self.page_host)
            self.pages[key] = card
        run = self.pages['run'].body
        bar = tk.Frame(run,bg='white')
        bar.pack(fill='x',pady=(2,16))
        self.read_button = RoundButton(bar,'读取账号',lambda:self.work(self.read_accounts),width=104)
        self.read_button.pack(side='left')
        self.start_button = RoundButton(bar,'开始执行',self.start,primary=True,width=116)
        self.start_button.pack(side='left',padx=(8,14))
        self.cycle = tk.BooleanVar(value=False)
        self.all_check = ttk.Checkbutton(bar,text='全部已保存账号',variable=self.cycle)
        self.all_check.pack(side='left')
        self.stop_button = RoundButton(bar,'停止',self.stop,width=80)
        self.stop_button.pack(side='right')
        self.pause_button = RoundButton(bar,'暂停',self.pause,width=80)
        self.pause_button.pack(side='right',padx=8)
        self.pause_button.configure(state='disabled')
        self.stop_button.configure(state='disabled')
        tk.Label(run,text='执行账号',bg='white',fg=INK,font=('Microsoft YaHei UI',12,'bold')).pack(anchor='w')
        tk.Label(run,text='双击条目启用或停用；每次执行都会重新核对游戏内进度。',
                 bg='white',fg='#647B95').pack(anchor='w',pady=(4,12))
        self.table = self.create_table(run,[('enabled','启用',50),('account','账号',165),
                                           ('status','状态',90),('detail','当前步骤 / 结果',540)])
        self.table.bind('<Double-1>',self.toggle)
        tk.Label(run,text='最近消息',bg='white',fg='#647B95').pack(anchor='w',pady=(12,6))
        self.log = tk.Text(run,height=3,bg='#F5F9FE',fg='#526C89',font=('Microsoft YaHei UI',9),
                           relief='flat',bd=0,padx=12,pady=8,state='disabled',wrap='word')
        self.log.pack(fill='x')
        history = self.pages['history'].body
        history_bar = tk.Frame(history,bg='white')
        history_bar.pack(fill='x',pady=(0,14))
        tk.Label(history_bar,text='最近 200 条记录',bg='white',fg=INK,
                 font=('Microsoft YaHei UI',12,'bold')).pack(side='left')
        RoundButton(history_bar,'刷新历史',self.refresh_history,width=110).pack(side='right')
        self.history = self.create_table(history,[('time','时间',175),('account','账号',155),
                                                  ('status','状态',100),('detail','详情',510)])
        help_page = self.pages['help'].body
        for title,body in [
            ('开始之前','打开鸣潮官服，停留在已保存账号的登录界面。保持游戏窗口非最小化。'),
            ('三个步骤','1. 读取账号，双击停用不需要的条目。\n2. 点击“开始执行”，依次完成周常并返回登录。\n3. 在运行历史中查看每个账号的结果。'),
            ('暂停与停止','暂停会在当前步骤的检查点生效；停止后保留游戏当前页面，不会自动退出游戏。'),
            ('遇到问题','本项目仍在完善，部分后台登录点击可能未生效。失败时查看运行历史和本机诊断文件。\n重新执行前，请手动回到账号登录界面；权限错误请使用 start-admin.cmd 启动。'),
            ('本机数据','账号列表、身份绑定、运行历史和诊断截图保存在 data 文件夹，不随源码上传。')]:
            tk.Label(help_page,text=title,bg='white',fg=INK,font=('Microsoft YaHei UI',12,'bold')).pack(anchor='w',pady=(6,4))
            tk.Label(help_page,text=body,bg='white',fg='#647B95',justify='left',wraplength=860).pack(anchor='w',pady=(0,4))
        RoundButton(help_page,'打开数据目录',self.open_data,width=150).pack(anchor='w',pady=(8,0))
        footer = tk.Frame(self,bg=BG)
        footer.pack(fill='x',padx=30,pady=(0,18))
        tk.Label(footer,text='●',fg=BLUE,bg=BG).pack(side='left',anchor='n')
        self.status = tk.StringVar(value='准备就绪 · 请在游戏登录界面读取账号')
        tk.Label(footer,textvariable=self.status,bg=BG,fg='#526C89',wraplength=980,
                 justify='left',anchor='w').pack(side='left',fill='x',expand=True,padx=8)
        self.show_page('run')

    def create_table(self, parent, columns):
        frame = tk.Frame(parent,bg='white')
        frame.pack(fill='both',expand=True)
        table = ttk.Treeview(frame,columns=[c[0] for c in columns],show='headings',selectmode='browse',height=5)
        for key,title,width in columns:
            table.heading(key,text=title)
            table.column(key,width=width,minwidth=width if key != 'detail' else 200,
                         stretch=key=='detail',anchor='center' if key=='enabled' else 'w')
        scroll = ttk.Scrollbar(frame,orient='vertical',command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y')
        table.pack(side='left',fill='both',expand=True)
        return table

    def show_page(self, key):
        for name,card in self.pages.items():
            card.pack_forget()
            self.nav[name].primary = name == key
            self.nav[name].draw()
        self.pages[key].pack(fill='both',expand=True)
        if key == 'history':
            self.refresh_history()

    def restore_accounts(self):
        path = self.data/'accounts.json'
        if not path.exists():
            return
        try:
            accounts = json.loads(path.read_text(encoding='utf-8'))
            from .cn_login import account_name
            if not isinstance(accounts,list) or not all(isinstance(a,str) and account_name(a) for a in accounts):
                return
            for account in dict.fromkeys(accounts):
                self.table.insert('','end',values=('✓',account,'已保存','执行前重新核对游戏账号列表'))
        except (ValueError,OSError):
            pass

    def open_data(self):
        import os
        os.startfile(self.data)

    def connect(self):
        from .windows import windows, Window
        matches = windows()
        if len(matches) != 1:
            raise RuntimeError(f'找到 {len(matches)} 个游戏窗口，需要唯一的鸣潮游戏窗口')
        return Window(matches[0][0])

    def make_driver(self, validate=True):
        from .vision import VisionDriver
        path = self.data/'profile.json'
        if not path.exists():
            raise RuntimeError('缺少官服校准配置 data/profile.json；请先进行实机适配')
        driver = VisionDriver(self.connect(),path,self.control,self.data/'evidence')
        if validate:
            driver.validate()
        return driver

    def read_accounts(self):
        self.driver = self.make_driver(validate=False)
        try:
            accounts = self.driver.read_accounts()
            if not accounts:
                raise RuntimeError('没有识别到账号')
            self.events.put(('accounts',accounts))
            complete = getattr(self.driver,'account_list_complete',False)
            detail = (f'已从游戏账号控件读取完整列表：{len(accounts)} 个账号' if complete else
                      f'已读取当前可见的 {len(accounts)} 个账号；列表完整性尚未验证')
            self.events.put(('log',detail))
            self.store.record('账号读取','当前窗口','成功',detail)
        except Exception as error:
            self.driver.evidence()
            self.store.record('账号读取','当前窗口','失败',str(error))
            raise
        finally:
            self.driver.window.close()

    def work(self, action):
        if self.busy:
            return
        self.busy = True
        self.control = Control()
        self.read_button.configure(state='disabled')
        self.start_button.configure(state='disabled')
        self.all_check.configure(state='disabled')
        self.pause_button.configure(state='normal',text='暂停')
        self.stop_button.configure(state='normal')
        def run():
            try:
                action()
            except Halt:
                self.events.put(('log','已停止'))
            except Exception as error:
                self.events.put(('error',str(error)))
            finally:
                self.events.put(('idle',None))
        threading.Thread(target=run,daemon=True).start()

    def start(self):
        accounts = [self.table.item(i,'values')[1] for i in self.table.get_children() if self.table.item(i,'values')[0]=='✓']
        cycle = self.cycle.get()
        if not accounts and not cycle:
            messagebox.showinfo('账号队列','请先读取账号并选择要执行的账号')
            return
        def task():
            driver = self.make_driver(validate=False)
            try:
                if not driver.profile.get('cn_login'):
                    raise RuntimeError('多账号批次仅支持官服配置')
                runner = Runner(driver,self.store,self.control,lambda *args:self.events.put(('update',args)))
                result = runner.run_batch(None if cycle else accounts)
            finally:
                driver.window.close()
            completed=sum(status=='已完成' for status in result.values())
            self.events.put(('log',f'批次处理结束：完成 {completed} / {len(result)}，失败 {len(result)-completed}'))
        self.work(task)

    def pause(self):
        if self.busy:
            if self.control.paused.is_set():
                self.control.paused.clear()
                self.status.set('继续运行')
                self.pause_button.configure(text='暂停')
            else:
                self.control.paused.set()
                self.status.set('已请求暂停')
                self.pause_button.configure(text='继续')

    def stop(self):
        if not self.busy:
            return
        self.control.stop.set()
        self.status.set('已请求停止')

    def toggle(self,event):
        if self.busy:
            return
        item = self.table.identify_row(event.y)
        if item:
            values = list(self.table.item(item,'values'))
            values[0] = '' if values[0] else '✓'
            self.table.item(item,values=values)

    def refresh_history(self):
        self.history.delete(*self.history.get_children())
        for row in self.store.history():
            self.history.insert('', 'end',values=row)

    def drain(self):
        try:
            while True:
                kind,value = self.events.get_nowait()
                if kind == 'idle':
                    self.busy = False
                    self.read_button.configure(state='normal')
                    self.start_button.configure(state='normal')
                    self.all_check.configure(state='normal')
                    self.pause_button.configure(state='disabled',text='暂停')
                    self.stop_button.configure(state='disabled')
                    self.refresh_history()
                elif kind == 'accounts':
                    (self.data/'accounts.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
                    self.table.delete(*self.table.get_children())
                    for account in value:
                        self.table.insert('','end',values=('✓',account,'待执行',''))
                    self.status.set(f'已读取 {len(value)} 个账号')
                elif kind == 'update':
                    account,status,detail = value
                    found = False
                    for item in self.table.get_children():
                        row = self.table.item(item,'values')
                        if row[1] == account:
                            found = True
                            self.table.item(item,values=(row[0],account,status,detail))
                    if not found:
                        self.table.insert('','end',values=('✓',account,status,detail))
                    self.status.set(f'{account} · {status} · {detail}')
                else:
                    self.status.set(value)
                    self.log.configure(state='normal')
                    self.log.insert('end',f'{datetime.now():%H:%M:%S}  {value}\n')
                    self.log.see('end')
                    self.log.configure(state='disabled')
        except queue.Empty:
            pass
        self.after(100,self.drain)

    def close(self):
        self.control.stop.set()
        if self.busy:
            self.status.set('正在停止任务后关闭…')
            self.after(150,self.close)
        else:
            self.destroy()
