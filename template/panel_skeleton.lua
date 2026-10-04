-- HD2 mod skeleton — a minimal, contract-correct starting point.
--
-- Purpose: prove the two rules that cost the most time before you write any
-- feature code.
--
--   1. A guard must be a VALUE CHECK, not pcall.  pcall only traps Lua errors;
--      a NULL engine slot or a bad pointer faults natively and kills the frame
--      callback for the rest of the session.  See native_ok()/call_engine().
--   2. Bring the engine up in STAGES, and only advance on a positive fact.
--      Log the first success of every stage and the reason for every hold.
--   3. Never let a broken frame repeat forever: count consecutive failures and
--      stop the feature after FAIL_LIMIT, leaving a named reason in the log.
--
-- What this file deliberately does NOT do (read the skills/ docs instead):
--   * no drawing beyond one rect      -> hd2-in-game-panel
--   * no input lock / cursor grab     -> hd2-native-panel-input-lock (see the
--     opt-in cursor helper at the bottom, which needs the F7 panel to make sense)
--   * no game memory writes at all
--
-- Deploy: drop the built addon into your loader, then check the log at
--   %LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\<global>.log
-- and the STATUS file next to it, which is written even when nothing else works.

local KEY = 'HD2Skeleton'
if rawget(_G, KEY) then return rawget(_G, KEY) end        -- survive re-injection

local MOD = {
    version = '0.1.0',
    global  = KEY,
    status  = 'starting',
    frame   = 0,
}
rawset(_G, KEY, MOD)

--==========================================================================
-- 0. Logging.  One line per state change, plus a STATUS file the user can
--    send you when the mod "does nothing".  Never log per frame.
--==========================================================================
local HOME = (os.getenv('LOCALAPPDATA') or os.getenv('TEMP') or '.')
             .. '/CowboyBingus/Helldivers2/'
local LOG = HOME .. 'Logs/' .. KEY .. '.log'
local STATUS = HOME .. 'Logs/' .. KEY .. '-STATUS.txt'
local boot = os.clock()

local function stamp() return os.date('!%Y-%m-%dT%H:%M:%SZ') end

-- Append one line.  The whole thing is pcall'd: logging must never be the
-- reason a frame dies.
local function log(s)
    MOD.status = s
    pcall(function()
        local f = io.open(LOG, 'a') or io.open(KEY .. '.log', 'a')
        if f then f:write(stamp() .. ' ' .. s .. '\n') f:close() end
    end)
end

