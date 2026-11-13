# The Design Skills Architecture

<https://github.com/devbyshima/design-skills>

## Introduction

Design Skills is a collection of Agent Skills for things people look at. Each skill is a folder with a `SKILL.md`: YAML frontmatter whose `description` is the trigger an agent harness matches on, and a body of steps the agent follows. They install with `npx skills@latest add devbyshima/design-skills`, or as a Claude Code plugin through `.claude-plugin/plugin.json`.

There is one skill so far, under `skills/slides/`. `one-idea-slides` turns a talk written as one JSON file into a PowerPoint deck in the style of the Ijwi Demo Day deck. A Python builder lays every slide out, checks it, writes the `.pptx` and speaker notes, and draws PNG previews so the agent can look at what it made. CI runs the skill's tests and publishes a release for each tag; nothing is built.

## What Design Skills is NOT

- Design Skills is not an app, a theme or a template file. It is Agent Skills: Markdown, with the Python each skill needs to check and preview its work.
- It does not ship fonts, photos or icons. A skill names what to install and where to get it.
- A release is not what installs read. Installs read the repository at `HEAD`; a tag only marks a snapshot.

## Major Components

### Skills [MARKDOWN]

#### [skills/slides](skills/slides)

The slide-deck category. Its `README.md` lists each skill under User-invoked or Model-invoked.

#### [skills/slides/one-idea-slides](skills/slides/one-idea-slides)

`SKILL.md`: pin the talk, write the script, write `deck.json`, check, preview, hand over. `references/style.md` holds the style's rules and sizes, running orders, languages and printing; `references/spec.md` the JSON format and every check; `assets/example-deck.json` a made-up pitch that uses every slide kind.

### Deck builder [PYTHON]

#### [skills/slides/one-idea-slides/scripts](skills/slides/one-idea-slides/scripts)

`build_deck.py`: `load` reads the spec, `walked` expands step walk-throughs, and `layout_deck` turns each slide kind (`k_title`, `k_number`, `k_steps` and the rest, listed in `KINDS`) into text, picture, film and shade items on a 1920 x 1080 px grid. It checks them as it goes: `check_fields` (unknown fields), `check_text` (line breaks, measured by `Measure`), `check_overlaps` (margins and overlaps), sources, placeholders, contrast and talk time. `write_pptx` draws the items with python-pptx and `render_png` draws the same items with Pillow for the previews. `notes_markdown` writes the speaker notes with each speaker's time; `WORDS` and `language` hold the builder's own words per language. `--check` needs only the standard library.

#### [skills/slides/one-idea-slides/tests](skills/slides/one-idea-slides/tests)

`test_scripts.py` (unittest): notes and timing parsing, crops, walk-throughs, credits, French words, every check and malformed specs on the standard library; with python-pptx, building the example deck, pictures cropped, rounded and graded, CMYK photos and language tags, and a film with its poster (that one needs ffmpeg).

### Plugin [JSON]

#### [.claude-plugin](.claude-plugin)

`plugin.json`: the `devbyshima-design-skills` plugin, its version and licence, and the `skills` array naming every skill's folder.

### Repository assets [PNG, SVG]

#### [.github/assets](.github/assets)

The README's banner (`banner-light.svg`, `banner-dark.svg`) and, under `slides/`, its slide previews: slides of `assets/example-deck.json` drawn by `build_deck.py --preview` and scaled to 1280 x 720.

## External Pieces

- **Agent Skills** ([agentskills.io](https://agentskills.io)): the `SKILL.md` format with `name` and `description` frontmatter.
- **The `skills` CLI** (vercel-labs/skills): finds `skills/<category>/<name>/SKILL.md` and installs from the repository; the README's badge is from skills.sh.
- **Claude Code plugins:** `.claude-plugin/plugin.json`.
- **python-pptx** (with Pillow): writes the decks; installed by the user, and by CI for the tests. **ffmpeg**, optional, gives films a poster frame.
- **Fonts:** the slide style defaults to Inter (SIL Open Font License), which the user installs; none is bundled.
- **GitHub Actions:** `actions/checkout`, `actions/setup-python` and `softprops/action-gh-release`.

## Tooling

`scripts/list-skills.sh` prints every skill's name and description; `scripts/link-skills.sh` symlinks every skill into `~/.claude/skills` and `~/.agents/skills`, so a `git pull` updates them. Both skip `skills/deprecated/`. `.github/workflows/test.yml` installs python-pptx and runs every `skills/**/tests/test_scripts.py` on pushes to `main` and on pull requests; `.github/workflows/release.yml` runs them again and publishes a release on a `v*` tag.

# Workflows

## What does a deck look like?

1. The user asks for a pitch or talk deck, and the agent loads `one-idea-slides` by its description.
2. It settles the audience, slot, speakers, language and sources, writes the script beat by beat, and writes `deck.json`, one slide kind per beat, starting from `assets/example-deck.json`.
3. `python scripts/build_deck.py deck.json --check` reports errors and warnings (lines that run long, overlaps, numbers without a source, `[?]` placeholders, notes whose words don't fit their time).
4. `python scripts/build_deck.py deck.json --preview preview/` writes `deck.pptx`, the speaker notes and a PNG per slide with `contact.png`; the agent reads the contact sheet, fixes and rebuilds, then hands over the deck with what's left to fill.

## What does the Development flow look like?

A new skill goes in `skills/<category>/<name>/` with a `SKILL.md`, and is registered in `.claude-plugin/plugin.json`, the category's `README.md`, the root README's Reference list and this file. `bash scripts/list-skills.sh` checks it is found, and a skill that ships scripts gets a `tests/test_scripts.py`. The steps are in [CONTRIBUTING.md](CONTRIBUTING.md) and, for agents, [CLAUDE.md](CLAUDE.md).

## What does the Release flow look like?

Changes people would notice are noted under `Unreleased` in [CHANGELOG.md](CHANGELOG.md) as they land. A release dates that section and bumps `plugin.json`'s `version` in one pull request; then a `v*` tag on the merge commit makes `release.yml` run the skill tests and publish a GitHub Release with generated notes. Installs keep reading `HEAD`, so a release only tags a snapshot.

# Invariants

Things the repository relies on that are easy to break:

- **Registration:** a skill is wired in four places, `plugin.json`'s `skills`, its category README, the root README and this file. One left out of `plugin.json` is missing from the Claude Code plugin.
- **Frontmatter:** every `SKILL.md` has `name` and `description`, and the description is the trigger.
- **Self-contained:** scripts resolve paths from their own location, so skills work wherever they are installed.
- **One layout, two drawings:** `build_deck.py` lays a slide out once; `write_pptx` and `render_png` must draw every item type (`text`, `image`, `video`, `rect`) the same way, or the previews stop telling the truth about the deck.
- **Standard library first:** `--check` and the layout tests run without python-pptx or Pillow, so neither is imported at the top of `build_deck.py` or its tests.
- **Test location:** CI finds tests only at `skills/**/tests/test_scripts.py`.
- **Retiring:** a skill is retired by moving it under `skills/deprecated/`, which both scripts skip.
- **Kept out of git:** `node_modules/`, `scripts/.cache/` and lockfiles (`.gitignore`).

## License

Design Skills is source-available under the [PolyForm Noncommercial License 1.0.0](LICENSE): free for non-commercial use.
