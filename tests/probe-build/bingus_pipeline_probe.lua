-- HD2-Addon: mods/yc426/bingus_pipeline_probe
-- A probe mod: it proves the hd2-bingus-mod-development pipeline end to end.
-- Its whole job is to log that it loaded, then log a heartbeat every 600 frames.
-- Safe to delete: it changes no game data, patches nothing, writes one log file.
local MOD = { version = '0.1.0', global = 'BingusPipelineProbe' }
local KEY = MOD.global
if rawget(_G, KEY) then return rawget(_G, KEY) end
rawset(_G, KEY, MOD)

local HOME = (os.getenv('LOCALAPPDATA') or os.getenv('TEMP') or '.')
             .. '/CowboyBingus/Helldivers2/'
local LOG = HOME .. 'Logs/' .. KEY .. '.log'
local STATUS = HOME .. 'Logs/' .. KEY .. '-STATUS.txt'
local boot = os.clock()

local function stamp() return os.date('!%Y-%m-%dT%H:%M:%SZ') end

local function log(s)
    MOD.status = s
    pcall(function()
        local f = io.open(LOG, 'a') or io.open(KEY .. '.log', 'a')
        if f then f:write(stamp() .. ' ' .. s .. '\n') f:close() end
    end)
end

-- Written on load and on a heartbeat, so "it never drew anything" still leaves
-- a file that can be sent in a bug report.
local function write_status()
    pcall(function()
        local f = io.open(STATUS, 'w')
        if not f then return end
        for _, line in ipairs({
            KEY .. ' ' .. MOD.version,
            'status    = ' .. tostring(MOD.status),
            'frame     = ' .. tostring(MOD.frame),
            'uptime_s  = ' .. string.format('%.1f', os.clock() - boot),
            'stage     = ' .. tostring(MOD.stage) .. '/' .. tostring(#MOD.STAGES),
        }) do f:write(line .. '\n') end
        f:close()
    end)
end

log('enter version=' .. MOD.version .. ' (pipeline probe)')

local ok_ffi, ffi = pcall(require, 'ffi')
MOD.ffi_ok = ok_ffi
local k
if ok_ffi then
    -- kernel32 only. Declaring a user32 symbol here would displace another
    -- mod's declaration, because LuaJIT's ffi.cdef keeps the first one.
    for _, d in ipairs({
        'void *GetModuleHandleA(const char*);',
        'void *GetCurrentProcess(void);',
        'int ReadProcessMemory(void*,const void*,void*,size_t,size_t*);',
        'size_t VirtualQuery(const void*,void*,size_t);',
    }) do pcall(ffi.cdef, d) end
    local ok_load, lib = pcall(ffi.load, 'kernel32')
    if ok_load then k = lib end
end
log('ffi=' .. tostring(ok_ffi) .. ' kernel32=' .. tostring(k ~= nil))

-- Positive-fact guards: a value check, not a pcall. Staged, and re-checked each
-- frame; nothing is latched as impossible on one early failure.
MOD.STAGES = { 'ffi surface', 'engine table', 'ship world', 'gui resolution', 'done' }
MOD.stage = 0

local function callable(v)
    local t = type(v)
    return t == 'function' or t == 'cdata'          -- LuaJIT binds C fns as cdata
end

local function call_engine(what, fn, ...)
    if type(fn) ~= 'function' then return false, what .. ': not a function' end
    -- The arity is spelled out: `local ok, a = pcall(...)` silently drops every
    -- result after the first, which makes two-value engine calls look broken.
    local ok, a, b = pcall(fn, ...)
    if not ok then
        log('engine call failed: ' .. what .. ': ' .. tostring(a))
        return false, tostring(a)
    end
    return true, a, b
end

local STAGE_FACT = {
    [1] = function()
        if not ok_ffi then return false, 'ffi unavailable' end
        if not k then return false, 'kernel32 unavailable' end
        if not callable(k.ReadProcessMemory) then return false, 'ReadProcessMemory undeclared' end
        return true
    end,
    [2] = function()
        local sr = rawget(_G, 'stingray')
        if type(sr) ~= 'table' then return false, 'stingray not a table' end
        if type(sr.Gui) ~= 'table' or type(sr.World) ~= 'table' then
            return false, 'Gui/World missing'
        end
        if type(sr.Application) ~= 'table' then return false, 'Application missing' end
        return true
    end,
    [3] = function()
        -- The ship world resolves LATE. Creating a screen GUI before it exists
        -- faults at native level, and pcall cannot catch that.
        local ok, world = call_engine('Application.main_world',
            rawget(_G, 'stingray').Application.main_world)
        if not ok or world == nil then return false, 'main_world not resolved' end
        MOD.ship_world = world
        return true
    end,
    [4] = function()
        local sr = rawget(_G, 'stingray')
        local ok, w, h = call_engine('Gui.resolution', sr.Gui.resolution)
        if not ok then return false, 'resolution unavailable' end
        if type(w) ~= 'number' or type(h) ~= 'number' then return false, 'resolution not numeric' end
        if w < 640 or h < 480 then return false, 'implausible resolution' end
        MOD.rw, MOD.rh = w, h
        return true
    end,
    [5] = function() return true end,
}

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
            .. (next_stage == 4 and (' res=' .. tostring(MOD.rw) .. 'x' .. tostring(MOD.rh)) or ''))
        -- Refresh STATUS on every transition, not only at load: a STATUS file
        -- that says "stage = 0/5" while the log says "stage 5 ok" is worse than
        -- no STATUS file, because it sends the reader down the wrong path.
        write_status()
    end
