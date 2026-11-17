import unittest
import json
import main
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from garden.vision import VisionDriver
from garden.return_login import menu_visible, return_confirmation


def rows(*items):
    return [(text,.99,(x*1000,y*1000)) for text,x,y in items]


class ReturnTests(unittest.TestCase):
    def test_ignored_guide_escape_uses_close_icon_once(self):
        d=VisionDriver.__new__(VisionDriver)
        d.control=Mock(); d.report=Mock(); d.image=Mock()
        d.frame=Mock(size=(1000,1000),width=1000,height=1000)
        d.profile={'templates':{'guide_close':{}}}
        d.locate=Mock(return_value=(942,58))
        d.window=Mock(); d.window.account_control.side_effect=[None,None,None,None,123]
        guide=rows(('活跃行迹',.08,.06),('周度游历',.33,.13))
        d.texts=Mock(side_effect=[guide,guide,guide,rows(('特征码:123456789',.9,.98)),[]])
        with tempfile.TemporaryDirectory() as folder, patch('garden.vision.time.monotonic',side_effect=range(0,1000,2)):
            d.evidence_dir=Path(folder)
            d.return_to_login()
        d.window.click.assert_called_once_with(942,58)
        d.locate.assert_called_once_with('guide_close')
        self.assertEqual(d.window.key.call_count,2)

    def test_real_exit_dialog_clicks_return_login(self):
        sample=json.loads((Path(__file__).parent/'fixtures/exit_dialog.json').read_text(encoding='utf-8'))
        point=return_confirmation(sample,2560,1440)
        self.assertAlmostEqual(point[0],.65625)
        d=VisionDriver.__new__(VisionDriver)
        d.control=Mock(); d.report=Mock(); d.image=Mock()
        d.frame=Mock(size=(2560,1440),width=2560,height=1440)
        d.window=Mock(); d.window.account_control.side_effect=[None,123]
        d.texts=Mock(side_effect=[sample,[]])
        with tempfile.TemporaryDirectory() as folder:
            d.evidence_dir=Path(folder)
            d.return_to_login()
        d.window.click.assert_called_once_with(point[0]*2560,point[1]*1440)
        d.window.key.assert_not_called()

    def test_ambiguous_return_button_is_not_clicked(self):
        sample=rows(('是否确定退出游戏？',.5,.48),('退出游戏',.33,.63),('返回登录',.65,.63),('返回登录',.7,.63))
        self.assertIsNone(return_confirmation(sample,1000,1000))

    def test_guide_to_world_menu_confirm_login_sequence(self):
        d=VisionDriver.__new__(VisionDriver)
        d.control=Mock()
        d.report=Mock()
        d.image=Mock()
        d.frame=Mock(size=(1000,1000),width=1000,height=1000)
        d.window=Mock()
        d.window.account_control.side_effect=[None,None,None,None,123]
        d.texts=Mock(side_effect=[
            rows(('活跃行迹',.08,.06),('周度游历',.33,.13)),
            rows(('特征码:123456789',.9,.98)),
            rows(('共鸣者',.5,.4),('背包',.6,.4),('任务',.7,.4)),
            rows(('是否返回登录界面？',.5,.4),('确认',.65,.65)),
            []])
        with tempfile.TemporaryDirectory() as folder:
            d.evidence_dir=Path(folder)
            d.return_to_login()
        self.assertEqual([call.args for call in d.window.key.call_args_list],[(27,),(27,)])
        self.assertEqual([call.args for call in d.window.click.call_args_list],[(40.,960.),(650.,650.)])

    def test_menu_requires_multiple_anchors(self):
        self.assertFalse(menu_visible(rows(('设置',.5,.5))))
        self.assertTrue(menu_visible(rows(('共鸣者',.5,.4),('背包',.6,.4),('任务',.7,.4))))

    def test_return_prompt_and_button(self):
        self.assertEqual(return_confirmation(rows(('是否返回登录界面？',.5,.4),('确认',.65,.65)),1000,1000),(.65,.65))
        self.assertIsNone(return_confirmation(rows(('是否退出游戏？',.5,.4),('确认',.65,.65)),1000,1000))
        self.assertIsNone(return_confirmation(rows(('确认',.65,.65)),1000,1000))
