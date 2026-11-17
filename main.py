import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if sys.prefix == sys.base_prefix:
    sys.path.insert(0, str(ROOT / '.deps'))

if __name__ == '__main__':
    import ctypes
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    from garden.ui import App
    App(ROOT).mainloop()
