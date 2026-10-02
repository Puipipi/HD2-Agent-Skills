# HD2 Agent Skills

Agent skills for driving **Helldivers 2** unattended on Windows — launching the game,
reaching the ship, and entering a mission with a known loadout, with verifiable
evidence at each step.

These skills exist because the game gives no automation API: an agent has to work
through window focus, synthetic input, in-game menus, and mod logs. Every coordinate,
key sequence and failure mode here was verified in real runs.

## Skills

| Skill | Purpose |
|---|---|
| [`hd2-mission-entry`](skills/hd2-mission-entry/SKILL.md) | Cold start to boots-on-ground: launch, skip intro, confirm ship readiness, star-map mission selection, briefing loadout, deploy, and the evidence to confirm each step. |

## Usage

Point your agent/skill loader at `skills/`, or copy a skill folder into your agent's
skill directory. Each skill is a self-contained `SKILL.md` with frontmatter
(`name`, `description`).

## Conventions

- Coordinates are **logical pixels** on a 1707x1067 layout (the game runs at a
  non-100% DPI scale, so physical = logical x scale).
- Input injection always verifies the **target window is foreground** before sending.
- Every step has a **log evidence line or screenshot** to confirm it actually happened.

## License

MIT
