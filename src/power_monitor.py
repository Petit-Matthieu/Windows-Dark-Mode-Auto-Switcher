r"""Windows power/display event monitoring.

Creates a hidden message-only window that receives:
- WM_POWERBROADCAST: sleep/resume events
- WM_DISPLAYCHANGE / session events: screen on/off

Uses ctypes to avoid heavy dependencies. Runs in a daemon thread with
its own Windows message loop.
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ── Windows constants ──
WM_POWERBROADCAST = 0x0218
WM_SESSION_CHANGE = 0x0021
PBT_APMRESUMEAUTOMATIC = 0x0012
PBT_APMRESUMESUSPEND = 0x0007
PBT_APMRESUMESTANDBY = 0x0008
PBT_APMSUSPEND = 0x0004
HWND_MESSAGE = -3

# Session change types
WTS_SESSION_UNLOCK = 0x8

# GUID_MONITOR_POWER_ON = {02717039-...}
# We register for this to get display on/off notifications
GUID_MONITOR_POWER_ON = bytes([
    0x39, 0x70, 0x71, 0x02, 0x71, 0x02, 0x82, 0x46,
    0x8E, 0x01, 0x02, 0x4D, 0xA1, 0x16, 0x3C, 0x51,
])

# RegisterPowerSettingNotification flags
DEVICE_NOTIFY_WINDOW_HANDLE = 0x00000000

# ── ctypes definitions ──
WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, wintypes.HWND, wintypes.UINT,
    wintypes.WPARAM, wintypes.LPARAM,
)


class WNDCLASSEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HWND),
        ("hIcon", wintypes.HWND),
        ("hCursor", wintypes.HWND),
        ("hbrBackground", wintypes.HWND),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HWND),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class POWERBROADCAST_SETTING(ctypes.Structure):
    _fields_ = [
        ("PowerSetting", GUID),
        ("DataLength", wintypes.DWORD),
        ("Data", wintypes.DWORD),
    ]


# ── Win32 API functions ──
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
    wintypes.DWORD, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, wintypes.HWND,
    wintypes.HWND, wintypes.HWND, wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND

user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEX)]
user32.RegisterClassExW.restype = wintypes.ATOM

user32.DefWindowProcW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
]
user32.DefWindowProcW.restype = ctypes.c_long

user32.GetMessageW.argtypes = [
    ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
]
user32.GetMessageW.restype = wintypes.BOOL

user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = ctypes.c_long

user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
]
user32.PostThreadMessageW.restype = wintypes.BOOL

user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL

user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HWND]
user32.UnregisterClassW.restype = wintypes.BOOL

user32.RegisterPowerSettingNotification.argtypes = [
    wintypes.HWND, ctypes.POINTER(GUID), wintypes.DWORD,
]
user32.RegisterPowerSettingNotification.restype = wintypes.HWND

kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

WM_QUIT = 0x0012


class PowerMonitor(object):
    """Monitor Windows power/display events in a background thread.

    Events detected:
    - System resume from sleep/hibernate (WM_POWERBROADCAST)
    - Display on/off (RegisterPowerSettingNotification + GUID_MONITOR_POWER_ON)
    - Session unlock / screen unlock (WM_SESSION_CHANGE + WTS_SESSION_UNLOCK)

    When any of these events fires, the provided callback is invoked.
    """

    CLASS_NAME = "DarkModePowerMonitor"

    def __init__(self, on_resume=None):
        # type: (Optional[Callable[[], None]]) -> None
        self._on_resume = on_resume
        self._thread = None  # type: Optional[threading.Thread]
        self._running = False
        self._thread_id = 0
        self._hwnd = 0

    def start(self):
        # type: () -> None
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Power monitor started")

    def stop(self):
        # type: () -> None
        self._running = False
        if self._thread_id:
            try:
                user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        logger.info("Power monitor stopped")

    def _fire_callback(self, reason):
        # type: (str) -> None
        if self._on_resume:
            try:
                logger.info("Power event: %s", reason)
                self._on_resume()
            except Exception:
                logger.exception("Power callback failed (%s)", reason)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        # type: (int, int, int, int) -> int
        if msg == WM_POWERBROADCAST:
            if wparam in (PBT_APMRESUMEAUTOMATIC, PBT_APMRESUMESUSPEND,
                          PBT_APMRESUMESTANDBY):
                self._fire_callback("resume from sleep")
            elif wparam == PBT_APMSUSPEND:
                logger.info("System entering sleep")

            # Check for display power change via POWERBROADCAST_SETTING
            if lparam and wparam == 0x8000:  # PBT_POWERSETTINGCHANGE
                try:
                    pbs = ctypes.cast(
                        lparam, ctypes.POINTER(POWERBROADCAST_SETTING)
                    ).contents
                    # Data = 0 means display OFF, Data = 1 means display ON
                    display_on = pbs.Data
                    if display_on:
                        self._fire_callback("display on")
                except Exception:
                    pass

        elif msg == WM_SESSION_CHANGE:
            if wparam == WTS_SESSION_UNLOCK:
                self._fire_callback("session unlock")

        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run(self):
        # type: () -> None
        self._thread_id = kernel32.GetCurrentThreadId()

        wnd_proc_callback = WNDPROC(self._wnd_proc)

        wc = WNDCLASSEX()
        wc.cbSize = ctypes.sizeof(WNDCLASSEX)
        wc.lpfnWndProc = wnd_proc_callback
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = self.CLASS_NAME

        atom = user32.RegisterClassExW(ctypes.byref(wc))
        if not atom:
            logger.error("Failed to register window class: %s",
                         ctypes.FormatError())
            self._running = False
            return

        hwnd = user32.CreateWindowExW(
            0, self.CLASS_NAME, "PowerMonitor", 0,
            0, 0, 0, 0, HWND_MESSAGE, None, wc.hInstance, None,
        )

        if not hwnd:
            logger.error("Failed to create message window: %s",
                         ctypes.FormatError())
            user32.UnregisterClassW(self.CLASS_NAME, wc.hInstance)
            self._running = False
            return

        self._hwnd = hwnd

        # Register for display power state changes (GUID_MONITOR_POWER_ON)
        try:
            guid = GUID()
            guid.Data1 = 0x02717039
            guid.Data2 = 0x0271
            guid.Data3 = 0x4682
            guid.Data4 = (ctypes.c_ubyte * 8)(
                0x8E, 0x01, 0x02, 0x4D, 0xA1, 0x16, 0x3C, 0x51
            )
            user32.RegisterPowerSettingNotification(
                hwnd, ctypes.byref(guid), DEVICE_NOTIFY_WINDOW_HANDLE
            )
            logger.debug("Registered for display power notifications")
        except Exception as e:
            logger.debug("Could not register display power: %s", e)

        # Message loop
        msg = MSG()
        while self._running:
            ret = user32.GetMessageW(ctypes.byref(msg), hwnd, 0, 0)
            if ret == 0 or ret == -1:
                break
            user32.DispatchMessageW(ctypes.byref(msg))

        user32.DestroyWindow(hwnd)
        user32.UnregisterClassW(self.CLASS_NAME, wc.hInstance)
        self._running = False
