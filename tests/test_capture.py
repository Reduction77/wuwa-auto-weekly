import main  # project-local imaging dependencies
import threading
import time
import unittest
import numpy as np
from garden.windows import Window


class CaptureTests(unittest.TestCase):
    def static_window(self):
        window = object.__new__(Window)
        window.hwnd = 1
        window._capture = object()
        window._frame_lock = threading.Condition()
        window._latest = np.full((8,8,4),128,dtype=np.uint8)
        window._frame_at = time.monotonic()
        window._closed = False
        window.check = lambda:None
        window.size = lambda:(8,8)
        window._popups = {}
        return window

    def test_static_frame_does_not_require_second_event(self):
        window = self.static_window()
        started = time.monotonic()
        for _ in range(3):
            self.assertEqual(window.capture(include_owned=False).size,(8,8))
        self.assertLess(time.monotonic()-started,2)

    def test_closed_session_not_served_from_cache(self):
        window = self.static_window()
        window._closed = True
        with self.assertRaises(RuntimeError):
            window.capture(include_owned=False)

    def test_input_invalidates_popup_and_main(self):
        window = self.static_window()
        popup = self.static_window()
        window._popups[2] = popup
        window.invalidate_frames()
        self.assertFalse(hasattr(window,'_capture'))
        self.assertFalse(hasattr(popup,'_capture'))
