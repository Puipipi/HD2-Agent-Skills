---
name: hd2-event-chat-automation
description: Use when building or debugging Helldivers 2 event-driven chat alerts, message templates, per-player cooldowns, welcome or scheduled messages, host/client AutoChat presets, or an AutoChat plugin. This describes AutoChat's verified contract; other mods may choose different behavior.
---

# HD2 event chat automation

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-event-chat-automation/SKILL_cn.md)

Use this for the message path after a game event is identified. Event recognition is a separate concern; do not infer a trigger from an alert's message or rule name. Use [HD2 game event identification](../hd2-game-event-identification/SKILL.md) for the upstream evidence and normalized event. AutoChat-specific behavior below is verified against [PLAYER-TEMPLATES.md](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/docs/PLAYER-TEMPLATES.md), [PLUGIN-API.md](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/docs/PLUGIN-API.md), and their linked source/tests. Treat these as that product's contract, not a requirement for every mod.

## Event, welcome, and scheduled-message timing

AutoChat's default event bucket is shared by one triggering player across ordinary event rules. When a rule has an explicit cooldown, that rule instead uses its own bucket for that player; it replaces the default bucket rather than stacking on top of it. A cooldown-rejected event is consumed and marked seen, so it is dropped rather than held until the bucket reopens. This differs from an event already accepted into AutoChat's bounded internal ping queue: a transient send failure can keep that accepted entry for retry until its expiry. A zero-cooldown rule uses the urgent queue path, but still obeys master enable, dedupe, session, role, creator and send checks. Welcome messages are independent per newcomer: configured delay and one-welcome-per-session behavior remain in force, but event cooldown does not defer them. Scheduled messages also run when due despite event cooldown and keep their own recurrence; neither welcome nor scheduled sends refreshes the event-cooldown ledger. Do not replace these actor-scoped rules with a shared global drop gate: simultaneous newcomers must each be eligible for their own welcome.

## Identity, templates, and output

AutoChat sends through local chat, so the displayed sender remains the local player in this implementation. `creator_id` is trigger ownership/filter context; it does not select or spoof the network sender. This product-specific fact says nothing about every engine or mod's ability to alter identity.

Template tokens are fixed aliases replaced by the formatter, not regular expressions. The player aliases include `{player}`, `{player_name}`, `{name}`, `{short}`, `{abbr}`, `{slot}`, and `{number}`; event and mission aliases include `{category}`, `{target}`, `{stratagem}`, `{action}`, `{objective}`, `{task}`, `{objective_type}`, `{task_type}`, and `{position}`. Player tokens are available in welcome, scheduled, and plugin messages; event tokens are populated only when their event/mission context supplies a value. Replacement is one pass: braces or percent signs inside a player's name are inserted literally and are not interpreted as another token; unknown tokens remain unchanged. See the linked template guide for the full table and examples.

For AutoChat core alerts, a known complete player name is wrapped once as `[name]`; a missing identity uses the teammate fallback without brackets. Before substitution, the formatter removes control characters and literal `<`/`>` delimiters from the name; text inside a tag-like sequence remains as ordinary name text, so do not preserve markup from a player name. Braces and percent signs remain literal after the single substitution pass. The core colors the name and mark prefix only when `ping_sender_color` is enabled. Plugin messages get bracket formatting but no automatic name color. A single leading line feed is added before the body. The body budget is 511 bytes, including color markup, so the line feed plus body must fit the 512-byte chat limit. UTF-8 truncation also closes active color markup within that budget. Host output defaults to squad chat and client output defaults to local-only, but the selected role profile's `output` setting controls the actual route. If local output fails, AutoChat does not fall back to public chat.

## Role presets and saved state

Host and client presets are separate pools. Four built-in presets (Chinese/English for each role) are immutable: they cannot be deleted, overwritten, or renamed. Their default profiles enable the actual reminder flags while retaining role output defaults and solo-permission policy; this does not mean every boolean is enabled. Event-rule overrides start empty, so a new preset does not create zero-cooldown rules. Retired `quick_timer_*` fields are excluded from portable snapshots and must not be presented as an active feature or restored when loading a preset. The new-install selection defaults to the English built-in, independently of UI language. Merely changing UI language or selecting a preset does not apply its settings: explicit manual apply does. Never migrate an existing user's saved settings or custom presets to these built-in defaults.

Portable preset snapshots capture role options, portable task definitions, and only plugin data that opts into the preset hooks. Task definitions carry their name, mode, time, message, and enabled state, not runtime IDs, due times, delivery results, or progress. Older snapshots without task data leave the destination role's tasks intact. The library has no ordinary fixed item-count cap, but payload, persistence-size, and serial-number bounds still apply; describe it as bounded by those storage constraints, not unlimited.

## Plugin integration and batch editing

The AutoChat plugin contract documents the same-level menu registration, load-before/load-after handling, game/API language source, readonly settings snapshot, and optional inherited or independent send policy. The panel's English preview locale is UI-only; it must not leak into plugin language or message-template selection. An independent plugin cooldown/output setting does not skip session, role, creator/ownership, native-send, or message-legality checks. The plugin send API has no queue and no event dedupe: with independent `cooldown=0`, each valid call can send again, so the caller must deduplicate repeated event callbacks when needed. This is distinct from AutoChat core's event pipeline, which has its own seen-event handling. Callers that receive a retryable failure own their retry behavior. Preset integration is opt-in through four hooks; preserve unknown plugin blobs, preflight before applying, and roll back failed applies. A readonly settings snapshot must not expose mutable host state.

AutoChat's batch stratagem-rule editor is an internal UI/backend operation: it scopes edits by role and current filter, spans pages, applies atomically, and preserves unrelated rule fields. Do not present it as a public plugin SDK method.

## See also

- [HD2 in-game panel](../hd2-in-game-panel/SKILL.md) for panel lifecycle and layout.
- [HD2 game event identification](../hd2-game-event-identification/SKILL.md) for the upstream trigger and target evidence.
- [HD2 offline engine harness](../hd2-offline-engine-harness/SKILL.md) for offline fake-engine tests; use the AutoChat sources and tests linked above as product evidence.
