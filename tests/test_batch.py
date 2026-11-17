import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from garden.core import Runner, Store, Halt


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'history.db')
        self.driver=Mock()
        self.driver.read_accounts.return_value=['a','b']
        self.driver.account_list_complete=True
        self.driver.login.side_effect=['100000001','100000002']
        self.driver.run_garden.return_value='游历值已满，领取点击已执行，并返回登录页'
        self.driver.recover_login.return_value=True
        self.runner=Runner(self.driver,self.store,Mock(),Mock())

    def test_two_accounts_login_guide_garden_return_in_order(self):
        self.assertEqual(self.runner.run_batch(),{'a':'已完成','b':'已完成'})
        names=[call[0] for call in self.driver.mock_calls]
        self.assertEqual(names,['read_accounts','login','collect_weekly_entry','run_garden','recover_login',
                                'login','collect_weekly_entry','run_garden','recover_login'])
        self.assertEqual([r[2] for r in self.store.history()].count('已完成'),2)

    def test_only_enabled_account_is_processed(self):
        self.runner.run_batch(['b'])
        self.driver.login.assert_called_once_with('b')

    def test_incomplete_or_changed_list_blocks_before_login(self):
        self.driver.account_list_complete=False
        with self.assertRaises(RuntimeError): self.runner.run_batch()
        self.driver.account_list_complete=True
        with self.assertRaises(RuntimeError): self.runner.run_batch(['missing'])
        self.driver.login.assert_not_called()

    def test_failure_in_game_stops_before_next_account(self):
        self.driver.run_garden.side_effect=RuntimeError('页面未识别')
        self.driver.recover_login.return_value=False
        with self.assertRaisesRegex(RuntimeError,'批次停止'): self.runner.run_batch()
        self.driver.login.assert_called_once_with('a')
        self.assertNotIn('已完成',[r[2] for r in self.store.history()])

    def test_stop_does_not_switch_account(self):
        self.driver.run_garden.side_effect=Halt()
        with self.assertRaises(Halt): self.runner.run_batch()
        self.driver.login.assert_called_once_with('a')
        self.driver.recover_login.assert_not_called()

    def test_identity_mismatch_never_runs_garden(self):
        self.store.bind('a','999999999')
        self.runner.run_batch(['a'])
        self.driver.collect_weekly_entry.assert_not_called()
        self.driver.run_garden.assert_not_called()
        self.assertEqual(self.store.history()[0][2],'失败')
