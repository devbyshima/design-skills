# CLAUDE.md

Instructions for an agent working **in this repo** (it's a collection of Agent Skills for design, not an app).

## Layout

```
skills/<category>/<name>/SKILL.md   # each skill, a self-contained folder (categories: slides, ...)
.claude-plugin/plugin.json          # plugin manifest (lists every skill path)
scripts/list-skills.sh              # list all skills
scripts/link-skills.sh              # symlink skills into ~/.claude/skills & ~/.agents/skills for local dev
CHANGELOG.md                        # every change people would notice, newest first; new ones go under Unreleased
ARCHITECTURE.md                     # map of the repo; update it when a skill, folder or invariant changes
```

## Adding or changing a skill

1. Put it at `skills/<category>/<name>/` with a `SKILL.md` (`name` + `description` frontmatter required; the description is the trigger, so make it specific). Push detail into `references/`; keep the body lean (progressive disclosure).
2. Keep it **self-contained**: scripts resolve paths from their own location (`os.path.dirname(__file__)`), heavy deps are optional and degrade gracefully. Add a `tests/` folder if it ships scripts.
3. A design skill needs a way to **see the result**: a preview the agent can read (PNG, contact sheet) and checks that name what's wrong. Taste the agent can't check is taste it won't follow.
4. Wire it up in **four places**:
   - `.claude-plugin/plugin.json`: add the skill path to the `skills` array
   - `skills/<category>/README.md`: add it under User-invoked or Model-invoked
   - root `README.md`: add a bullet to the Reference list
   - `ARCHITECTURE.md`: add its folders under Major Components
5. `bash scripts/list-skills.sh` to sanity-check discovery; run the skill's tests (`python3 skills/<category>/<name>/tests/test_scripts.py`).
6. Add a line under `## [Unreleased]` in `CHANGELOG.md` for anything people using the skill would notice.

## Conventions

- `kebab-case` folder names; one concern per skill.
- Keep `README.md` concise and minimal: a short intro, Install, Why use it?, and a Reference list with one bullet and one short sentence per skill. Detail goes in the skill or its category README.
- Never bundle a font, photo or icon set whose licence doesn't allow it; point to where to get it.
- Don't commit `node_modules/`, `scripts/.cache/`, build output or lockfiles (see `.gitignore`).
- Retire a skill by moving it under `skills/deprecated/` rather than deleting it.
- If a skill is adapted from another project, keep that project's license/attribution in the skill folder.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the human-facing version.
