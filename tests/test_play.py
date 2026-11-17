import unittest
from garden.play import GardenPolicy, choose_reward, is_garden_board, garden_page, reward_candidates
import json
from pathlib import Path


def rows(*items):
    return [(text,.99,(x*1000,y*1000)) for text,x,y in items]


class PolicyTests(unittest.TestCase):
    def test_real_capped_preparation_exits_on_resume_and_return(self):
        sample=json.loads((Path(__file__).parent/'fixtures/preparation_capped.json').read_text(encoding='utf-8'))
        for returning in (False,True):
            policy=GardenPolicy()
            policy.returning=returning
            self.assertEqual(policy.decide(sample,2560,1440).name,'退出乐园准备页')

    def test_unrelated_cap_text_does_not_finish_week(self):
        sample=rows(('幻梦游园',.15,.1),('开始游戏',.9,.9),('本周游历值',.08,.15),
                    ('已达到上限',.7,.5))
        policy=GardenPolicy(); policy.returning=True
        self.assertEqual(policy.decide(sample,1000,1000).name,'unknown')

    def test_numeric_full_preparation_also_exits_on_fresh_resume(self):
        sample=rows(('幻梦游园',.15,.1),('开始游戏',.9,.9),('6000/6000',.1,.2))
        self.assertEqual(GardenPolicy().decide(sample,1000,1000).name,'退出乐园准备页')

    def test_conflicting_preparation_progress_stops(self):
        sample=rows(('幻梦游园',.15,.1),('开始游戏',.9,.9),('本周游历值',.08,.15),
                    ('已达到上限',.1,.2),('3000/6000',.2,.2))
        self.assertEqual(GardenPolicy().decide(sample,1000,1000).name,'unknown')
    def test_real_success_returns_instead_of_endless_mode(self):
        sample=json.loads((Path(__file__).parent/'fixtures/result_success.json').read_text(encoding='utf-8'))
        self.assertEqual(garden_page(sample,2560,1440),'result')
        policy=GardenPolicy()
        decision=policy.decide(sample,2560,1440)
        self.assertEqual(decision.name,'返回并复查周进度')
        self.assertAlmostEqual(decision.point[0],.664,places=2)
        self.assertTrue(policy.returning)
    def test_encounter_select_before_confirm(self):
        sample=json.loads((Path(__file__).parent/'fixtures/encounter.json').read_text(encoding='utf-8'))
        self.assertEqual(garden_page(sample,2560,1440),'encounter')
        policy=GardenPolicy()
        first=policy.decide(sample,2560,1440)
        self.assertEqual(first.name,'选择最下面的不感兴趣')
        self.assertAlmostEqual(first.point[1],.556,places=2)
        self.assertEqual(policy.decide(sample,2560,1440).name,'unknown')
        self.assertEqual(policy.decide(sample,2560,1440,confirmation_ready=True).name,'确认奇缘选项')
        self.assertEqual(policy.decide(sample,2560,1440,confirmation_ready=True).name,'unknown')

    def test_encounter_missing_option_never_confirms(self):
        sample=rows(('奇缘异遇',.62,.18),('确认',.75,.63))
        self.assertEqual(GardenPolicy().decide(sample,1000,1000,confirmation_ready=True).name,'unknown')

    def test_encounter_lowest_full_label(self):
        sample=rows(('奇缘异遇',.62,.18),('不感兴趣',.5,.3),('你对此不感兴趣',.5,.55),('确认',.75,.63))
        self.assertEqual(GardenPolicy().decide(sample,1000,1000).point,(.5,.55))

    def test_encounter_confirm_colour(self):
        from PIL import Image,ImageDraw
        from garden.play import encounter_confirmation_ready
        sample=rows(('确认',.75,.63))
        image=Image.new('RGB',(1000,1000),'gray')
        self.assertFalse(encounter_confirmation_ready(image,sample))
        ImageDraw.Draw(image).rectangle((670,600,830,660),fill=(238,174,65))
        self.assertTrue(encounter_confirmation_ready(image,sample))

    def test_real_shop_purchase_then_close(self):
        policy=GardenPolicy()
        for fixture,expected in [('shop_available','商店购买'),('shop_sold_out','离开商店')]:
            sample=json.loads((Path(__file__).parent/'fixtures'/f'{fixture}.json').read_text(encoding='utf-8'))
            self.assertEqual(garden_page(sample,2560,1440),'shop')
            self.assertEqual(policy.decide(sample,2560,1440).name,expected)

    def test_sold_out_overrides_purchase_template(self):
        sample=rows(('乐园商店',.22,.06),('已售罄',.76,.7))
        decision=GardenPolicy().decide(sample,1000,1000,features={'shop_buy':(.8,.7),'shop_close':(.82,.06)})
        self.assertEqual(decision.name,'离开商店')

    def test_generic_close_is_not_shop_exit(self):
        self.assertEqual(GardenPolicy().decide(rows(('关闭',.82,.06)),1000,1000).name,'unknown')
        sample=rows(('乐园商店',.22,.06),('关闭',.4,.5))
        self.assertEqual(GardenPolicy().decide(sample,1000,1000).name,'unknown')

    def test_real_stage_result_resumes_and_advances(self):
        sample = json.loads((Path(__file__).parent/'fixtures/stage_result.json').read_text(encoding='utf-8'))
        self.assertEqual(garden_page(sample,2560,1440),'stage_result')
        policy = GardenPolicy()
        decision = policy.decide(sample,2560,1440)
        self.assertEqual(decision.name,'进入新阶段')
        self.assertAlmostEqual(decision.point[0],.617,places=2)
        self.assertFalse(policy.returning)

    def test_stage_template_fallback_without_button_ocr(self):
        sample = rows(('第2阶段收益结算',.6,.23),('本阶段乐园收益目标',.5,.44))
        self.assertEqual(GardenPolicy().decide(sample,1000,1000,features={'new_stage':(.62,.66)}).point,(.62,.66))

    def test_stage_is_not_final_even_with_6000(self):
        sample = rows(('第7阶段收益结算',.6,.23),('本阶段乐园收益目标',.5,.44),
                      ('进入新阶段',.62,.66),('6000',.6,.5))
        self.assertEqual(GardenPolicy().decide(sample,1000,1000).name,'进入新阶段')

    def test_reward_page_can_resume(self):
        sample=json.loads((Path(__file__).parent/'fixtures/reward_choice.json').read_text(encoding='utf-8'))
        self.assertEqual(garden_page(sample,2560,1440),'reward')
        self.assertEqual(GardenPolicy().decide(sample,2560,1440).name,'选择奖励（金色优先）')

    def test_rarity_uses_header_not_body_text(self):
        from PIL import Image, ImageDraw
        image=Image.new('RGB',(1000,1000),'gray')
        draw=ImageDraw.Draw(image)
        draw.rectangle((200,170,340,210),fill=(180,80,230))
        draw.rectangle((670,170,810,210),fill=(235,190,60))
        draw.rectangle((435,400,575,500),fill=(235,190,60))
        choices=reward_candidates(image)
        self.assertEqual(choose_reward(choices),(.74,.2))
        self.assertEqual(len(choices),2)

    def test_enter_next_day_full_label(self):
        decision = GardenPolicy().decide(rows(('进入下一天',.9,.88)),1000,1000)
        self.assertEqual(decision.name,'下一天')
        self.assertEqual(decision.point,(.9,.88))

    def test_board_can_resume_without_entrance_title(self):
        board = rows(('本周游园',.07,.06),('阶段：1/7',.09,.11),('乐园详情',.07,.22))
        self.assertTrue(is_garden_board(board,1000,1000))
        self.assertFalse(is_garden_board(board[1:],1000,1000))
        self.assertFalse(is_garden_board(rows(('进入下一天',.9,.88)),1000,1000))

    def test_gold_before_purple(self):
        self.assertEqual(choose_reward([('purple',(.2,.5)),('gold',(.7,.5))]),(.7,.5))

    def test_purple_and_fallback(self):
        self.assertEqual(choose_reward([('purple',(.2,.5))]),(.2,.5))
        self.assertEqual(choose_reward([]),(.5,.2))

    def test_lowest_decline(self):
        p = GardenPolicy()
        self.assertEqual(p.decide(rows(('不感兴趣',.3,.4),('不感兴趣',.3,.7)),1000,1000).point,(.3,.7))
        self.assertEqual(p.decide(rows(('确认',.7,.8)),1000,1000).name,'确认选择')

    def test_reward_before_next_day(self):
        p = GardenPolicy()
        d = p.decide(rows(('跳过',.8,.8),('确认',.7,.8),('下一天',.9,.9)),1000,1000,[('gold',(.4,.5))])
        self.assertEqual(d.point,(.4,.5))

    def test_blessing_sequence(self):
        p = GardenPolicy()
        entrance = rows(('幻梦游园',.15,.1),('开始游戏',.9,.9),('祝福·幻梦机遇',.48,.85))
        self.assertEqual(p.decide(entrance,1000,1000).name,'打开祝福选择')
        popup = rows(('选择祝福',.5,.2),('确认',.8,.85))
        self.assertEqual(p.decide(popup,1000,1000).name,'选择第一个祝福')
        self.assertEqual(p.decide(popup,1000,1000).name,'确认祝福')
        self.assertEqual(p.decide(entrance,1000,1000).name,'开始游戏')

    def test_result_rule_and_recheck(self):
        for score,expected in [('3000/6000','返回并复查周进度'),('6000/6000','返回并复查周进度')]:
            p = GardenPolicy()
            d = p.decide(rows(('返回主页',.3,.8),('重新挑战',.7,.8),(score,.5,.5)),1000,1000)
            self.assertEqual(d.name,expected)

    def test_empty_result_does_not_finish(self):
        p = GardenPolicy()
        self.assertEqual(p.decide(rows(('返回主页',.3,.8),('重新挑战',.7,.8)),1000,1000).name,'返回并复查周进度')
        entrance=rows(('幻梦游园',.15,.1),('开始游戏',.9,.9))
        self.assertEqual(p.decide(entrance,1000,1000).name,'unknown')

    def test_real_failure_confirms_then_checks_preparation_score(self):
        sample=json.loads((Path(__file__).parent/'fixtures/stage_failure.json').read_text(encoding='utf-8'))
        p=GardenPolicy()
        self.assertEqual(p.decide(sample,2560,1440).name,'确认阶段结束')
        self.assertTrue(p.returning)
        self.assertEqual(p.decide(rows(('返回主页',.3,.8),('重新挑战',.7,.8)),1000,1000).name,'返回并复查周进度')
        entrance=rows(('幻梦游园',.15,.1),('开始游戏',.9,.9),('祝福·幻梦机遇',.48,.85),('3000/6000',.1,.2))
        self.assertEqual(p.decide(entrance,1000,1000).name,'打开祝福选择')
        self.assertFalse(p.returning)

    def test_final_stage_and_full_week_exit(self):
        p=GardenPolicy()
        final=rows(('第7阶段收益结算',.62,.23),('本阶段乐园收益目标',.5,.44),('确认',.62,.66))
        self.assertEqual(p.decide(final,1000,1000).name,'确认阶段结束')
        entrance=rows(('幻梦游园',.15,.1),('开始游戏',.9,.9),('6000/6000',.1,.2))
        self.assertEqual(p.decide(entrance,1000,1000).name,'退出乐园准备页')

    def test_ambiguous_button_is_not_clicked(self):
        p = GardenPolicy()
        self.assertEqual(p.decide(rows(('确认',.3,.8),('确认',.7,.8)),1000,1000).name,'unknown')
