"""Game-only long key press, with the foreground check that makes it safe.

Every injected key must be focused first: an unfocused SendKeys goes to whatever
window the user happens to be looking at. This locates the game window by process
id (never by title - it carries U+2122), restores and focuses it, VERIFIES the
foreground actually changed, and re-checks focus between repeats.

    python hd2_verified_input.py <key> [duration] [--repeat N] [--interval S]

Prerequisites
    Windows, Python 3.8+, the GAME RUNNING as the same user (so it can be focused).
    `hd2_window.py` sits next to this file and is shipped with it.
    The autoplay sequence in SKILL.md additionally needs the mods listed there.
"""
import ctypes
import importlib
import os
from pathlib import Path
import sys
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
locator = importlib.import_module('hd2_window')
user32 = locator.user32
KEYS={'space':0x20,'tab':0x09,'esc':0x1B,'f1':0x70,'f8':0x77,'b':0x42,'w':0x57,'e':0x45,'a':0x41,'d':0x44,
      's':0x53,'1':0x31,'2':0x32,'3':0x33,'4':0x34,'v':0x56,'shift':0x10,
      'mouse_left':-1,'mouse_right':-2}

def focus():
    pids=locator.game_pid()
    if len(pids)!=1: raise RuntimeError(f'Expected one game process, got {pids}')
    # class/title preference lives in the locator, so both tools agree on which
    # window is the game rather than each doing their own (different) match.
    hwnd=locator.game_window(pids[0])
    if hwnd is None: raise RuntimeError('No visible game window found')
    user32.ShowWindow(hwnd,9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.35)
    if user32.GetForegroundWindow()!=hwnd: raise RuntimeError('Game did not become foreground')
    print(f'foreground confirmed pid={pids[0]} hwnd={hwnd}')
    return hwnd

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('key')
    parser.add_argument('duration',type=float,nargs='?',default=0.15)
    parser.add_argument('--repeat',type=int,default=1)
    parser.add_argument('--interval',type=float,default=0.25)
    args=parser.parse_args()
    key=args.key.lower()
    duration=args.duration
    parts=key.split('+')
    if len(parts)>3 or len(set(parts))!=len(parts) or any(k not in KEYS for k in parts) or not 0.05<=duration<=2:
        raise ValueError('Unsupported key/duration')
    if not 1<=args.repeat<=20 or not 0.1<=args.interval<=2:raise ValueError('Unsafe repetition')
    hwnd=focus()
    pressed=[(KEYS[k],user32.MapVirtualKeyW(KEYS[k],0) if KEYS[k]>=0 else 0) for k in parts]
    def inject(vk,scan,release=False):
        if vk<0:
            flags={-1:(2,4),-2:(8,16)}[vk]
            user32.mouse_event(flags[1 if release else 0],0,0,0,0)
        else:user32.keybd_event(vk,scan,2 if release else 0,0)
    for index in range(args.repeat):
        if user32.GetForegroundWindow()!=hwnd:raise RuntimeError('Foreground changed; stopped sequence')
        down=[]
        try:
            for vk,scan in pressed:
                inject(vk,scan)
                down.append((vk,scan))
            time.sleep(duration)
        finally:
            for vk,scan in reversed(down):inject(vk,scan,release=True)
        if index+1<args.repeat:time.sleep(args.interval)
    print(f'pressed {key} for {duration:.2f}s x{args.repeat}')
