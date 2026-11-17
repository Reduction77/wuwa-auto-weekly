"""Guide routing and the user-selected 6000-point completion rule."""
import re
from dataclasses import dataclass, field


@dataclass
class WeeklyView:
    page: str = 'unknown'
    current: int | None = None
    target: int | None = None
    rewards: str = 'unknown'
    targets: dict = field(default_factory=dict)

    @property
    def status(self):
        if self.current is None or self.target is None:
            return '进度待确认'
        if self.current < self.target:
            return '尚未开始' if self.current == 0 else '部分完成'
        return '积分已满，执行领取后结束'


def classify_guide(rows, width, height):
    clean = [(re.sub(r'\s+','',text),score,(x/width,y/height))
             for text,score,(x,y) in rows if score >= .9]
    def hits(word,region):
        l,t,r,b = region
        return [p for text,_,p in clean if word in text and l<p[0]<r and t<p[1]<b]
    weekly_tab = hits('周度游历',(.2,.07,.5,.2))
    active_title = hits('活跃行迹',(0,0,.3,.12))
    garden = hits('幻梦游园',(.1,.22,.45,.6))
    points_label = hits('游历值',(.12,.86,.3,.96))
    view = WeeklyView()
    if active_title and weekly_tab:
        view.page = 'activity'
        if len(weekly_tab) == 1:
            view.targets['weekly_tab'] = weekly_tab[0]
        if garden and points_label:
            view.page = 'weekly'
            view.target = 6000
            view.targets['enter'] = garden[0]
            # Last reward chest, measured on this client's weekly page.
            view.targets['claim'] = (.93,.89)
            numbers = [int(text) for text,score,(x,y) in clean if score>=.94
                       and re.fullmatch(r'\d{1,6}',text) and .17<x<.29 and .82<y<.89]
            if len(numbers)==1:
                view.current = numbers[0]
    elif hits('素材获取',(0,0,.3,.12)) and hits('培养目标',(.08,.1,.38,.23)):
        view.page = 'materials'
        # Observed activity category icon in this page's fixed left sidebar.
        view.targets['activity_category'] = (.039,.18)
    elif hits('索拉指南',(0,0,.35,.15)):
        view.page = 'guide'
    return view
