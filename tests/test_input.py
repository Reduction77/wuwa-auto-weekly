import unittest
from unittest.mock import patch
from garden.windows import Window


class MessageTests(unittest.TestCase):
    def test_background_sequence_and_same_target(self):
        window = object.__new__(Window)
        window.hwnd = 100
        window._popups = {}
        sent = []
        window.size = lambda:(2560,1440)
        window.input_target = lambda x,y:(101,30,40)
        window.post = lambda *args:sent.append(args)
        with patch('garden.windows.time.sleep'):
            window.click(2400,790)
        self.assertEqual([args[0] for args in sent],[0x6,0x6,0x200,0x201,0x202])
        self.assertEqual([args[3] for args in sent[2:]],[101,101,101])
        self.assertEqual(len(set(args[2] for args in sent[2:])),1)

    def test_releases_after_down_failure(self):
        window = object.__new__(Window)
        window.hwnd = 100
        window._popups = {}
        sent = []
        window.size = lambda:(2560,1440)
        window.input_target = lambda x,y:(100,x,y)
        def post(*args):
            sent.append(args[0])
            if args[0] == 0x201:
                raise RuntimeError('test failure')
        window.post = post
        with patch('garden.windows.time.sleep'),self.assertRaises(RuntimeError):
            window.click(2400,790)
        self.assertEqual(sent[-1],0x202)
