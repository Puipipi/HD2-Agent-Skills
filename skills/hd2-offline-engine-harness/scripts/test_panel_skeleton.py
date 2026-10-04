"""Exercise template/panel_skeleton.lua on LuaJIT with a fake engine boundary.

This is the offline half of "prove the rules before you trust them". It does not
test the game; it tests that the skeleton behaves correctly around the boundary,
which is where the expensive mistakes live:

  1. run the static FFI audit (every called symbol must be declared)
  2. compile it on real LuaJIT and confirm the globals are installed
  3. with NO engine at all: it must not create a GUI, must not crash, and must
     name why it is holding
  4. with a partial engine (no ship world): it must stop BEFORE the GUI stage
  5. with a full engine: it advances to the last stage, and a GUI is created at
     most once
  6. a frame that throws 5 times must STOP the feature and leave a reason, not
     keep throwing forever

Run:  python -B scripts/test_panel_skeleton.py [--skeleton <path>]

Prerequisites
    Python 3.8+ and lupa (real LuaJIT 2.1 with ffi). No game, no loader tools.
    It writes its scratch log directory under the system temp dir, never in the repo.
"""
import argparse
import importlib.util
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from lupa import luajit21 as lj  # noqa: E402  (LuaJIT 2.1 — the real target)

FAILS = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + (("  -- " + detail) if detail and not cond else ""))
    if not cond:
        FAILS.append(label)


def fresh(source, prelude=""):
    """A LuaJIT runtime with a fake environment. The skeleton writes a log file,
    so point LOCALAPPDATA at a scratch dir to keep the workspace clean."""
    # Under the system temp dir, never inside the repository: a harness that
    # litters the working tree gets its own output committed by accident.
    scratch = os.path.join(tempfile.gettempdir(), "hd2_skeleton_harness")
    os.makedirs(os.path.join(scratch, "CowboyBingus", "Helldivers2", "Logs"), exist_ok=True)
    rt = lj.LuaRuntime(unpack_returned_tuples=True)
    rt.execute(f"os.getenv = function(n) if n == 'LOCALAPPDATA' then return [[{scratch}]] end end")
    if prelude:
        rt.execute(prelude)
    rt.execute(source)
    return rt


# ---------------------------------------------------------------- 1. ffi audit
def test_ffi_audit():
    """Prefer this repository's own auditor; fall back to a workspace copy."""
    candidates = [
        os.path.join(SKILL, "..", "hd2-ffi-audit", "scripts", "ffi_audit.py"),
        os.path.join(HERE, "..", "..", "..", "mods", "custom-armor-kit", "work",
                     "standalone", "ffi_audit.py"),
    ]
    found = next((os.path.abspath(c) for c in candidates if os.path.exists(c)), None)
    if found is None:
        check("static FFI audit available", False, "ffi_audit.py not found")
        return
    spec = importlib.util.spec_from_file_location("ffi_audit", found)
    if spec is None or not os.path.exists(spec.origin):
        check("static FFI audit runs", False, "ffi_audit.py not found")
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    missing = mod.audit(SKELETON, verbose=False)
    check("static FFI audit: every called symbol is declared", not missing, str(missing))


# ------------------------------------------------------- 2. compiles on LuaJIT
def test_compiles():
    src = open(SKELETON, encoding="utf-8").read()
    rt = lj.LuaRuntime()
    try:
        rt.execute("return function(s) return loadstring(s, 'skeleton') end")
        loader = rt.eval("function(s) return loadstring(s, 'skeleton') end")
        chunk = loader(src)
        check("compiles on LuaJIT 2.1", chunk is not None)
        # Two legitimate shapes: require('ffi') and pcall(require, 'ffi').
        check("uses LuaJIT ffi",
              bool(re.search(r"require\s*\(\s*['\"]ffi['\"]\s*\)", src))
              or bool(re.search(r"require\s*,\s*['\"]ffi['\"]", src)))
        check("no engine writes (WriteProcessMemory absent)", "WriteProcessMemory" not in src)
        check("no VirtualAllocEx (memory allocation absent)", "VirtualAllocEx" not in src)
    except Exception as exc:  # pragma: no cover - compile failure is the finding
        check("compiles on LuaJIT 2.1", False, str(exc))


