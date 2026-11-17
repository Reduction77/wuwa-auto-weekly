import unittest
from garden.weekly import classify_guide


def scene(current, reward=None):
    items = [('活跃行迹',.08,.065),('周度游历',.33,.13),('幻梦游园·狂想',.2,.4),
             ('游历值',.21,.91),(str(current),.2,.86),
             ('通关可获得游历值6000',.5,.69)]
    items += [(str(n),.33+i*.11,.91) for i,n in enumerate(range(1000,6001,1000))]
    if reward: items.append((reward,.8,.9))
    return [(text,.99,(x*2560,y*1440)) for text,x,y in items]


class WeeklyTests(unittest.TestCase):
    def test_zero_not_confused_with_advertised_reward(self):
        view = classify_guide(scene(0),2560,1440)
        self.assertEqual((view.current,view.target,view.status),(0,6000,'尚未开始'))

    def test_partial(self):
        self.assertEqual(classify_guide(scene(3000),2560,1440).status,'部分完成')

    def test_full_score_uses_simple_rule(self):
        self.assertEqual(classify_guide(scene(6000),2560,1440).status,'积分已满，执行领取后结束')

    def test_explicit_reward_states(self):
        self.assertEqual(classify_guide(scene(6000,'一键领取'),2560,1440).status,'积分已满，执行领取后结束')
        self.assertEqual(classify_guide(scene(6000,'全部已领取'),2560,1440).status,'积分已满，执行领取后结束')

    def test_material_page(self):
        view = classify_guide([('素材获取',.99,(220,90)),('培养目标',.99,(500,220))],2560,1440)
        self.assertEqual(view.page,'materials')

    def test_daily_page(self):
        view = classify_guide([('活跃行迹',.99,(220,90)),('周度游历',.99,(850,190))],2560,1440)
        self.assertEqual(view.page,'activity')
        self.assertIsNone(view.current)
