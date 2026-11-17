import main
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from garden.vision import VisionDriver
from garden.core import Observation


class LoginStageTests(unittest.TestCase):
    def driver(self):
        driver = object.__new__(VisionDriver)
        driver.profile = {'cn_login':True}
        driver.control = SimpleNamespace(wait=lambda t:None)
        driver.window = SimpleNamespace(account_control=lambda:123,select_saved_account=Mock(),
            selected_saved_account=lambda:'138****0001')
        driver.recover_login = lambda:True
        driver.act = Mock()
        driver.submit_account_login = Mock()
        driver.wait_identity = lambda:'123456789'
        driver.login_view = SimpleNamespace(selected='138****0001')
        driver.observe = lambda:Observation('login',{})
        return driver

    def test_selection_is_verified_before_login(self):
        driver = self.driver()
        self.assertEqual(driver.login('138****0001'),'123456789')
        driver.window.select_saved_account.assert_called_once_with('138****0001')
        driver.submit_account_login.assert_called_once_with('138****0001')

    def test_display_mismatch_prevents_login(self):
        driver = self.driver()
        with self.assertRaises(RuntimeError):
            driver.login('138****0002')
        self.assertNotIn(unittest.mock.call('login'),driver.act.call_args_list)

    def test_native_selection_allows_stale_painted_label(self):
        driver = self.driver()
        driver.login_view.selected = '138****9999'
        self.assertEqual(driver.login('138****0001'),'123456789')
        driver.submit_account_login.assert_called_once_with('138****0001')

    def test_unchanged_login_retries_dialog_then_stops(self):
        driver = self.driver()
        del driver.submit_account_login
        driver.frame = SimpleNamespace(size=(2560,1440))
        driver.login_view.targets = {'login':(.5,.55)}
        driver.window.click = Mock()
        driver.window.click_login_dialog = Mock()
        with self.assertRaises(RuntimeError):
            driver.submit_account_login('138****0001')
        self.assertEqual(driver.window.click.call_count,1)
        self.assertEqual(driver.window.click_login_dialog.call_count,2)

    def test_login_transition_stops_further_clicks(self):
        driver = self.driver()
        del driver.submit_account_login
        driver.frame = SimpleNamespace(size=(2560,1440))
        driver.login_view.targets = {'login':(.5,.55)}
        driver.window.click = Mock()
        driver.window.click_login_dialog = Mock()
        driver.observe = Mock(side_effect=[Observation('login',{}),Observation('connected_title',{})])
        driver.submit_account_login('138****0001')
        driver.window.click.assert_called_once()
        driver.window.click_login_dialog.assert_not_called()

    def test_three_consistent_uid_reads_required(self):
        driver = self.driver()
        del driver.wait_identity
        driver.frame = SimpleNamespace(size=(1920,1080))
        driver.observe = lambda:Observation('unknown',{})
        driver.texts = Mock(side_effect=[
            [('UID: 123456789',.99,(1900,1060))], [],
            [('UID: 123456789',.99,(1900,1060))],
            [('UID: 123456789',.99,(1900,1060))],
            [('UID: 123456789',.99,(1900,1060))]])
        self.assertEqual(driver.wait_identity(),'123456789')
        self.assertEqual(driver.texts.call_count,5)
