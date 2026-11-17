import ctypes as C
import threading
import time
from ctypes import wintypes as W

u = C.WinDLL('user32', use_last_error=True)
g = C.WinDLL('gdi32', use_last_error=True)
k = C.WinDLL('kernel32', use_last_error=True)
k.OpenProcess.argtypes = [W.DWORD,W.BOOL,W.DWORD]
k.OpenProcess.restype = W.HANDLE
k.QueryFullProcessImageNameW.argtypes = [W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]
k.CloseHandle.argtypes = [W.HANDLE]


def process_name(hwnd):
    pid = W.DWORD()
    u.GetWindowThreadProcessId(hwnd,C.byref(pid))
    handle = k.OpenProcess(0x1000,False,pid.value)
    if not handle:
        return ''
    try:
        size = W.DWORD(2048)
        path = C.create_unicode_buffer(size.value)
        if k.QueryFullProcessImageNameW(handle,0,path,C.byref(size)):
            return path.value.replace('\\','/').rsplit('/',1)[-1].lower()
        return ''
    finally:
        k.CloseHandle(handle)
for lib, name, args, result in [
    (u, 'GetParent', [W.HWND], W.HWND),
    (u, 'GetDlgCtrlID', [W.HWND], C.c_int),
    (u, 'GetClassNameW', [W.HWND,W.LPWSTR,C.c_int], C.c_int),
    (u, 'SendMessageTimeoutW', [W.HWND,W.UINT,W.WPARAM,W.LPARAM,W.UINT,W.UINT,C.POINTER(C.c_size_t)], W.LPARAM),
    (u, 'GetWindow', [W.HWND,W.UINT], W.HWND),
    (u, 'GetWindowRect', [W.HWND,C.POINTER(W.RECT)], W.BOOL),
    (u, 'GetForegroundWindow', [], W.HWND),
    (u, 'GetWindowThreadProcessId', [W.HWND,C.POINTER(W.DWORD)], W.DWORD),
    (u, 'GetClientRect', [W.HWND,C.POINTER(W.RECT)], W.BOOL),
    (u, 'ClientToScreen', [W.HWND,C.POINTER(W.POINT)], W.BOOL),
    (u, 'ScreenToClient', [W.HWND,C.POINTER(W.POINT)], W.BOOL),
    (u, 'ChildWindowFromPointEx', [W.HWND,W.POINT,W.UINT], W.HWND),
    (u, 'IsWindow', [W.HWND], W.BOOL),
    (u, 'IsWindowVisible', [W.HWND], W.BOOL),
    (u, 'IsIconic', [W.HWND], W.BOOL),
    (u, 'GetDC', [W.HWND], W.HDC), (u, 'ReleaseDC', [W.HWND, W.HDC], C.c_int),
    (u, 'PrintWindow', [W.HWND,W.HDC,W.UINT], W.BOOL),
    (u, 'PostMessageW', [W.HWND,W.UINT,W.WPARAM,W.LPARAM], W.BOOL),
    (g, 'CreateCompatibleDC', [W.HDC], W.HDC),
    (g, 'CreateCompatibleBitmap', [W.HDC,C.c_int,C.c_int], W.HBITMAP),
    (g, 'SelectObject', [W.HDC,W.HANDLE], W.HANDLE),
    (g, 'DeleteObject', [W.HANDLE], W.BOOL), (g, 'DeleteDC', [W.HDC], W.BOOL),
    (g, 'GetDIBits', [W.HDC,W.HBITMAP,W.UINT,W.UINT,C.c_void_p,C.c_void_p,W.UINT], C.c_int),
]:
    fn = getattr(lib, name)
    fn.argtypes, fn.restype = args, result


class Header(C.Structure):
    _fields_ = [('size',W.DWORD),('width',W.LONG),('height',W.LONG),('planes',W.WORD),
                ('bits',W.WORD),('compression',W.DWORD),('image_size',W.DWORD),
                ('x',W.LONG),('y',W.LONG),('used',W.DWORD),('important',W.DWORD)]


def windows():
    found = []
    callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    @callback
    def collect(hwnd, _):
        text = C.create_unicode_buffer(512)
        u.GetWindowTextW(hwnd, text, 512)
        if (u.IsWindowVisible(hwnd) and any(s in text.value.lower() for s in ['鸣潮','wuthering'])
                and process_name(hwnd) in {'client-win64-shipping.exe','wuthering waves.exe'}):
            found.append((hwnd, text.value))
        return True
    u.EnumWindows(collect, 0)
    return found


