---
name: one-idea-slides
description: Make a presentation in a calm keynote style as a PowerPoint (.pptx) file - one idea per slide on a dark (or light) page, big numbers in one accent colour, sourced claims, photos graded alike, and the whole script with timings in the presenter notes. Use when the user wants a pitch deck, demo day deck, talk, lecture or class slides "like a keynote" or "like Apple's", or asks for slides like the Ijwi deck. Writes a JSON spec, builds it with python-pptx, checks it, and draws PNG previews of every slide.
license: PolyForm-Noncommercial-1.0.0
---

# One-idea slides

A deck where each slide says one thing a listener takes in within three seconds, and the speaker says the rest. Modelled on the Ijwi Demo Day deck: a near-black page, white bold words, soft yellow for the one thing to look at, a source line at the foot, and a script with who speaks and for how long.

You write the talk as `deck.json`; `scripts/build_deck.py` in this skill's folder lays out every slide on a 1920 x 1080 grid, checks it, and writes the `.pptx`, a speaker-notes Markdown file and PNG previews. Below, `<skill>` stands for this skill's folder.

## Setup

```bash
pip install python-pptx            # brings Pillow
```

- **Font.** The default is Inter (free: rsms.me/inter or Google Fonts). It has to be on the computer that presents, not only the one that builds. Set `theme.font` to another font only if that computer has it.
- **ffmpeg** (optional) gives films a poster frame.

## Workflow

### 1. Pin the talk

Ask, in one round, whatever the user hasn't said: the audience, the slot in minutes, who speaks, the language, the one thing the room should remember, the ask, whether it will be printed, and which photos, films, logos and sources they have.

Never invent a number, quote or source. Write `[?]` where one is missing (`"number": "[?]"`); the checker lists every `[?]` left, and you list them for the user.

### 2. Write the script before the slides

Beat by beat: who says it, about how long, and the words (about 130 spoken words a minute). Each beat becomes one slide; a beat that needs two ideas becomes two slides. Running orders for a pitch and a technical talk are in [references/style.md](references/style.md#running-orders).

### 3. Write deck.json

Copy [assets/example-deck.json](assets/example-deck.json) and replace its content. Set `minutes`, and `lang` if the talk isn't in English. Pick a kind per slide:

| kind | for |
|---|---|
| `title` | logo and name, optional line under it |
| `number` | one big number or word, a short line under it |
| `numbers` | two to four numbers side by side, optionally one lit |
| `statement` | one sentence, large, centred |
| `split` | a sentence on the left, a photo on the right |
| `photo` | a full-bleed photo, optional sentence at the bottom left |
| `steps` | numbered steps; with `walk`, one slide per step, each lit in turn with its own picture |
| `columns` | one to four pictures with a head and a tail line each |
| `media` | one picture or film with a caption, or full-bleed |
| `tiles` | a sentence over a row of photo tiles, one highlighted |
| `team` | photos with name and role |
| `list` | big numbered asks, a QR code beside them |
| `closing` | "Thank you." and "Questions?" |
| `custom` | anything else, placed in px |

Fields, notes format, references, credits, languages and themes: [references/spec.md](references/spec.md).

### 4. Check

```bash
python <skill>/scripts/build_deck.py deck.json --check
```

Fix every error. Treat warnings as real: shorten words rather than shrinking type, add sources, fix notes whose words don't fit their time. Warnings about unknown fields usually mean a typo.

### 5. Build and look

```bash
python <skill>/scripts/build_deck.py deck.json --preview preview/
```

Read `preview/contact.png`, then any slide that looks off at full size (`preview/slide-07.png`). The checker catches words that overflow, overlap or cross the margins; your eyes catch the rest: photos cropped off their subject, a set of photos that doesn't match, a slide that says two things. Fix and rebuild until it reads cleanly. The preview is Pillow's drawing of the same layout, close to PowerPoint's but not identical.

### 6. Hand over

Give the user the `.pptx` and the speaker-notes `.md`, and tell them:

- each `[?]` still to fill, and each grey PHOTO / VIDEO placeholder to replace;
- films play on a click; for one that should start by itself, select it in PowerPoint and set Playback > Start > Automatically;
- to install the deck's font on the presenting computer, or embed it (PowerPoint: Save options > Embed fonts);
- for printing: see [style.md](references/style.md#printing).

## The style in brief

The full rules, with sizes and reasons, are in [references/style.md](references/style.md).

- One idea a slide. On screen, a short sentence or a number and a line; everything else goes in the notes.
- One family, bold for what's read, regular for small lines. No bullets.
- One accent colour, only on the thing to look at.
- Sets of photos graded alike with rounded corners; the product in colour, full-bleed.
- Every claim names its source at the foot; the last slide lists them, numbered in order of first use.
- Fade through black between slides; dissolve between steps of one sequence.

## Limits

- No charts or tables: show the one number that matters with `number` or `numbers`, or a chart as a picture.
- Keynote may refuse files written by python-pptx. Open the deck in PowerPoint or Google Slides; Keynote users can export from there.
- Films start on a click until set to start automatically in PowerPoint.
