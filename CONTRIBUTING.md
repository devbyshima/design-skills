# Contributing

This repo is a collection of [Agent Skills](https://agentskills.io) for design work. Each skill is a self-contained folder discovered by the [`skills` CLI](https://github.com/vercel-labs/skills).

## Add a skill

1. **Pick (or create) a category** under `skills/`, e.g. `skills/slides/`, `skills/icons/`, `skills/motion/`. Categories are just folders; group by what the skill *makes*.

2. **Create the skill folder** with at least a `SKILL.md`:

   ```
   skills/<category>/<skill-name>/
     SKILL.md          # required
     scripts/          # optional: executable helpers (python, node, ...)
     references/       # optional: docs the agent reads on demand
     assets/           # optional: examples and templates
     tests/            # required if it ships scripts
   ```

3. **Write `SKILL.md`** with YAML frontmatter. `name` and `description` are required (the description is the trigger the agent matches on, so make it specific). Keep the body lean and push detail into `references/`.

   ```markdown
   ---
   name: my-skill
   description: Use when the user wants to ...  (be specific: this is the trigger)
   license: PolyForm-Noncommercial-1.0.0
   ---

   # My Skill
   ```

4. **Let the agent see its work.** A design skill should give the agent a preview it can look at and checks that say what's wrong, in words it can act on ("'colour' sits alone on the last line"). Rules it can't check, it won't follow.

5. **Keep it self-contained.** Scripts resolve paths relative to their own location so the skill works wherever it's installed. Optional dependencies degrade gracefully and are documented. Don't bundle fonts, photos or icons whose licence doesn't allow it.

6. **Test it.** CI (`.github/workflows/test.yml`) runs every `skills/**/tests/test_scripts.py`, after installing python-pptx. Tests that need a heavier tool should skip when it's missing.

7. **Register it in four places:**
   - [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json): add the skill path to the `skills` array
   - `skills/<category>/README.md`: add it under **User-invoked** or **Model-invoked**
   - root [`README.md`](README.md): add a bullet to the Reference list (one short sentence)
   - [`ARCHITECTURE.md`](ARCHITECTURE.md): its folders under Major Components

   Then `bash scripts/list-skills.sh` to confirm it's discovered.

## Conventions

- One concern per skill; name folders in `kebab-case`.
- Prefer the standard library and tools the user already has; document any extra dependency.
- Don't commit `node_modules/`, build output or lockfiles (see `.gitignore`).
- If a skill is adapted from another project, keep the original license/attribution in the skill folder.
- **Retire** a skill by moving it under `skills/deprecated/` (with a note) rather than deleting it.

## Install a skill while developing

The `skills` CLI accepts a local path, so you can test discovery before pushing:

```bash
npx skills add /path/to/this/repo            # discovers all skills
npx skills add /path/to/this/repo --skill my-skill
```

Or symlink every skill so a `git pull` keeps them current, and list what is discovered:

```bash
bash scripts/link-skills.sh    # into ~/.claude/skills and ~/.agents/skills
bash scripts/list-skills.sh    # name and description of each skill
```

## Releasing

Installs read the repo at `HEAD`, so a release is only for tagging a snapshot.

1. As changes land, add each one people using the skills would notice under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md).
2. To release, rename that heading to the version and today's date (`## [0.2.0] - YYYY-MM-DD`), put a new empty `## [Unreleased]` above it, update the compare links at the bottom, and bump `version` in `.claude-plugin/plugin.json` to match. Merge it through a pull request.
3. Tag the merge commit and push the tag. `.github/workflows/release.yml` runs the tests and publishes a GitHub Release with auto-generated notes:

```bash
git tag v0.2.0
git push origin v0.2.0
```
