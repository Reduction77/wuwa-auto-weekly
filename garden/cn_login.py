"""Mainland login observations; independent of the international SDK ComboBox.

Coordinates here are normalized OCR observations, not copied click coordinates.
Only the account text center is selectable; the row's delete icon is excluded.
"""
import re
from dataclasses import dataclass, field


def account_name(text):
    text = re.sub(r'\s+', '', text).replace('＊', '*').replace('∗', '*')
    return text if re.fullmatch(r'1\d{2}\*{4}\d{4}', text) else None


@dataclass
class LoginView:
    state: str = 'unknown'
    selected: str | None = None
    accounts: list = field(default_factory=list)
    targets: dict = field(default_factory=dict)


def classify(rows, width, height):
    """rows are (text, confidence, pixel center)."""
    clean = [(re.sub(r'\s+', '', text), score, (x/width,y/height))
             for text,score,(x,y) in rows if score >= .88]
    def find(text, region):
        left,top,right,bottom = region
        hits = [point for value,_,point in clean if value == text and
                left < point[0] < right and top < point[1] < bottom]
        return hits[0] if len(hits) == 1 else None
    view = LoginView()
    confirm = find('确认登出',(.5,.5,.8,.75))
    prompt = find('确认登出账号?',(.3,.3,.7,.6)) or find('确认登出账号？',(.3,.3,.7,.6))
    if confirm and prompt:
        return LoginView('logout_confirm',targets={'confirm_logout':confirm})
    brand = find('KUROGAMES',(.35,.3,.65,.42))
    if brand:
        accounts = [(account_name(text),point) for text,score,point in clean
                    if score >= .93 and account_name(text) and .39 < point[0] < .56]
        header = [(name,point) for name,point in accounts if .42 < point[1] < .495]
        body = [(name,point) for name,point in accounts if .495 < point[1] < .88]
        if len(header) != 1:
            return view
        view.selected = header[0][0]
        # The chevron is to the right of the header; derived from observed panel.
        view.targets['account_list'] = (.607,header[0][1][1])
        view.targets['close_account_list'] = view.targets['account_list']
        if body:
            names = [name for name,_ in body]
            if len(names) != len(set(names)):
                return LoginView('ambiguous_accounts')
            view.state = 'account_list'
            view.accounts = sorted(body,key=lambda row:row[1][1])
        else:
            login = find('登录',(.35,.5,.65,.61))
            if login:
                view.state = 'login'
                view.targets['login'] = login
        return view
    enter = find('登入',(.88,.24,.98,.36))
    if enter:
        return LoginView('signed_out',targets={'open_login':enter})
    account = find('账号',(.88,.48,.98,.59))
    connect = find('点击连接',(.38,.88,.62,.98))
    if account and connect:
        return LoginView('connected_title',targets={'logout':account,'connect':connect})
    return view


RECOVERY = {
    'connected_title': 'logout',
    'logout_confirm': 'confirm_logout',
    'signed_out': 'open_login',
    'account_list': 'close_account_list',
}


EXPECTED = {
    'logout': 'logout_confirm',
    'confirm_logout': 'signed_out',
    'open_login': 'login',
    'account_list': 'account_list',
    'close_account_list': 'login',
}


def open_account_list(driver):
    """One action per verified transition, never retry a stale click."""
    for _ in range(6):
        state = driver.observe().state
        if state == 'account_list':
            return
        action = 'account_list' if state == 'login' else RECOVERY.get(state)
        if action is None:
            raise RuntimeError(f'无法从页面 {state} 打开账号列表')
        driver.act(action)
        expected = EXPECTED[action]
        for _ in range(12):
            driver.control.wait(.5)
            after = driver.observe().state
            if after == expected:
                break
            # Some clients open the login panel immediately after logout.
            if action == 'confirm_logout' and after == 'login':
                break
            if after not in (state, 'unknown'):
                raise RuntimeError(f'{action} 后出现意外页面 {after}')
        else:
            raise RuntimeError(f'{action} 后未出现预期页面 {expected}，停止操作')
    raise RuntimeError('打开账号列表超过阶段上限')
