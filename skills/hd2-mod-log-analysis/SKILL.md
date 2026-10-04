---
name: hd2-mod-log-analysis
description: Analyze a Helldivers 2 mod's runtime log to answer "did it actually do anything, and where did it stop?" — stage-by-stage classification of a stage-based log, append-across-launches and UTC timestamp handling, correlating two mods' logs in one session, and JSON output for reports. Use when a mod appears to do nothing, when a feature silently no-ops, or when you need in-game evidence without launching the game.
---

# hd2-mod-log-analysis

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-mod-log-analysis/SKILL_cn.md)

> **Confidence:** reported. The incident behind it is real; no script here was executed.

"The mod does nothing" is only answerable from the log. This skill is how to read one, and
how to write a tool that reads it for you.

The motivating case, from this workspace: a mod stayed **silent for 165 sessions** without
leaving a single trace. Making the log stage-based, and writing one analyzer for it
(`stratagem-cooldown/tools/analyze_vehicle_cooldown_log.py`), is what turned "does nothing"
into "stopped at `locate failed`".

## Prerequisites

| Need | Why | If missing |
|---|---|---|
| Python 3.8+ | the analyzer | — |
| the mod's log file | the evidence | default to the standard path and **say** what it looked at: `%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\<Mod>.log` |
| the game **not** required | reading a log needs no game | — if the file is absent, print the path tried and exit non-zero; do not crash |

Read-only. It never touches the game, its files or its memory.

## First: the log is the deliverable

You cannot analyze a log that does not exist. Before writing the analyzer, make the mod log
correctly — this is the part that decides whether analysis is possible at all:

1. **One line per state change**, plus a heartbeat while stuck. Never per frame.
2. **Name every outcome, including the negative ones.** `table located at load`,
   `no vehicle records yet`, `ABORTED + rolled back`, `error: ...`. A silent `return` is
   invisible in a log; a named one is a stage.
3. **Make the sequence stage-based**, so a reader can tell *where* it stopped:
   ```python
   STAGES = [
       ('locate failed',  re.compile(r'STOPPED at load')),
       ('located',        re.compile(r'table located at load')),
       ('installed',      re.compile(r'v([\d.]+) installed')),
       ('gate',           re.compile(r'uptime gate passed')),
       ('records',        re.compile(r'vehicle records appeared')),
       ('no-records',     re.compile(r'no vehicle records yet')),
       ('applied',        re.compile(r'cooldown applied to')),
       ('rollback',       re.compile(r'ABORTED \+ rolled back')),
       ('error',          re.compile(r'error: ')),
       ('heartbeat',      re.compile(r'heartbeat: ')),
   ]
   ```
4. **Write a status file** alongside it, so "the panel never opened" still produces something
   to send.

## Then: analyzing it

- **Logs append across launches.** To judge "this run", filter by timestamp, not by file
  position — take a cutoff from something in the session (a start marker, a load line) rather
  than assuming the file starts fresh.
- **Timestamps are UTC.** At UTC+8, `12:xx:xxZ` is local 20:xx. Getting this wrong has
  produced real mis-readings of which run a line belonged to. Print both, or say which is
  which.
- **Classify, then count.** Report the stage sequence first (what happened, in order), then
  the per-stage counts. A single `applied` line surrounded by 4000 heartbeats is a different
  bug from `locate failed`.
- **Correlate two mods when the failure crosses them.** The loader interposes on other mods,
  so the answer may be in two files: accept `--log` **and** `--smooth-log`, align them by
  timestamp, and report the combined sequence.
- **`--json`** so a report can quote exact numbers instead of paraphrasing.
- **Never paraphrase away the raw line.** Include the matching log line (or its line number)
  next to each classification, so a human can go look.

## Skeleton

```python
"""Read <Mod>'s runtime log and report what the addon actually did, stage by stage.

    python -B tools/analyze_<mod>_log.py
    python -B tools/analyze_<mod>_log.py --log <path> --smooth-log <path> --json

Read-only diagnostic: it never touches the game, its files or memory. It exists because
"the mod does nothing" is only answerable from the log, and the 1.5.x family proved that a
mod can stay silent for 165 sessions without leaving a single trace.
"""
import argparse, collections, datetime, io, json, os, re, sys

DEFAULT_LOG = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'CowboyBingus',
                           'Helldivers2', 'Logs', '<Mod>.log')
```

Report shape: stage sequence, counts per stage, first and last timestamp, the run's line
count, and any `error:` / `rollback` lines quoted verbatim. Exit non-zero when the log is
missing or contains nothing for the selected window — an empty report must not look like a
pass.

## Limitations

- It can only see what the mod logged. If the mod was skipped by the loader, there is no log
  at all — check `BingusSharedLoader.log` first, which says whether the entry loaded.
- Regex stage matching is only as good as the log's discipline: two features sharing one
  message string cannot be told apart.
- A log says what the mod *believed*; it is not independent proof of game behaviour. Pair it
  with a screenshot or an in-game observation for anything user-visible.

## See also

`writing-mod-tools` (exit codes, `--json`, prerequisites, honest limits),
`docs/hd2-mod-failure-catalog.md` §7 for what to log in the first place.