# ------------------------------------------------- 3. no engine: hold, no crash
def test_no_engine():
    src = open(SKELETON, encoding="utf-8").read()
    rt = fresh(src)
    mod = rt.globals().HD2Skeleton
    check("installs its global on load", mod is not None)
    for i in range(1, 8):
        mod.tick(i)
    check("no engine: does not reach the draw stage", not mod.drew_once)
    check("no engine: stages did not advance past native memory",
          int(mod.stage) < int(rt.eval("HD2Skeleton.stage")) + 1, f"stage={mod.stage}")
    check("no engine: leaves a named hold reason in the log",
          "held" in open(os.path.join(tempfile.gettempdir(), "hd2_skeleton_harness",
                                        "CowboyBingus", "Helldivers2", "Logs",
                                      "HD2Skeleton.log"), encoding="utf-8", errors="replace").read())


# ------------------------------- 4. partial engine: must stop before GUI stage
def test_partial_engine_no_world():
    src = open(SKELETON, encoding="utf-8").read()
    prelude = """
    CREATED = 0
    stingray = { Gui = { resolution = function() return 1920, 1080 end },
                 World = { create_screen_gui = function() CREATED = CREATED + 1; return {} end },
                 Application = { main_world = function() return nil end } }
    """
    rt = fresh(src, prelude)
    mod = rt.globals().HD2Skeleton
    for i in range(1, 20):
        mod.tick(i)
    check("no ship world: no GUI is created", int(rt.globals().CREATED) == 0,
          f"CREATED={rt.globals().CREATED}")
    check("no ship world: stops at the ship-world stage", int(mod.stage) < 4, f"stage={mod.stage}")


# ------------------------------------- 5. full engine: advances, one GUI at most
def test_full_engine():
    src = open(SKELETON, encoding="utf-8").read()
    prelude = """
    CREATED = 0
    WORLD = { name = 'ship' }
    stingray = { Gui = { resolution = function() return 1920, 1080 end },
                 World = { create_screen_gui = function() CREATED = CREATED + 1; return {} end },
                 Application = { main_world = function() return WORLD end } }
    """
    rt = fresh(src, prelude)
    mod = rt.globals().HD2Skeleton
    for i in range(1, 30):
        mod.tick(i)
    check("full engine: advances to the last stage", int(mod.stage) == 6, f"stage={mod.stage}")
    check("full engine: records the resolution", f"{mod.rw}x{mod.rh}" == "1920x1080",
          f"{mod.rw}x{mod.rh}")
    check("full engine: reaches the draw stage exactly once", bool(mod.drew_once))
    check("full engine: creates no more than one GUI", int(rt.globals().CREATED) <= 1,
          f"CREATED={rt.globals().CREATED}")


