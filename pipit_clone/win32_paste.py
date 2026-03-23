"""
Windows helpers: restore foreground window and inject Ctrl+V reliably for global paste.
"""
from __future__ import annotations

import ctypes
import time

user32 = ctypes.windll.user32

ASFW_ANY = 0xFFFFFFFF  # Allow any process to set foreground (best-effort)

# https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002


def get_foreground_hwnd() -> int:
    return int(user32.GetForegroundWindow())


def is_window(hwnd: int) -> bool:
    if not hwnd:
        return False
    return bool(user32.IsWindow(hwnd))


def allow_set_foreground_any() -> None:
    try:
        user32.AllowSetForegroundWindow(ASFW_ANY)
    except Exception:
        pass


def set_foreground_hwnd(hwnd: int) -> bool:
    if not hwnd:
        return False
    allow_set_foreground_any()
    # Small flash workaround: some apps need the thread to attach (optional)
    ok = bool(user32.SetForegroundWindow(hwnd))
    if ok:
        time.sleep(0.05)
    return ok


def send_ctrl_v_keybd_event() -> None:
    """Legacy keybd_event — widely compatible for synthetic Ctrl+V."""
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
