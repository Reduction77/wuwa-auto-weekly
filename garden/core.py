import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager


class Halt(Exception):
    pass


def week_key(now=None):
    now = now or datetime.now(timezone(timedelta(hours=8)))
    # Mainland weekly reset: Monday 04:00; actual progress is always re-read.
    shifted = now - timedelta(hours=4)
    return (shifted.date() - timedelta(days=shifted.weekday())).isoformat()


class Control:
    def __init__(self):
        self.stop = threading.Event()
        self.paused = threading.Event()

    def check(self):
        while self.paused.is_set():
            if self.stop.wait(.1):
                raise Halt('已停止')
        if self.stop.is_set():
            raise Halt('已停止')

    def wait(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.check()
            self.stop.wait(min(.1, max(0, end - time.monotonic())))


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, batch TEXT, account TEXT, week TEXT, status TEXT, detail TEXT, at TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS identities(account TEXT PRIMARY KEY, uid TEXT UNIQUE)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def record(self, batch, account, status, detail=''):
        with self.connect() as db:
            db.execute('INSERT INTO runs(batch,account,week,status,detail,at) VALUES(?,?,?,?,?,?)',
                       (batch, account, week_key(), status, detail, datetime.now().isoformat(timespec='seconds')))

    def bind(self, account, uid):
        with self.connect() as db:
            row = db.execute('SELECT uid FROM identities WHERE account=?', (account,)).fetchone()
            if row and row[0] != uid:
                raise RuntimeError('登录 UID 与已绑定身份不一致')
            db.execute('INSERT OR IGNORE INTO identities VALUES(?,?)', (account, uid))
            row = db.execute('SELECT account FROM identities WHERE uid=?', (uid,)).fetchone()
            if row[0] != account:
                raise RuntimeError('不同登录条目指向同一 UID，请核对账号')

    def history(self):
        with self.connect() as db:
            return db.execute('SELECT at,account,status,detail FROM runs ORDER BY id DESC LIMIT 200').fetchall()


class CycleTracker:
    def __init__(self):
        self.seen = []

    def visit(self, uid):
        if not uid:
            raise RuntimeError('无法确认账号身份')
        if self.seen and uid == self.seen[-1]:
            raise RuntimeError('账号没有切换，不能判定遍历完成')
        if uid in self.seen:
            if uid == self.seen[0] and len(self.seen) > 1:
                return False
            raise RuntimeError('账号遍历出现异常重复')
        self.seen.append(uid)
        return True


@dataclass
class Observation:
    state: str
    values: dict


class Runner:
    def __init__(self, driver, store, control, emit, account_timeout=1800):
        self.driver, self.store, self.control, self.emit = driver, store, control, emit
        self.account_timeout = account_timeout

    def run_batch(self, accounts=None):
        """Use the native list once; execute each requested identity at most once."""
        available = self.driver.read_accounts()
        if not getattr(self.driver,'account_list_complete',False):
            raise RuntimeError('未确认完整账号列表，不能启动多账号批次')
        if not available or len(available)!=len(set(available)):
            raise RuntimeError('账号列表为空或存在重复，批次未启动')
        requested = list(available if accounts is None else accounts)
        if not requested or len(requested)!=len(set(requested)):
            raise RuntimeError('执行队列为空或包含重复账号')
        if any(account not in available for account in requested):
            raise RuntimeError('已保存账号列表发生变化，请重新读取账号')
        batch = datetime.now().isoformat()
        results = {}
        for account in requested:
            self.emit(account,'待执行','等待前一个账号完成')
        previous_callback = getattr(self.driver,'progress_callback',None)
        try:
            for index,account in enumerate(requested,1):
                self.control.check()
                def progress(detail, current=account, number=index):
                    self.emit(current,'执行中',f'[{number}/{len(requested)}] {detail}')
                self.driver.progress_callback=progress
                self.store.record(batch,account,'执行中')
                try:
                    progress('选择账号并核对身份')
                    uid=self.driver.login(account)
                    self.store.bind(account,uid)
                    progress('身份已核对，打开周度游历')
                    self.driver.collect_weekly_entry()
                    detail=self.driver.run_garden()
                    if not self.driver.recover_login():
                        raise RuntimeError('周常结束但未确认登录页，不切换下一账号')
                    results[account]='已完成'
                    self.store.record(batch,account,'已完成',detail)
                    self.emit(account,'已完成',detail)
                except Halt:
                    self.store.record(batch,account,'已停止')
                    self.emit(account,'已停止','批次已停止')
                    raise
                except Exception as error:
                    self.driver.evidence()
                    results[account]='失败'
                    self.store.record(batch,account,'失败',str(error))
                    self.emit(account,'失败',str(error))
                    # A partial game must not be silently abandoned to switch users.
                    if not self.driver.recover_login():
                        raise RuntimeError('当前账号失败且未回到登录页，批次停止；可单号续跑') from error
            return results
        finally:
            self.driver.progress_callback=previous_callback

    def run_cycle(self, limit=100):
        tracker = CycleTracker()
        batch = datetime.now().isoformat()
        for index in range(limit):
            self.control.check()
            uid = self.driver.login_next(first=index == 0)
            if not tracker.visit(uid):
                return
            account = f'UID {uid}'
            self.emit(account,'执行中','逐号遍历')
            self.store.record(batch,account,'执行中')
            try:
                self.clear(account)
                self.store.record(batch,account,'已完成','游历值已满，已执行两次领取点击')
                self.emit(account,'已完成','游历值已满，已执行两次领取点击')
            except Halt:
                self.store.record(batch,account,'已停止')
                raise
            except Exception as exc:
                self.driver.evidence()
                self.store.record(batch,account,'失败',str(exc))
                self.emit(account,'失败',str(exc))
                if not self.driver.recover_login():
                    raise RuntimeError('无法安全切换下一账号') from exc
        raise RuntimeError('达到账号遍历上限，未确认完整循环')

    def run(self, accounts):
        batch = datetime.now().isoformat()
        for account in accounts:
            self.control.check()
            self.emit(account, '执行中', '正在切换账号')
            self.store.record(batch, account, '执行中')
            try:
                uid = self.driver.login(account)
                self.store.bind(account, uid)
                self.clear(account)
                self.store.record(batch, account, '已完成', '游历值已满，已执行两次领取点击')
                self.emit(account, '已完成', '游历值已满，已执行两次领取点击')
            except Halt:
                self.store.record(batch, account, '已停止')
                self.emit(account, '已停止', '')
                raise
            except Exception as exc:
                self.driver.evidence()
                self.store.record(batch, account, '失败', str(exc))
                self.emit(account, '失败', str(exc))
                # Continue only after a positively identified login page.
                if not self.driver.recover_login():
                    raise RuntimeError('未恢复到登录页，批次已停止') from exc

    def clear(self, account):
        deadline = time.monotonic() + self.account_timeout
        last_progress = time.monotonic()
        previous = None
        while time.monotonic() < deadline:
            self.control.check()
            obs = self.driver.observe()
            self.emit(account, '执行中', obs.state)
            progress = (obs.state, json.dumps(obs.values, sort_keys=True))
            if progress != previous:
                previous, last_progress = progress, time.monotonic()
            if obs.state == 'weekly':
                current, target = obs.values.get('current'), 6000
                if isinstance(current, int) and isinstance(target, int) and target > 0 and current >= target:
                    self.driver.act('claim')
                    return
                else:
                    if current is None or target is None:
                        raise RuntimeError('无法读取周进度，停止操作')
                    self.driver.act('enter')
            else:
                self.driver.step(obs)
            if time.monotonic() - last_progress > 90:
                raise RuntimeError('90 秒没有可确认的进度变化')
            self.control.wait(.7)
        raise RuntimeError('单账号执行超时')