-- Overwrite the STATUS file.  Cheap facts only; safe to call on a heartbeat.
local function write_status()
    pcall(function()
        local f = io.open(STATUS, 'w')
        if not f then return end
        for _, line in ipairs({
            KEY .. ' ' .. MOD.version,
            'status    = ' .. tostring(MOD.status),
            'frame     = ' .. tostring(MOD.frame),
            'uptime_s  = ' .. string.format('%.1f', os.clock() - boot),
            'stages    = ' .. tostring(MOD.stage) .. '/' .. tostring(#MOD.STAGES),
            'ship_ok   = ' .. tostring(MOD.ship_ok == true),
            'world     = ' .. tostring(MOD.world_serial or 0),
            'gui       = ' .. tostring(MOD.gui ~= nil),
            'ffi_ok    = ' .. tostring(MOD.ffi_ok == true),
            'frame_err = ' .. tostring(MOD.frame_errors or 0),
            'stopped   = ' .. tostring(MOD.stopped_reason or 'no'),
        }) do f:write(line .. '\n') end
        f:close()
    end)
end

log('enter version=' .. MOD.version)

--==========================================================================
-- 1. RULE 1 — native-safe guards, and an FFI surface that cannot half-load.
--==========================================================================
-- Every symbol you CALL must be declared, and a declaration another mod got
-- first wins in LuaJIT.  A missing declaration is a hard error at the call
-- site, which is exactly how "clicking a card does nothing" happened once.
-- Audit this list with ffi_audit.py before shipping.
local FFI_LIST = {
    'void *GetCurrentProcess(void);',
    'uint32_t GetCurrentProcessId(void);',
    'int ReadProcessMemory(void*,const void*,void*,size_t,size_t*);',
    'size_t VirtualQuery(const void*,void*,size_t);',
}

local ffi_ok, ffi = pcall(require, 'ffi')
MOD.ffi_ok = ffi_ok
local k                                              -- kernel32, when usable
if ffi_ok then
    -- A failed cdef must NOT be silent.  A typo in a declaration list is how
    -- "the mod loads but every action does nothing" starts: the call site
    -- raises "missing declaration for symbol 'X'".  ffi_audit.py catches the
    -- static case; this catches the runtime one.
    for _, d in ipairs(FFI_LIST) do
        local ok_d, err = pcall(ffi.cdef, d)
        if not ok_d then log('ffi.cdef FAILED for: ' .. d .. ' -- ' .. tostring(err)) end
    end
    local ok_load, lib = pcall(ffi.load, 'kernel32')
    if ok_load then k = lib else log('ffi.load kernel32 failed: ' .. tostring(lib)) end
end
log('ffi=' .. tostring(ffi_ok) .. ' kernel32=' .. tostring(k ~= nil))

-- LuaJIT binds a C function as callable CDATA, not as a Lua function.  Checking
-- only for 'function' is a false negative that silently disables every native
-- path — this file shipped that bug for one run.
local function callable(v)
    local t = type(v)
    return t == 'function' or t == 'cdata'
end

local function u32(s, o)
    if not s or #s < o + 4 then return nil end
    local a, b, c, d = s:byte(o + 1, o + 4)
    return a + 256 * b + 65536 * c + 16777216 * d
end

-- A bounded, guarded read.  Every rule the failure catalog lists for reading
-- game memory is applied here, because getting any of them wrong crashes the
-- process rather than raising:
--   * only MEM_COMMIT (0x1000) and MEM_PRIVATE (0x20000) pages
--   * only readable protection, never guard/noaccess (prot 0 or 1, or >= 0x100)
--   * bounded length, and a plausible address
-- The MBI is parsed as raw bytes: ffi.cdef'ing our own struct could displace
-- another mod's declaration of the same name (LuaJIT keeps the first one).
local READ_MAX = 262144
local MBI = ffi_ok and ffi.new('uint8_t[?]', 48) or nil
local rbuf = ffi_ok and ffi.new('uint8_t[?]', READ_MAX) or nil
local got = ffi_ok and ffi.new('size_t[1]') or nil
local PROC = nil

local function read_mem(at, n)
    if not (k and PROC) then return nil, 'no process handle' end
    if type(at) ~= 'number' or type(n) ~= 'number' then return nil, 'bad args' end
    if n < 1 or n > READ_MAX then return nil, 'length out of range' end
    if at < 65536 or at + n >= 140737488355328 then return nil, 'address out of range' end

    if k.VirtualQuery(ffi.cast('const void*', at), ffi.cast('void*', MBI), 48) ~= 48 then
        return nil, 'VirtualQuery failed'
    end
    local mbi = ffi.string(MBI, 48)
    local state, prot = u32(mbi, 32), u32(mbi, 36)
    if state ~= 0x1000 then return nil, 'not MEM_COMMIT' end
    if prot == 0 or prot % 256 == 1 or prot >= 0x100 then return nil, 'unreadable protection' end

    if k.ReadProcessMemory(PROC, ffi.cast('const void*', at), ffi.cast('void*', rbuf), n, got) == 0 then
        return nil, 'ReadProcessMemory failed'
    end
    if tonumber(got[0]) ~= n then return nil, 'short read' end
    return ffi.string(rbuf, n)
end

--==========================================================================
-- 1b. RULE 1 — positive-fact guards.
--==========================================================================
-- A guard must be an observed value.  Each of these returns false instead of
-- calling into the engine when the precondition cannot be shown to hold.
local function native_ok()
    if not ffi_ok then return false, 'ffi unavailable' end
    if not k then return false, 'kernel32 unavailable' end
    if not callable(k.ReadProcessMemory) then return false, 'ReadProcessMemory undeclared' end
    if not callable(k.VirtualQuery) then return false, 'VirtualQuery undeclared' end
    -- Reading a buffer we own proves the handle and the whole read path work,
    -- before anything depends on them.  GetCurrentProcess returns the
    -- PSEUDO-handle (HANDLE)-1, so the read targets our own static buffer — a
    -- real address — and the handle itself is never treated as an address.
    PROC = PROC or k.GetCurrentProcess()
    if PROC == nil then return false, 'GetCurrentProcess returned nil' end
    local buf_addr = tonumber(ffi.cast('uintptr_t', rbuf))
    if not buf_addr or buf_addr < 65536 then return false, 'static buffer has no address' end
    local probe, why = read_mem(buf_addr, 8)
    if not probe then return false, 'self-read failed: ' .. tostring(why) end
    return true
end

-- The only shape in which it is safe to touch the engine: prove the fact you
-- depend on, then call.  `pcall` around the call is NOT the guard — it is only
-- there so a Lua-level mistake does not also take the frame.
--
-- The return values are spelled out explicitly, and that is the whole point of
-- this helper.  `local ok, a = pcall(fn, ...)` SILENTLY DROPS every result after
-- the first, so a two-value engine call like Gui.resolution() comes back with a
-- nil second value and every guard that checks it fails forever.  It reads as a
-- wrong engine assumption and it is really a Lua arity mistake.
--
-- Need more results? Add them here. Do not reach for select('#') — a helper that
-- returns a variable number of values cannot be compared safely.
local function call_engine(what, fn, ...)
    if type(fn) ~= 'function' then return false, what .. ': not a function' end
    local ok, a, b = pcall(fn, ...)
    if not ok then
        log('engine call failed: ' .. what .. ': ' .. tostring(a))
        return false, tostring(a)
    end
    return true, a, b
end

--==========================================================================
-- 2. RULE 2 — staged bring-up.  Each stage states a fact it needs and a fact
--    it establishes.  It is re-checked every frame; nothing is latched as
--    "impossible" on one early failure (engine libraries are built late).
--==========================================================================
MOD.STAGES = { 'ffi surface', 'native memory', 'engine table', 'ship world', 'gui resolution', 'first draw' }
MOD.stage = 0

local STAGE_FACT = {
    -- stage index -> function returning true, or false plus a reason for the log
    [1] = function()
        if not ffi_ok then return false, 'ffi unavailable' end
        if not k then return false, 'kernel32 unavailable' end
        return true
    end,
    [2] = native_ok,                                     -- positive fact, see above
    [3] = function()
        local sr = rawget(_G, 'stingray')
        if type(sr) ~= 'table' then return false, 'stingray not a table' end
        if type(sr.Gui) ~= 'table' or type(sr.World) ~= 'table' then
            return false, 'Gui/World missing'
        end
        if type(sr.Application) ~= 'table' then return false, 'Application missing' end
        return true
    end,
    [4] = function()
        -- The ship world resolves LATE (observed around frame 600).  Creating a
        -- screen GUI before this faults at native level — pcall cannot catch it.
        local ok, world = call_engine('Application.main_world', rawget(_G, 'stingray').Application.main_world)
        if not ok or world == nil then return false, 'main_world not resolved' end
        MOD.ship_world = world
        MOD.world_serial = MOD.world_serial or 1          -- real mods key a weak map
        return true
    end,
    [5] = function()
        local sr = rawget(_G, 'stingray')
        local ok, w, h = call_engine('Gui.resolution', sr.Gui.resolution)
        if not ok then return false, 'resolution unavailable' end
        if type(w) ~= 'number' or type(h) ~= 'number' then return false, 'resolution not numeric' end
        if w < 640 or h < 480 then return false, 'implausible resolution' end
        MOD.rw, MOD.rh = w, h
        return true
    end,
    [6] = function()
        -- Only now is any GUI call defensible.  The skeleton stops here: the
        -- real work is hd2-in-game-panel's job.
        return true, 'ready for panel work'
    end,
}

-- Advance as far as the observed facts allow, logging every transition and the
-- reason for each hold exactly once.
local function advance_stages()
    while MOD.stage < #MOD.STAGES do
        local next_stage = MOD.stage + 1
        local ok, why = STAGE_FACT[next_stage]()
        if not ok then
            local key = 'hold' .. next_stage
            if not MOD[key] then
                MOD[key] = true
                log('stage ' .. next_stage .. ' (' .. MOD.STAGES[next_stage] .. ') held: ' .. tostring(why))
            end
            return
        end
        MOD.stage = next_stage
        MOD['hold' .. next_stage] = nil
        log('stage ' .. next_stage .. ' (' .. MOD.STAGES[next_stage] .. ') ok'
            .. (next_stage == 5 and (' res=' .. tostring(MOD.rw) .. 'x' .. tostring(MOD.rh)) or ''))
    end
end

-- The per-frame body.  Called through the budget wrapper below — the wrapper is
-- not optional: one broken frame repeated every frame is how a mod becomes an
-- unplayable game.
--
-- NOTE the ordering trap, because it bit this file: FAIL_LIMIT must be declared
-- ABOVE frame(). A `local` declared later in the chunk is not in scope inside an
-- earlier function, so the reference silently compiled to a GLOBAL nil and
-- `0 >= nil` raised on the first frame. Lua does not warn about this.
local FAIL_LIMIT = 5

local function frame(frames)
    -- "Stopped" must mean stopped.  Without this check the budget would keep
    -- calling the broken body on every later frame (the counter resets when a
    -- call returns without raising), which would loop forever in practice.
    if MOD.stopped_reason or (MOD.frame_errors or 0) >= FAIL_LIMIT then return end

    -- Cheap, no engine access: safe even when everything above failed.
    advance_stages()
    if MOD.stage < #MOD.STAGES then
        if frames % 300 == 0 then
            log('waiting: stage=' .. MOD.stage .. '/' .. #MOD.STAGES
                .. ' status=' .. tostring(MOD.status))
        end
        return
    end

    -- --- feature work goes here -------------------------------------------
    -- One rect, drawn once, is the smallest thing that proves the whole path:
    --   Gui.rect(gui, Vector3(x, y, layer), Vector2(w, h), color)
    -- Remember Gui origin is bottom-left and y is up.
    --
    -- Put your per-frame work in MOD.work and call it here.  The indirection is
    -- the seam the tests drive: replacing MOD.work exercises the error budget
    -- through the REAL guard above, whereas replacing MOD.frame would bypass it.
    -- ---------------------------------------------------------------------
    if not MOD.drew_once then
        MOD.drew_once = true
        log('feature ready: first draw point reached (see hd2-in-game-panel)')
    end
    if MOD.work then MOD.work(MOD.rw, MOD.rh) end
end

-- The budget wrapper.  Five consecutive failures stop the feature and leave a
-- named reason behind; the process and the game keep running.
local function safe_frame(frames)
    local ok, why = pcall(MOD.frame, frames)
    if ok then
        MOD.frame_errors = 0
        return
    end
    MOD.frame_errors = (MOD.frame_errors or 0) + 1
    log('frame error ' .. MOD.frame_errors .. '/' .. FAIL_LIMIT .. ': ' .. tostring(why))
    if MOD.frame_errors >= FAIL_LIMIT then
        MOD.stopped_reason = tostring(why)
        log('STOPPED after ' .. FAIL_LIMIT .. ' consecutive frame errors: ' .. MOD.stopped_reason)
        write_status()
    end
end

-- Called by the loader (name it whatever your loader calls).  Exposed on MOD so
-- this file is testable without a loader.  MOD.frame is a deliberate seam:
-- replace it to exercise the budget from a test.
MOD.frame_number = 0
MOD.heartbeat = 0
MOD.frame = frame
MOD.tick = function(frames)
    MOD.frame_number = frames or (MOD.frame_number + 1)
    safe_frame(MOD.frame_number)
    MOD.heartbeat = MOD.heartbeat + 1
    if MOD.heartbeat % 600 == 0 then write_status() end
end

--==========================================================================
-- 4. Registration — the part that differs per loader.  Keep it at the bottom
--    so the contract above stays readable.
--==========================================================================
-- Most HD2 mods are driven by the loader's own update hook.  Adapt this to your
-- loader; the two things that matter are (a) the entry point is wrapped in the
-- budget, and (b) a heartbeat writes STATUS so a dead mod still leaves evidence.
local function register()
    local sr = rawget(_G, 'stingray')
    if type(sr) ~= 'table' then
        log('no stingray at load time; frames will be driven by the loader hook')
    end
    MOD.registered = true
end
register()

--=== OPT-IN: Win32 pointer, for when you add a clickable panel =============
-- Only meaningful once you open a panel; see hd2-native-panel-input-lock.
-- The two rules that matter here: read the button from Windows (the engine's
-- Mouse.button is unreliable in menu states), and treat the cursor as
-- client-pixels-top-left, converting to Gui units with Y flipped.
--   y_gui = height - (y_px * height / client_h)
-- Uncomment and declare GetForegroundWindow / GetWindowThreadProcessId /
-- GetCurrentProcessId / GetCursorPos / ScreenToClient / GetClientRect /
-- GetAsyncKeyState, then run ffi_audit.py again.

log('loaded: ffi=' .. tostring(MOD.ffi_ok) .. ' stages=' .. tostring(MOD.stage))
write_status()
return MOD
