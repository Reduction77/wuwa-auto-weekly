import ctypes
import unittest
from unittest.mock import Mock, patch
from garden.windows import Window


class AccountControlTests(unittest.TestCase):
    def window(self, labels):
        window = object.__new__(Window)
        window.account_control = lambda:123
        def message(hwnd, command, index=0, value=0):
            if command == 0x146: return len(labels)
            if command == 0x149: return len(labels[index])
            if command == 0x148:
                buf = ctypes.create_unicode_buffer(labels[index])
                ctypes.memmove(value,buf,ctypes.sizeof(buf))
                return len(labels[index])
            self.fail('unexpected message, native reading must not mutate selection')
        window.control_message = message
        return window

    def test_complete_list_without_expanding_dropdown(self):
        labels = ['138****0001','138****0002']
        self.assertEqual(self.window(labels).saved_accounts(),labels)

    def test_duplicate_masked_accounts_rejected(self):
        with self.assertRaises(RuntimeError):
            self.window(['138****0001','138****0001']).saved_accounts()

    def test_non_account_control_rejected(self):
        with self.assertRaises(RuntimeError):
            self.window(['其他登录方式']).saved_accounts()

    def test_selection_notifies_parent_without_cancelling_dropdown(self):
        window = object.__new__(Window)
        window.account_control = lambda:123
        window.saved_accounts = lambda:['138****0001','138****0002']
        window.invalidate_frames = Mock()
        selected = 0
        sent = []
        def message(hwnd, command, index=0, value=0):
            nonlocal selected
            sent.append((hwnd,command,index,value))
            if command == 0x14e:
                selected = index
                return index
            if command == 0x147: return selected
            if command == 0x14f:
                selected = 0  # SDK cancel restores the old account
            return 0
        window.control_message = message
        with patch('garden.windows.u.GetParent',return_value=456), \
             patch('garden.windows.u.GetDlgCtrlID',return_value=77):
            window.select_saved_account('138****0002')
        self.assertEqual(selected,1)
        self.assertIn((456,0x111,(1<<16)|77,123),sent)
        self.assertNotIn(0x14f,[row[1] for row in sent])
        window.invalidate_frames.assert_called_once()

    def test_open_list_closes_before_setting_target(self):
        window = object.__new__(Window)
        window.account_control = lambda:123
        window.saved_accounts = lambda:['138****0001','138****0002']
        window.invalidate_frames = Mock()
        selected = 0
        commands = []
        def message(hwnd, command, index=0, value=0):
            nonlocal selected
            commands.append(command)
            if command == 0x157: return 1
            if command == 0x14f: selected = 0
            if command == 0x14e: selected = index
            if command in (0x14e,0x147): return selected
            return 0
        window.control_message = message
        with patch('garden.windows.u.GetParent',return_value=456), \
             patch('garden.windows.u.GetDlgCtrlID',return_value=77):
            window.select_saved_account('138****0002')
        self.assertLess(commands.index(0x14f),commands.index(0x14e))
        self.assertEqual(window.selected_saved_account(),'138****0002')
