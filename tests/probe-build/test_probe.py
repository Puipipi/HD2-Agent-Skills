"""Run the shipped probe against a fake engine before asking a human to load it.

If the probe cannot reach "PIPELINE OK" here, a failed in-game run would be
ambiguous: loader problem or probe problem? This removes that ambiguity.
"""
import io
import os
import re

import lupa.luajit21 as lj

SRC = r"C:\Users\23825\Desktop\2-apex-x20\work\scratch\probe_mod\bingus_pipeline_probe.lua"
ZIP = r"C:\Users\23825\Desktop\2-apex-x20\work\scratch\probe_mod\dist\Bingus-Pipeline-Probe-0.1.0.zip"
SCRATCH = r"C:\Users\23825\Desktop\2-apex-x20\work\scratch\probe_mod\_run"

failures = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(label)


src = io.open(SRC, encoding="utf-8").read()
os.makedirs(os.path.join(SCRATCH, "CowboyBingus", "Helldivers2", "Logs"), exist_ok=True)
# fresh log each run so "did it log" is unambiguous
for f in ("BingusPipelineProbe.log", "BingusPipelineProbe-STATUS.txt"):
    p = os.path.join(SCRATCH, "CowboyBingus", "Helldivers2", "Logs", f)
    if os.path.exists(p):
        os.remove(p)

LOG = os.path.join(SCRATCH, "CowboyBingus", "Helldivers2", "Logs", "BingusPipelineProbe.log")
STATUS = os.path.join(SCRATCH, "CowboyBingus", "Helldivers2", "Logs", "BingusPipelineProbe-STATUS.txt")

PRELUDE = """
    CREATED = 0
    WORLD = { name = 'ship' }
    stingray = { Gui = { resolution = function() return 1920, 1080 end },
                 World = { create_screen_gui = function() CREATED = CREATED + 1; return {} end },
                 Application = { main_world = function() return WORLD end } }
    """

rt = lj.LuaRuntime(unpack_returned_tuples=True)
rt.execute(f"os.getenv = function(n) if n == 'LOCALAPPDATA' then return [[{SCRATCH}]] end end")
rt.execute(PRELUDE)
rt.execute(src)
mod = rt.globals().BingusPipelineProbe

for i in range(1, 8):
    mod.tick(i)

log_text = io.open(LOG, encoding="utf-8", errors="replace").read() if os.path.exists(LOG) else ""
status_text = io.open(STATUS, encoding="utf-8", errors="replace").read() if os.path.exists(STATUS) else ""

check("probe logs on load", "enter version=" in log_text, log_text[:200])
check("probe reaches the last stage", int(mod.stage) == 5, f"stage={mod.stage}")
check("probe logs PIPELINE OK", "PIPELINE OK" in log_text, log_text[-300:])
check("probe writes a STATUS file", bool(status_text))
check("STATUS reflects the stage it actually reached", "stage     = 5/5" in status_text,
      status_text[:200])
# The rule is about ffi.cdef DECLARATIONS, not about the word appearing in a
# comment explaining the rule. Check it the way the build gate does.
import re as _re
_declared = set()
for _b in _re.findall(r"ffi\.cdef\s*\[\[(.*?)\]\]", src, _re.S):
    _declared.update(m.group(1) for m in _re.finditer(r"([A-Za-z_]\w*)\s*\([^;()]*\)\s*;", _b))
for _c in _re.findall(r"ffi\.cdef\s*,\s*'([^']*)'", src):
    _declared.update(m.group(1) for m in _re.finditer(r"([A-Za-z_]\w*)\s*\([^;()]*\)\s*;", _c))
USER32 = {"GetCursorPos", "GetClientRect", "ScreenToClient", "GetForegroundWindow",
          "GetAsyncKeyState", "GetWindowThreadProcessId", "GetCurrentProcessId"}
check("probe declares no user32 symbol in any ffi.cdef",
      not (_declared & USER32), str(sorted(_declared & USER32)))
check("probe creates no GUI (it draws nothing)", int(rt.globals().CREATED) == 0)

# The shipped ZIP must match this source, or the probe tests the wrong thing.
import zipfile
z = zipfile.ZipFile(ZIP)
names = z.infolist()
manifest = z.read("manifest.json").decode()
archive = [i for i in names if i.filename.startswith("Addon/") and i.filename.endswith("patch_0")]
check("package has the addon archive", bool(archive))
check("package has README.txt", "README.txt" in [i.filename for i in names])
check("manifest carries the probe GUID",
      "a17f4c6e-9b23-4d81-8f5c-3e7d0a92b416" in manifest)
check("manifest does not advertise a missing icon", "IconPath" not in manifest)
# the archive embeds the source with the declaration line prepended
blob = z.read(archive[0].filename)
check("archive embeds the probe source",
      b"pipeline probe" in blob and b"PIPELINE OK" in blob)

print()
print("RESULT:", "OK" if not failures else f"FAIL ({len(failures)})")
for f in failures:
    print("  - " + f)
raise SystemExit(1 if failures else 0)