class Window:
    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.pid = W.DWORD()
        u.GetWindowThreadProcessId(hwnd, C.byref(self.pid))
        self._popups = {}

    def owned_windows(self):
        found = []
        callback = C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
        @callback
        def visit(hwnd, _):
            if hwnd == self.hwnd or not u.IsWindowVisible(hwnd):
                return True
            pid = W.DWORD()
            u.GetWindowThreadProcessId(hwnd,C.byref(pid))
            if pid.value != self.pid.value:
                return True
            owner = u.GetWindow(hwnd,4)
            seen = set()
            while owner and owner not in seen:
                if owner == self.hwnd:
                    found.append(hwnd)
                    break
                seen.add(owner)
                owner = u.GetWindow(owner,4)
            return True
        u.EnumWindows(visit,0)
        return found  # topmost first, as returned by EnumWindows

    def check(self):
        pid = W.DWORD()
        u.GetWindowThreadProcessId(self.hwnd, C.byref(pid))
        if not u.IsWindow(self.hwnd) or pid.value != self.pid.value:
            raise RuntimeError('游戏窗口已失效')
        if u.IsIconic(self.hwnd):
            raise RuntimeError('游戏已最小化，请恢复窗口')

    def account_control(self):
        candidates = set()
        callback = C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
        @callback
        def visit(hwnd, _):
            if not u.IsWindowVisible(hwnd):
                return True
            name = C.create_unicode_buffer(128)
            u.GetClassNameW(hwnd,name,len(name))
            if name.value == 'ComboBox':
                pid = W.DWORD()
                u.GetWindowThreadProcessId(hwnd,C.byref(pid))
                if pid.value == self.pid.value:
                    candidates.add(hwnd)
            return True
        self.check()
        for hwnd in self.owned_windows():
            u.EnumChildWindows(hwnd,visit,0)
        if len(candidates) > 1:
            raise RuntimeError('存在多个可见账号控件，停止读取以避免选错')
        return next(iter(candidates),None)

    def control_message(self, hwnd, message, index=0, value=0):
        result = C.c_size_t()
        C.set_last_error(0)
        if not u.SendMessageTimeoutW(hwnd,message,index,value,2,1500,C.byref(result)):
            raise RuntimeError(f'读取账号控件失败（Windows 错误 {C.get_last_error()}），请确认助手以管理员身份运行')
        return C.c_ssize_t(result.value).value

    def saved_accounts(self):
        """Read native SDK entries without opening, selecting or deleting rows."""
        from .cn_login import account_name
        hwnd = self.account_control()
        if hwnd is None:
            return None
        count = self.control_message(hwnd,0x146)
        if not 1 <= count <= 100:
            raise RuntimeError('账号控件数量无效或超过上限')
        labels = []
        for index in range(count):
            length = self.control_message(hwnd,0x149,index)
            if not 0 < length <= 256:
                raise RuntimeError('账号条目长度无效')
            buffer = C.create_unicode_buffer(length+1)
            copied = self.control_message(hwnd,0x148,index,C.addressof(buffer))
            label = account_name(buffer.value)
            if copied < 0 or not label:
                raise RuntimeError('账号控件包含无法确认的账号格式')
            labels.append(label)
        if len(labels) != len(set(labels)):
            raise RuntimeError('存在相同脱敏账号，需结合 UID 进一步区分')
        if self.control_message(hwnd,0x146) != count:
            raise RuntimeError('读取过程中账号列表发生变化')
        return labels

    def select_saved_account(self, account):
        labels = self.saved_accounts()
        if labels is None or labels.count(account) != 1:
            raise RuntimeError('目标账号不在唯一可确认的登录列表中')
        hwnd = self.account_control()
        index = labels.index(account)
        # Close an existing list BEFORE selecting: cancellation may restore the
        # previous item, so selection and notification must follow the close.
        if self.control_message(hwnd,0x157):  # CB_GETDROPPEDSTATE
            self.control_message(hwnd,0x14f,0)
        # Standard ComboBox protocol; notify its parent so the SDK updates its
        # own login state, not just the painted selected row.
        if self.control_message(hwnd,0x14e,index) != index:
            raise RuntimeError('账号控件未接受选择')
        parent = u.GetParent(hwnd)
        if not parent:
            raise RuntimeError('账号控件没有所属登录窗口')
        control_id = u.GetDlgCtrlID(hwnd)
        self.control_message(parent,0x111,(1 << 16) | (control_id & 0xffff),hwnd)
        # Do not send CB_SHOWDROPDOWN(FALSE) after committing. Closing an SDK
        # dropdown can restore its previous selection via the cancel handler.
        self.invalidate_frames()
        if self.control_message(hwnd,0x147) != index or self.saved_accounts() != labels:
            raise RuntimeError('账号选择后的控件校验不一致')

    def selected_saved_account(self):
        labels = self.saved_accounts()
        hwnd = self.account_control()
        if not labels or not hwnd:
            return None
        index = self.control_message(hwnd,0x147)
        return labels[index] if 0 <= index < len(labels) else None

    def click_login_dialog(self, x, y):
        # SDK artwork can be a Static child; mouse messages sent to that child
        # do not necessarily reach the dialog's button handler.
        combo = self.account_control()
        parent = u.GetParent(combo) if combo else None
        if not parent:
            raise RuntimeError('登录窗口已消失，停止点击')
        point = W.POINT(int(x),int(y))
        if not u.ClientToScreen(self.hwnd,C.byref(point)) or not u.ScreenToClient(parent,C.byref(point)):
            raise RuntimeError('无法转换登录按钮坐标')
        rect = W.RECT()
        u.GetClientRect(parent,C.byref(rect))
        if not 0 <= point.x < rect.right or not 0 <= point.y < rect.bottom:
            raise RuntimeError('登录按钮不在账号窗口内')
        self.click(x,y,target_point=(parent,point.x,point.y))

    def size(self):
        self.check()
        r = W.RECT()
        u.GetClientRect(self.hwnd, C.byref(r))
        return r.right, r.bottom

    def capture(self, include_owned=True):
        from windows_capture import WindowsCapture
        from PIL import Image
        self.check()
        # WGC is change-driven: a static dialog may deliver only one frame.
        # Reuse a live session's frame briefly; periodically re-open the session
        # to avoid treating an old image as indefinitely authoritative.
        if (hasattr(self, '_capture') and self._latest is not None
                and time.monotonic() - self._frame_at > 5):
            self.reset_capture()
        if not hasattr(self, '_capture'):
            self._frame_lock = threading.Condition()
            self._latest = None
            self._frame_number = 0
            self._frame_at = 0
            self._closed = False
            self._capture = WindowsCapture(window_hwnd=self.hwnd, cursor_capture=False,
                                           minimum_update_interval=100)
            @self._capture.event
            def on_frame_arrived(frame, control):
                with self._frame_lock:
                    self._latest = frame.frame_buffer.copy()
                    self._frame_number += 1
                    self._frame_at = time.monotonic()
                    self._frame_lock.notify_all()
            @self._capture.event
            def on_closed():
                with self._frame_lock:
                    self._closed = True
                    self._frame_lock.notify_all()
            self._capture_control = self._capture.start_free_threaded()
        with self._frame_lock:
            if not self._frame_lock.wait_for(lambda: self._latest is not None or self._closed,timeout=8):
                raise RuntimeError(f'后台截图超时，窗口 {self.hwnd} 没有提供首帧')
            if self._closed:
                raise RuntimeError('后台截图会话已关闭')
            data = self._latest.copy()
        image = Image.fromarray(data[:,:,2::-1])
        w,h = self.size()
        if image.size != (w,h):
            # WGC includes non-client borders; map client origin from DWM frame bounds.
            rect = W.RECT()
            dwm = C.WinDLL('dwmapi')
            dwm.DwmGetWindowAttribute.argtypes = [W.HWND,W.DWORD,C.c_void_p,W.DWORD]
            if dwm.DwmGetWindowAttribute(self.hwnd,9,C.byref(rect),C.sizeof(rect)) != 0:
                raise RuntimeError('无法映射截图与客户区坐标')
            point = W.POINT(0,0)
            u.ClientToScreen(self.hwnd,C.byref(point))
            x,y = point.x-rect.left,point.y-rect.top
            if x<0 or y<0 or x+w>image.width or y+h>image.height:
                raise RuntimeError('截图坐标与游戏客户区不一致')
            image = image.crop((x,y,x+w,y+h))
        if include_owned:
            origin = W.POINT(0,0)
            u.ClientToScreen(self.hwnd,C.byref(origin))
            owned = self.owned_windows()
            for hwnd in list(self._popups):
                if hwnd not in owned:
                    self._popups.pop(hwnd).close()
            for hwnd in reversed(owned):
                r = W.RECT()
                u.GetClientRect(hwnd,C.byref(r))
                # Fullscreen owner is a transparent SDK host, not the dialog.
                if r.right >= w and r.bottom >= h:
                    continue
                if r.right < 100 or r.bottom < 100:
                    continue
                point = W.POINT(0,0)
                u.ClientToScreen(hwnd,C.byref(point))
                x,y = point.x-origin.x, point.y-origin.y
                if x < 0 or y < 0 or x+r.right>w or y+r.bottom>h:
                    raise RuntimeError('登录弹窗超出游戏客户区，无法可靠映射')
                if hwnd not in self._popups:
                    self._popups[hwnd] = Window(hwnd)
                popup = self._popups[hwnd].capture(include_owned=False)
                image.paste(popup,(x,y))
        return image

    def close(self):
        for popup in self._popups.values():
            popup.close()
        self._popups.clear()
        self.reset_capture()

    def reset_capture(self):
        if hasattr(self,'_capture_control'):
            self._capture_control.stop()
            del self._capture_control
        if hasattr(self,'_capture'):
            del self._capture

    def invalidate_frames(self):
        # Input must be verified against newly acquired frames, including SDK
        # popups; a cached pre-click frame cannot confirm an action's result.
        for popup in self._popups.values():
            popup.reset_capture()
        self.reset_capture()

    def capture_printwindow(self):
        from PIL import Image, ImageStat
        w, h = self.size()
        if w < 640 or h < 360:
            raise RuntimeError('游戏客户区尺寸过小')
        dc = u.GetDC(self.hwnd)
        mem = g.CreateCompatibleDC(dc)
        bitmap = g.CreateCompatibleBitmap(dc, w, h)
        old = g.SelectObject(mem, bitmap)
        try:
            if not u.PrintWindow(self.hwnd, mem, 3):
                raise RuntimeError('后台截图失败')
            g.SelectObject(mem, old)
            header = Header(C.sizeof(Header), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
            buf = C.create_string_buffer(w*h*4)
            if not g.GetDIBits(mem, bitmap, 0, h, buf, C.byref(header), 0):
                raise RuntimeError('无法读取截图')
            image = Image.frombuffer('RGB', (w,h), buf.raw, 'raw', 'BGRX', 0, 1)
            if max(ImageStat.Stat(image).stddev) < 2:
                raise RuntimeError('截图为空白：当前客户端不支持此截图路径')
            return image
        finally:
            g.SelectObject(mem, old)
            g.DeleteObject(bitmap)
            g.DeleteDC(mem)
            u.ReleaseDC(self.hwnd, dc)

    def post(self, message, key=0, value=0, target=None):
        self.check()
        if not u.PostMessageW(target or self.hwnd, message, key, value):
            code = C.get_last_error()
            if code == 5:
                raise RuntimeError('后台输入被拒绝（Windows 错误 5）：游戏权限高于助手，请以管理员身份运行助手后重试')
            raise RuntimeError(f'后台输入被系统拒绝（Windows 错误 {code}）')

    def click(self, x, y, target_point=None):
        w,h = self.size()
        if not 0 <= x < w or not 0 <= y < h:
            raise RuntimeError('点击坐标越界')
        target, local_x, local_y = target_point or self.input_target(int(x),int(y))
        pos = (local_x & 0xffff) | ((local_y & 0xffff) << 16)
        self.last_input = {'method':'window_messages_v2','client_point':[int(x),int(y)],
                           'target':int(target),'target_point':[local_x,local_y],
                           'foreground_before':u.GetForegroundWindow()}
        # Notify the message consumer of activation; never raise the real window
        # or move the system pointer. Some game UI handlers ignore inactive messages.
        self.post(0x6, 1, 0)
        if target != self.hwnd:
            self.post(0x6, 1, 0, target)
        time.sleep(.08)
        self.post(0x200, 0, pos, target)
        time.sleep(.08)
        try:
            self.post(0x201, 1, pos, target)
            time.sleep(.08)
        finally:
            self.post(0x202, 0, pos, target)
            self.last_input['foreground_after'] = u.GetForegroundWindow()
            self.invalidate_frames()

    def input_target(self, x, y):
        target = self.hwnd
        screen = W.POINT(x,y)
        if not u.ClientToScreen(target,C.byref(screen)):
            raise RuntimeError('无法转换客户区坐标')
        for hwnd in self.owned_windows():
            rect = W.RECT()
            u.GetWindowRect(hwnd,C.byref(rect))
            if rect.left <= screen.x < rect.right and rect.top <= screen.y < rect.bottom:
                target = hwnd
                break
        for _ in range(12):
            point = W.POINT(screen.x,screen.y)
            if not u.ScreenToClient(target,C.byref(point)):
                raise RuntimeError('无法转换输入目标坐标')
            child = u.ChildWindowFromPointEx(target,point,7)
            if not child or child == target:
                return target,point.x,point.y
            pid = W.DWORD()
            u.GetWindowThreadProcessId(child,C.byref(pid))
            if pid.value != self.pid.value:
                raise RuntimeError('点击目标不属于游戏进程')
            target = child
        raise RuntimeError('输入窗口层级异常')

    def key(self, vk):
        scan = u.MapVirtualKeyW(vk, 0)
        self.post(0x6,1,0)
        try:
            self.post(0x100, vk, 1 | scan << 16)
            time.sleep(.06)
        finally:
            self.post(0x101, vk, 1 | scan << 16 | 3 << 30)
            self.invalidate_frames()
