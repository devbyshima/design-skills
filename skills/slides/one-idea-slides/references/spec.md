# deck.json

One JSON file describes the whole deck. Paths to pictures and films are relative to the JSON file. [assets/example-deck.json](../assets/example-deck.json) uses every kind.

## Contents

- [Top level](#top-level)
- [Theme](#theme)
- [Fields every slide takes](#fields-every-slide-takes)
- [Kinds](#kinds)
- [Placeholders](#placeholders)
- [References and credits](#references-and-credits)
- [What the builder writes and checks](#what-the-builder-writes-and-checks)

## Top level

```json
{
  "title": "Kibo pitch",
  "minutes": 5,
  "theme": { "preset": "dark", "font": "Inter" },
  "references": [ ... ],
  "credits": [ "Music: Name, licence." ],
  "slides": [ ... ]
}
```

- `minutes`: the slot. The checker warns when the notes' times add up to more, or to far less.
- `references_notes`: presenter notes for the reference list the builder adds.
- Keys starting with `_` are ignored, so `"_about"` can hold a note to yourself. Any other key the builder doesn't know gets a warning, with the nearest one it does ("did you mean 'caption'?").

## Theme

| Key | Default | |
|---|---|---|
| `preset` | `dark` | `dark` or `light` (for printing, bright rooms, or a light brand) |
| `font` | `Inter` | the font family name as PowerPoint lists it |
| `page`, `text`, `muted`, `accent`, `dim`, `placeholder` | see [style.md](style.md#colour) | `#RRGGBB` |
| `font_files` | none | `{"regular": "fonts/X-Regular.ttf", "bold": "fonts/X-Bold.ttf"}`: the files the preview measures with, when the font isn't installed |

`"theme": "light"` is short for `{"preset": "light"}`. Changing `accent` on the light preset needs a colour dark enough for a light page; the checker warns below 3:1 contrast.

## Fields every slide takes

| Field | |
|---|---|
| `kind` | required: one of the kinds below |
| `notes` | presenter notes: `"Ana · about 15 s\nWhat she says.\n\nIf asked ...: backup."` The first line can also be `Ana | 15 s` or `Ana - 15 s`. See [style.md](style.md#presenter-notes) |
| `label` | a small section label at the top left ("How it works") |
| `caption` | a small muted line: under the content, under the text column on `steps` and `split`, under the picture on `list` |
| `cite` | the sources: a key, or a list of keys (`"survey"`, `["survey", "trial"]`); the source line at the foot. `"cite": []` says a number has no source on purpose (an ask, a target, your own count) |
| `credit` | who made this slide's picture; the reference list gets "Slide N: ..." with the right number |
| `transition` | `fade` (default), `fade-slow`, `dissolve` or `cut` |
| `page` | this slide's ground: a token (`"accent"`) or `#RRGGBB` |
| `title` | the slide's name in the speaker-notes file (the builder picks one otherwise) |

Text fields take `\n` for a line break you choose. The bottom strip is shared: the caption sits at y 920 and the source line at y 990, and `media` moves its head and tail up to make room.

## Kinds

### title

```json
{ "kind": "title", "logo": "logo.png", "text": "How bees\nsee colour", "sub": "Ana Mugisha, class 4B" }
```

`logo` and `sub` are optional. Break a long talk title by hand; it may take two lines at 170 px. `logo_size`: `[w, h]` box in px, default `[400, 260]`. `size`: the name's px size.

### number

```json
{ "kind": "number", "number": "1 in 4", "text": "doses spoil before they arrive.", "cite": ["survey"] }
```

`number` can be a word ("Ethan") or a year. Up to about nine characters fit at the automatic size; put units in the line under it ("110" / "ms at p99"). `size` overrides the size; `color` the accent.

### numbers

```json
{ "kind": "numbers", "numbers": [ { "number": "300", "text": "images a second for a bee" }, { "number": "60", "text": "for us" } ],
  "highlight": 1 }
```

Two to four, spread across the margins. Sizes: 220 px for two, 160 for three, 110 for four; keep each number to about 6, 5 and 5 characters. All numbers are in the accent unless `highlight` (1-based) picks one, which leaves the others in the text colour. A number can also take its own `color` (a token or hex). `size` overrides.

### statement

```json
{ "kind": "statement", "text": "Most speak\nwith their hands." }
```

`size` (default 96), `width` (default 1500), `color`.

### split

```json
{ "kind": "split", "text": "Today's tools make\nthe child learn\nthe tool.", "image": "stock/tools.jpg", "focus": [0.62, 0.5] }
```

The photo fills 800 x 840 px at the right with rounded corners. `image_side`: `"left"` swaps them. `mono` (default true, so stock photos match; set `false` when colour is the point), `focus` (`[x, y]` fractions of the photo to keep in view), `alt` (shown on the placeholder), `size` (default 64).

### photo

```json
{ "kind": "photo", "image": "photos/in-use.jpg", "text": "Kibo keeps them cold for five days.", "focus": [0.5, 0.6] }
```

Full-bleed, on black. `text` is optional; with it, a dark fade rises from the bottom (`"shade": false` drops it). `mono` default false.

### steps

```json
{ "kind": "steps", "label": "How it works", "walk": true,
  "steps": [ { "head": "Charge it in the sun.", "tail": "Four hours on the roof.", "image": "screens/charge.png",
               "notes": "Ben · about 8 s\nFirst, it charges in the sun," },
             { "head": "Load the doses.", "tail": "Up to 300.", "image": "screens/load.png",
               "notes": "Ben · about 5 s\nthen the nurse loads the doses," },
             { "head": "Carry it out.", "image": "screens/carry.png", "notes": "Ben · about 6 s\nand carries it out." } ] }
```

- `walk: true` makes one slide per step, that step lit, each with its own `image` or `video`, `notes`, `credit` and `title`, and a dissolve between them. This is the usual way to show a process.
- Without `walk`, `active` (1-based) lights one step and dims the rest; leave both out to show every step lit.
- Steps can be plain strings. Three to five steps read well; more get closer together and a warning.
- The picture sits in a 780 x 900 box on the right, shown whole with rounded corners (`radius`, default 28). `"fit": "cover"` fills the box instead, cropped on `focus`. `mono` grades it.

### columns

```json
{ "kind": "columns", "label": "What powers it", "numbered": false, "mono": true,
  "columns": [ { "image": "renders/core.png", "head": "The cold core.", "tail": "Cells that hold 4 °C." },
               { "image": "renders/lid.png", "head": "The lid.", "tail": "A solar panel." } ] }
```

One to four, spread across the margins; the pictures stand on one line, heads and tails under them. `mono`, `radius`, `fit` and `focus` on the slide apply to every column, and a column can override them. `numbered: true` adds a big muted number under each picture. A column can have `video` instead of `image`. Heads can take two lines; with four columns, keep heads to about 14 characters and break long identifiers in the tail by hand.

### media

```json
{ "kind": "media", "image": "renders/band.png", "head": "The sensor.", "tail": "Nano 33 BLE Sense." }
{ "kind": "media", "video": "films/reveal.mp4", "full": true, "transition": "fade-slow" }
```

One picture (`image`) or film (`video`, with optional `poster`), as large as the slide allows, with its head and tail right under it. `full: true` fills the slide on black. `mono`, `radius` (default 28), `fit`, `focus` and `alt` as for `steps`.

### tiles

```json
{ "kind": "tiles", "text": "We start with vaccines. Then everything cold.", "highlight": 1,
  "tiles": [ { "image": "stock/vaccines.jpg", "caption": "Vaccines: first", "credit": "Photo: A. Name, Unsplash" },
             { "image": "stock/insulin.jpg", "caption": "Insulin", "focus": [0.6, 0.5] } ] }
```

Two to six tall photo tiles, black and white (`"mono": false` keeps colour). `highlight` (1-based) puts that caption in the accent.

### team

```json
{ "kind": "team", "people": [ { "name": "Ana", "role": "Lead", "photo": "team/ana.jpg", "focus": [0.5, 0.3] } ] }
```

One to six. Portraits are cut to 4:5 with the face about a third down; set `focus` per person to adjust. Names take one line: about 12 characters with five or six people.

### list

```json
{ "kind": "list", "items": [ "Pilot with us.", "Mentor us.", "Fund 50 boxes." ], "image": "qr.png",
  "caption": "kibo.example/join" }
```

Big numbered lines, centred as a block, with an optional square picture (a QR code) to the right and its `caption` under it. At 100 px beside a QR code, keep each line to about 17 characters; the checker warns when the block runs past the margins. `numbered: false` drops the numbers; `size` overrides.

Make the QR code with any generator and keep its white border (the quiet zone) on a dark page.

### closing

```json
{ "kind": "closing", "text": "Merci.", "sub": "Des questions ?" }
```

Defaults: "Thank you." and "Questions?". `"sub": ""` leaves only the thanks.

### custom

For a slide the kinds don't cover. Items are placed in px on the 1920 x 1080 grid, drawn in order. Keep words inside x 140 to 1780.

```json
{ "kind": "custom", "items": [
  { "type": "image", "path": "before.jpg", "x": 0, "y": 0, "w": 960, "h": 1080, "fit": "cover", "alt": "before" },
  { "type": "rect", "x": 0, "y": 700, "w": 1920, "h": 380, "color": "#000000", "opacity": [0, 0.9] },
  { "type": "text", "text": "Before", "x": 480, "y": 960, "w": 800, "size": 60, "align": "center", "anchor": "bottom" }
] }
```

| type | fields (defaults) |
|---|---|
| `text` | `text`, `x` (left edge, or the centre with `"align": "center"`), `y` (top, middle or bottom per `anchor`, default top), `w` (1640), `size` (44), `color` (token or hex, default `text`), `bold` (true), `italic`, `align` (left), `lines` (3: how many lines before the checker warns) |
| `image` | `path`, `x`, `y`, `w`, `h`, `fit` (`contain`, or `cover`), `focus`, `radius` (0), `mono` (false), `alt`, `credit` |
| `video` | `path`, `x`, `y`, `w`, `h`, `poster` |
| `rect` | `x`, `y`, `w`, `h`, `color` (default `text`), `opacity` (1, or `[top, bottom]` for a fade) |

Custom slides skip the words-on-screen and overlap checks; line and margin checks still run.

## Placeholders

Write `[?]` wherever a fact, name or source is still missing: `"number": "[?]"`, `"author": "[?]"`. The checker lists every `[?]` left, by slide and field, so the hand-over can name them. A picture whose file doesn't exist yet shows as a grey PHOTO box with its `alt`.

## References and credits

```json
"references": [
  { "key": "survey", "cite": "Health Office, 2025", "author": "Health Office", "year": "2025",
    "title": "Cold chain survey of rural clinics.", "source": "Example Health Office",
    "url": "https://example.org/cold-chain-survey" }
]
```

- `cite` is what the slide's source line shows; `author`, `year`, `title`, `source` (set in italics) and `url` make the entry: `[n] Author (Year) Title. Source.` A reference with no author or title gets a warning.
- `entry` instead writes the whole entry as given, for a citation style such as APA: `"entry": "Tautz, J. (2008). The buzz about bees. Springer."`. `url` still goes under it.
- A source still to find: `{ "key": "market", "cite": "[?]", "entry": "[?] Survey of phone ownership among maize farmers." }`; the checker lists it.
- Citing a key that isn't listed is an error; a listed reference nobody cites goes at the end, with a warning.
- Put `credit` on the slide, tile, person, column or step whose picture it is. The builder writes "Slide N: credit" lines on the reference list with the slide's final number. Top-level `credits` are extra lines as written.
- With any references or credits, a reference list is added as the last slide, over as many slides as it needs. Put `{ "kind": "references" }` where you want it instead; `text` renames it.

## What the builder writes and checks

```bash
python <skill>/scripts/build_deck.py deck.json [-o out.pptx] [--preview DIR] [--check]
```

- `deck.pptx`: 16:9 slides, each with its background, pictures, words, presenter notes and transition. Words are text boxes and pictures are pictures, so everything stays editable in PowerPoint.
- `deck speaker notes.md`: every slide's speaker, time, words on screen, spoken words and backup, with a table of speaking time per speaker.
- With `--preview DIR`: `slide-01.png` ... and `contact.png`, all slides on one sheet.
- `--check` writes nothing; it exits 1 on errors.

Errors stop the build: an unknown kind, a missing or malformed field, a citation with no reference, a bad colour. Warnings say what to fix and where:

- words: a line longer than its room, a word wider than its box, a word alone on a last line, too many words on screen;
- placement: words past the side of the slide, words over a picture or over other words, a list wider than the margins;
- facts: a number with no source, `[?]` placeholders left, references never cited;
- talk: missing notes, notes without a speaker and time, more or far fewer spoken words than the time allows (about 130 a minute), a total over the `minutes`;
- setup: unknown fields, missing files, a font that isn't installed, theme colours with too little contrast.
