# -*- coding: utf-8 -*-
"""Find + focus the Helldivers 2 top-level window by process id.

windowTitle matching fails on this build (the title carries U+2122 and the
window class name is reported inconsistently), and Get-Process's
MainWindowHandle is often 0 while the game is loading. EnumWindows + pid is the
only reliable route, and every injected key must be focused first - an
unfocused SendKeys goes to whatever window the user is looking at.

    python hd2_window.py            # print handle + foreground state
    python hd2_window.py focus      # restore + focus, then verify
"""
import ctypes
import sys
import time
from ctypes import wintypes

try:                       # the game title carries U+2122; the console is GBK
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:          # noqa: BLE001
    pass

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
SW_RESTORE = 9


def game_pid():
    import ctypes.wintypes as wt
    TH32CS_SNAPPROCESS = 0x00000002

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [('dwSize', wt.DWORD), ('cntUsage', wt.DWORD), ('th32ProcessID', wt.DWORD),
                    ('th32DefaultHeapID', ctypes.POINTER(ctypes.c_ulong)),
                    ('th32ModuleID', wt.DWORD), ('cntThreads', wt.DWORD),
                    ('th32ParentProcessID', wt.DWORD), ('pcPriClassBase', ctypes.c_long),
                    ('dwFlags', wt.DWORD), ('szExeFile', ctypes.c_char * 260)]

    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    found = []
    if kernel32.Process32First(snap, ctypes.byref(entry)):
        while True:
            if entry.szExeFile.decode('ascii', 'ignore').lower() == 'helldivers2.exe':
                found.append(entry.th32ProcessID)
            if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                break
    kernel32.CloseHandle(snap)
    return found


def windows_of(pid):
    out = []

    def callback(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            title = ctypes.create_unicode_buffer(256)
            klass = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title, 256)
            user32.GetClassNameW(hwnd, klass, 256)
            out.append((hwnd, bool(user32.IsWindowVisible(hwnd)), title.value, klass.value))
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return out


def game_window(pid=None):
    """The game's visible top-level window handle, or None.

    Preference order, because neither signal is reliable alone on every build:
      1. a visible window whose CLASS contains "stingray"
      2. a visible window whose TITLE contains "stingray"
      3. the first visible window of the process
    """
    if pid is None:
        pids = game_pid()
        if not pids:
            return None
        pid = pids[0]
    wins = [w for w in windows_of(pid) if w[1]]
    for hwnd, _v, _title, klass in wins:
        if 'stingray' in klass.lower():
            return hwnd
    for hwnd, _v, title, _klass in wins:
        if 'stingray' in title.lower():
            return hwnd
    return wins[0][0] if wins else None


def focus_game(settle=0.35):
    """Restore + focus the game, returning (hwnd, foreground_confirmed)."""
    hwnd = game_window()
    if hwnd is None:
        return None, False
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    time.sleep(settle)
    return hwnd, user32.GetForegroundWindow() == hwnd


def main():
    pids = game_pid()
    if not pids:
        sys.exit('helldivers2.exe is not running')
    pid = pids[0]
    wins = windows_of(pid)
    print('pid %d, %d top-level window(s)' % (pid, len(wins)))
    target = None
    for hwnd, visible, title, klass in wins:
        print('  hwnd=%d visible=%s class=%s title=%r' % (hwnd, visible, klass, title))
        if visible and (target is None or 'stingray' in klass):
            target = hwnd
    if target is None:
        sys.exit('no visible window to focus')
    if len(sys.argv) > 1 and sys.argv[1] == 'focus':
        user32.ShowWindow(target, SW_RESTORE)
        user32.SetForegroundWindow(target)
        foreground = user32.GetForegroundWindow()
        print('focused hwnd=%d foreground=%d match=%s'
              % (target, foreground, foreground == target))
    else:
        print('target hwnd=%d (pass "focus" to restore+focus)' % target)


if __name__ == '__main__':
    main()
