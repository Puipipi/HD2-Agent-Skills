# -*- coding: utf-8 -*-
"""Click inside the game despite the game moving the cursor itself.

The loadout/briefing screen repositions the pointer (raw-input camera anchor),
so a plain SetCursorPos lands somewhere else. This sets the position, verifies
it immediately, corrects with relative mouse_event deltas, and only then clicks
- all inside a few milliseconds.

    python hd2_click.py <logical_x> <logical_y> [--double] [--no-focus]
"""
import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.WinDLL('user32', use_last_error=True)


class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.mouse_event.argtypes = [wintypes.DWORD, ctypes.c_long, ctypes.c_long,
                               wintypes.DWORD, ctypes.POINTER(ctypes.c_ulong)]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def position():
    point = POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def focus_game():
    sys.path.insert(0, __file__.rsplit('\\', 1)[0])
    import importlib
    module = importlib.import_module('hd2_window')
    pids = module.game_pid()
    if not pids:
        return None
    for hwnd, visible, _title, klass in module.windows_of(pids[0]):
        if visible and 'stingray' in klass:
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.35)
            return hwnd
    return None


def move_to(x, y, tries=8):
    """Set + verify + correct with relative deltas until the pointer sticks."""
    for _ in range(tries):
        user32.SetCursorPos(int(x), int(y))
        current = position()
        dx, dy = int(x) - current[0], int(y) - current[1]
        if abs(dx) <= 3 and abs(dy) <= 3:
            return current, True
        user32.mouse_event(MOUSEEVENTF_MOVE, dx, dy, 0, None)
    return position(), False


def click(x, y, double=False, settle=0.0):
    landed, ok = move_to(x, y)
    if settle:
        # Hover first: the briefing grid only arms a slot once it has seen the
        # pointer, and an immediate click lands before that.
        time.sleep(settle)
        user32.SetCursorPos(int(x), int(y))
        time.sleep(0.05)
    user32.SetCursorPos(int(x), int(y))
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, None)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, None)
    if double:
        time.sleep(0.06)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, None)
        time.sleep(0.05)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, None)
    return landed, ok


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    x, y = int(args[0]), int(args[1])
    settle = 0.0
    for a in sys.argv[1:]:
        if a.startswith('--settle='):
            settle = float(a.split('=', 1)[1])
    if '--no-focus' not in sys.argv:
        hwnd = focus_game()
        print('focus hwnd=%s' % hwnd)
    time.sleep(0.2)
    before = position()
    landed, ok = click(x, y, double='--double' in sys.argv, settle=settle)
    after = position()
    print('target=(%d,%d) settle=%.2fs before=%s landed=%s locked=%s after=%s'
          % (x, y, settle, before, landed, ok, after))


if __name__ == '__main__':
    main()