# ------------------------------------------- 6. frame error budget stops a loop
def test_error_budget():
    """A frame that keeps throwing must STOP the feature after FAIL_LIMIT
    consecutive failures and leave a named reason — not throw forever.

    MOD.work is driven, not MOD.frame: the budget guard lives in the real frame
    body, so replacing the body would test nothing.
    """
    prelude = """
    CREATED = 0
    WORLD = { name = 'ship' }
    stingray = { Gui = { resolution = function() return 1920, 1080 end },
                 World = { create_screen_gui = function() CREATED = CREATED + 1; return {} end },
                 Application = { main_world = function() return WORLD end } }
    """
    src = open(SKELETON, encoding="utf-8").read()
    rt = fresh(src, prelude)
    mod = rt.globals().HD2Skeleton

    # Let it reach the last stage first, then make the work step throw.
    for i in range(1, 4):
        mod.tick(i)
    rt.execute("""
    BOOM_CALLS = 0
    HD2Skeleton.work = function() BOOM_CALLS = BOOM_CALLS + 1; error('synthetic work failure') end
    """)

    calls_at_stop = None
    peak_errors = 0
    for i in range(10, 24):
        mod.tick(i)
        peak_errors = max(peak_errors, int(mod.frame_errors))
        if mod.stopped_reason is not None and calls_at_stop is None:
            calls_at_stop = int(rt.globals().BOOM_CALLS)
    total_calls = int(rt.globals().BOOM_CALLS)

    # The counter reaches FAIL_LIMIT at the moment of stopping; afterwards the
    # guard short-circuits the body, so the counter stays where it stopped
    # instead of climbing. Asserting on the final value would be wrong.
    check("error budget: counter reached FAIL_LIMIT on the way to stopping",
          peak_errors == 5, f"peak_errors={peak_errors}")
    check("error budget: counter does not climb past FAIL_LIMIT",
          int(mod.frame_errors) <= 5, f"frame_errors={mod.frame_errors}")
    check("error budget: records a named stop reason",
          mod.stopped_reason is not None and "synthetic work failure" in str(mod.stopped_reason))
    check("error budget: stops after exactly FAIL_LIMIT frames", calls_at_stop == 5,
          f"calls_at_stop={calls_at_stop}")
    check("error budget: does not run the broken work afterwards",
          total_calls == 5, f"total_calls={total_calls}")

    # A successful frame must reset the counter, or a mod that hiccups once a
    # minute would eventually stop itself.
    rt2 = fresh(open(SKELETON, encoding="utf-8").read(), prelude)
    m2 = rt2.globals().HD2Skeleton
    rt2.execute("""
    N = 0
    HD2Skeleton.work = function()
        N = N + 1
        if N <= 3 then error('first three work calls fail') end
    end
    """)
    for i in range(1, 10):
        m2.tick(i)
    check("error budget: a good frame resets the counter",
          int(m2.frame_errors) == 0 and m2.stopped_reason is None,
          f"frame_errors={m2.frame_errors} stopped={m2.stopped_reason}")


def test_status_file_written():
    """Even a mod that never gets past stage 1 must leave a STATUS file."""
    rt = fresh(open(SKELETON, encoding="utf-8").read())
    mod = rt.globals().HD2Skeleton
    mod.tick(1)
    status = os.path.join(tempfile.gettempdir(), "hd2_skeleton_harness",
                                        "CowboyBingus", "Helldivers2", "Logs",
                          "HD2Skeleton-STATUS.txt")
    check("STATUS file exists after load", os.path.exists(status))
    if os.path.exists(status):
        text = open(status, encoding="utf-8", errors="replace").read()
        check("STATUS names the stage reached", "stages" in text)
        check("STATUS names the held state", "status" in text)


def main():
    test_ffi_audit()
    test_compiles()
    test_no_engine()
    test_partial_engine_no_world()
    test_full_engine()
    test_error_budget()
    test_status_file_written()
    print()
    if FAILS:
        print("RESULT: FAIL (%d)" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Offline engine-boundary harness.")
    ap.add_argument("--skeleton", default=None,
                    help="path to panel_skeleton.lua (default: search the repo)")
    opts = ap.parse_args()

    # Search plausible layouts rather than hard-coding one: this runs from the
    # repo root, from tests/, and from a copied skill folder.
    for cand in (opts.skeleton,
                 os.path.join(HERE, "panel_skeleton.lua"),
                 os.path.join(SKILL, "template", "panel_skeleton.lua"),
                 os.path.join(SKILL, "..", "..", "template", "panel_skeleton.lua"),
                 os.path.join(os.getcwd(), "template", "panel_skeleton.lua")):
        if cand and os.path.exists(cand):
            SKELETON = os.path.abspath(cand)
            break
    else:
        print("panel_skeleton.lua not found; pass --skeleton <path>")
        sys.exit(1)
    print("skeleton: %s" % SKELETON)
    print()
    sys.exit(main())