end

-- A frame error budget: five consecutive failures stop the feature and leave a
-- named reason, rather than throwing forever.
local FAIL_LIMIT = 5

local function frame(frames)
    MOD.frame = frames
    if MOD.stopped_reason or (MOD.frame_errors or 0) >= FAIL_LIMIT then return end
    advance_stages()
    if MOD.stage < #MOD.STAGES then
        if frames % 300 == 0 then
            log('waiting: stage=' .. MOD.stage .. '/' .. #MOD.STAGES
                .. ' status=' .. tostring(MOD.status))
        end
        return
    end
    if not MOD.reached_done then
        MOD.reached_done = true
        log('PIPELINE OK: all stages reached; probe is a loadable, running mod')
    end
end

local function safe_frame(frames)
    local ok, why = pcall(frame, frames)
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

MOD.frame_number = 0
MOD.heartbeat = 0
MOD.frame = frame
MOD.tick = function(frames)
    MOD.frame_number = frames or (MOD.frame_number + 1)
    safe_frame(MOD.frame_number)
    MOD.heartbeat = MOD.heartbeat + 1
    if MOD.heartbeat % 600 == 0 then write_status() end
end

-- Adapt this to your loader's update hook if it does not drive MOD.tick.
local function register()
    local sr = rawget(_G, 'stingray')
    if type(sr) ~= 'table' then
        log('no stingray at load time; the loader hook must drive MOD.tick')
    end
    MOD.registered = true
end
register()

--=== IN-GAME README: the build extracts this into README.txt ===============
--[===[Bingus Pipeline Probe - quick guide

This is a probe mod, not a gameplay mod. It exists to prove that a mod built by
the hd2-bingus-mod-development pipeline loads and runs.

What it does:
  - writes Logs/BingusPipelineProbe.log when it loads
  - writes Logs/BingusPipelineProbe-STATUS.txt on load and every 600 frames
  - logs "PIPELINE OK: all stages reached" once the engine is ready

How to confirm it worked:
  1. open %LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\BingusPipelineProbe.log
  2. look for "enter version=" (it loaded) and "PIPELINE OK" (it ran)
  3. if you only see "stage N (...) held: <reason>", that line names the
     precondition that was not true yet - that is the whole point of the log

It changes no game data and patches nothing. Delete the mod folder to remove it.
]===]

log('loaded: ffi=' .. tostring(MOD.ffi_ok) .. ' stages=' .. tostring(MOD.stage))
write_status()
return MOD
