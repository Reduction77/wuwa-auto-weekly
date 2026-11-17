"""Bounded guide -> world -> menu -> login routing."""
import re


def menu_visible(rows):
    words = {re.sub(r'\s+','',text) for text,score,_ in rows if score >= .94}
    return len(words & {'共鸣者','背包','任务','好友','设置','终端','唤取','商城'}) >= 3


def return_confirmation(rows, width, height):
    words = [(re.sub(r'\s+','',text),(x/width,y/height)) for text,score,(x,y) in rows if score >= .94]
    # This client offers two different actions, not a generic confirmation.
    exit_prompt = any(text in ('是否确定退出游戏？','是否确定退出游戏?','是否退出游戏？','是否退出游戏?')
                      and .3<x<.7 and .3<y<.6 for text,(x,y) in words)
    exits = [p for text,p in words if text == '退出游戏' and .2<p[0]<.45 and .55<p[1]<.75]
    returns = [p for text,p in words if text == '返回登录' and .55<p[0]<.8 and .55<p[1]<.75]
    if exit_prompt and len(exits)==1 and len(returns)==1:
        return returns[0]
    prompt = any(re.search(r'(返回|回到|退出至).{0,8}(登录|登入|标题)|登出',text)
                 and .15<x<.85 and .2<y<.7 for text,(x,y) in words)
    buttons = [p for text,p in words if text in ('确认','确定','确认退出','确认登出')
               and .45<p[0]<.85 and .45<p[1]<.85]
    return buttons[0] if prompt and len(buttons)==1 else None
