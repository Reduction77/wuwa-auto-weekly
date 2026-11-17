import unittest
from garden.cn_login import classify, account_name, open_account_list
from garden.core import Observation


def rows(*items):
    return [(text,.99,(x*2560,y*1440)) for text,x,y in items]


class LoginTests(unittest.TestCase):
    def test_complete_navigation(self):
        class Driver:
            def __init__(self):
                self.state = 'connected_title'
                self.actions = []
                self.control = type('Control',(),{'wait':lambda self,t:None})()
            def observe(self): return Observation(self.state,{})
            def act(self,action):
                self.actions.append(action)
                self.state = {'logout':'logout_confirm','confirm_logout':'signed_out',
                              'open_login':'login','account_list':'account_list'}[action]
        driver = Driver()
        open_account_list(driver)
        self.assertEqual(driver.actions,['logout','confirm_logout','open_login','account_list'])

    def test_ignored_click_not_repeated(self):
        class Driver:
            control = type('Control',(),{'wait':lambda self,t:None})()
            actions = []
            def observe(self): return Observation('connected_title',{})
            def act(self,action): self.actions.append(action)
        driver = Driver()
        with self.assertRaises(RuntimeError): open_account_list(driver)
        self.assertEqual(driver.actions,['logout'])

    def test_confirmation_requires_prompt(self):
        self.assertEqual(classify(rows(('确认登出',.66,.63)),2560,1440).state,'unknown')
        view = classify(rows(('确认登出',.66,.63),('确认登出账号？',.5,.48)),2560,1440)
        self.assertEqual(view.state,'logout_confirm')

    def test_header_not_counted_twice(self):
        view = classify(rows(('KURO GAMES',.5,.365),('138****0001',.46,.46),
                             ('138****0001',.46,.525),('138****0002',.46,.59)),2560,1440)
        self.assertEqual(view.state,'account_list')
        self.assertEqual(len(view.accounts),2)
        self.assertTrue(all(x < .56 for _,(x,y) in view.accounts))

    def test_duplicate_rows_fail_closed(self):
        view = classify(rows(('KURO GAMES',.5,.365),('138****0001',.46,.46),
                             ('138****0001',.46,.525),('138****0001',.46,.59)),2560,1440)
        self.assertEqual(view.state,'ambiguous_accounts')

    def test_login_not_signed_out_background(self):
        view = classify(rows(('KURO GAMES',.5,.365),('138****0001',.46,.46),
                             ('登录',.5,.55),('登入',.945,.31)),2560,1440)
        self.assertEqual(view.state,'login')

    def test_no_digit_substitution(self):
        self.assertIsNone(account_name('138****O001'))
        self.assertEqual(account_name('138 ＊＊＊＊ 0001'),'138****0001')
