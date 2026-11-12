# The one-idea style

The rules behind the deck, with the numbers the builder uses. They come from the Ijwi Demo Day deck, built in Keynote and shown at a 2026 demo day; the builder redraws its layouts for PowerPoint.

## Contents

- [The idea](#the-idea)
- [Grid](#grid)
- [Colour](#colour)
- [Type](#type)
- [Words on the slide](#words-on-the-slide)
- [Numbers](#numbers)
- [Pictures and films](#pictures-and-films)
- [Sources](#sources)
- [Presenter notes](#presenter-notes)
- [Transitions](#transitions)
- [Other languages](#other-languages)
- [Printing](#printing)
- [Running orders](#running-orders)
- [Before you hand it over](#before-you-hand-it-over)

## The idea

The room listens to the speaker and glances at the slide. A slide that needs reading competes with the speaker and loses both. So each slide holds one idea that lands in about three seconds: a number, a name, a sentence, a picture. The speaker carries the argument; the slide marks where it is.

## Grid

The slide is 1920 x 1080 px (13.33 x 7.5 in; one px is half a point).

| Place | Where |
|---|---|
| Side margin for words | 140 px (keep words between x 140 and 1780) |
| Section label ("How it works") | top left, y 100, 40 px bold, muted |
| Caption | y 920, 30 px regular, muted: centred, or under the text column, or under a QR code |
| Source line | left, y 990, 24 px regular, muted |
| Picture corners | 28 px radius on every picture but full-bleed ones and `custom` items |

The main content sits on the slide's middle line; a number and its line are centred as one block.

## Colour

Five tokens and one accent.

| Token | Dark (default) | Light | Used for |
|---|---|---|---|
| `page` | #171717 | #FBFBFD | the ground |
| `text` | #F5F5F7 | #1D1D1F | what's read |
| `muted` | #86868B | #6E6E73 | labels, captions, sources, "Questions?" |
| `accent` | #FDFC9B | #0071E3 | the one thing to look at |
| `dim` | #48484A | #C7C7CC | steps not yet lit |

- The accent goes on one thing per slide: the number, the lit step's number, the highlighted tile's caption. Never on a whole sentence. On a `numbers` slide where one number is the point, `highlight` it and the others go to the text colour.
- Change the accent to the product's own colour when it has one (Ijwi's yellow was sampled from its app). On the light preset it must be dark enough for a light page: the checker wants 3:1 against the page for the accent and muted, 4.5:1 for text.
- Full-bleed photos and films sit on black whatever the theme, and words over a photo stay light.

## Type

One family. Bold for everything read from the back of the room, regular for small lines (tails, captions, sources, references).

| Role | Size (px) |
|---|---|
| Name on the title slide | 170 |
| One big number or word | 300 (2 characters), 280 (up to 4), 220 (longer, about 9 at most) |
| Two, three, four numbers side by side | 220, 160, 110 (lines under them: 52, 44, 34) |
| "Thank you." | 150 |
| A list of asks | 100 (up to 3), 80 (up to 5), 64 (more) |
| Statement | 96 |
| Sentence beside a photo | 64 |
| Sentence over a photo | 60 |
| Line under one number | 52 |
| Step or column head | 44 |
| Section label, picture head | 40 |
| Step tail, caption | 30 |
| Source line | 24 |
| Reference entry, its address | 22, 16 |

Line height is 1.12. When words don't fit, cut words; don't drop a size. The reference list is small on purpose: it's there for whoever gets the file, not for the room.

The Ijwi deck used Cursor Gothic (a commercial font by Kimera). Inter is a free stand-in with the same plain, wide shapes. A system font (SF Pro, Helvetica Neue, Segoe UI) only works if the presenting computer has it too.

## Words on the slide

- One short sentence, or a fragment that finishes the number above it ("10" / "seconds. No words.").
- Eight words or fewer reads in a glance; fifteen is the ceiling the checker allows.
- No bullets, no paragraphs, no "Agenda".
- End sentences with a full stop, including "Thank you." Fragments under a number read as one sentence with the number.
- Break long lines by hand where the sense breaks ("Most speak\nwith their hands.", "How bees\nsee colour"), and never leave one word alone on the last line; the checker warns.
- A step list says what to do, in the imperative: "Name the movement." "Show the movement." "Do it."
- Put the speaker's words on the slide only when it's the line to remember.

## Numbers

- A number earns a slide when it changes what the room thinks. Pair two when the contrast is the point ("2 speech therapists" / "70+ children").
- Round so the claim stays true ("70+", "1 in 4", "1.25M").
- Units go in the line under the number ("110" / "ms at p99"), so the number stays short.
- Give a person's name before a crowd's number: "Ethan" then "50,000".
- Every number has a source on the slide's foot. An ask, a target or your own count has none: write `"cite": []` so the checker knows it's on purpose, and say in the notes where it comes from.

## Pictures and films

- **Sets read as one.** Stock photos, team photos and anything side by side get the same treatment: black and white, contrast stretched, rounded corners (`mono` is on by default for `split`, `tiles` and `team`). The steps are the same for each photo, so the results only match when the photos are alike: pick portraits with similar backgrounds and light.
- **Colour when colour is the point.** Turn `mono` off for a photo whose colour matters (`"mono": false`), and keep one treatment for a photo that comes back on several slides.
- **The product is in colour**, large: full-bleed (`photo`) or alone on black (`media` with `full`).
- **Screenshots and diagrams** keep their corners rounded. On the dark theme, export diagrams on a dark or transparent ground; a white diagram becomes a glaring block. Or give that slide `"page": "#FBFBFD"`.
- **Crop on the subject** with `focus` (fractions across and down). Pictures beside steps or in columns are shown whole unless `"fit": "cover"`. Faces sit about a third from the top (`team` does this by default).
- **Reveal with a film.** A short film of the product turning out of the dark, on black, with a slower fade into it. Films start on a click (see SKILL.md).
- **Show a process as one picture that changes**: a `steps` slide with `walk`, one step lit each time, a dissolve between them.
- Credit pictures that aren't yours with `credit` on the slide or entry; the reference list numbers them.
- Until a picture exists, leave its path in: a grey PHOTO box with its `alt` stands in.

## Sources

- On a slide with a claim: `Source: Author, Year` (or `Sources: A, 2024; B, 2026`) at the foot, muted.
- The last slide is the reference list, numbered in the order the talk first cites them: `[n] Author (Year) Title. Source.` with the source in italics and the address on the line below. If a teacher or journal wants APA or Harvard, write the whole entry in `entry` the way they want it; the builder adds only its number.

## Presenter notes

Each slide's notes start with one line naming the speaker and the time, then the words, then backup:

```text
Ana · about 15 s
In the clinics we surveyed, one dose in four spoils on the way.

If asked how it was measured: temperature loggers in 40 cool boxes over one month.
```

- First line: the name, then `·`, `|` or ` - `, then the time in any words: `about 15 s`, `environ 1 min 10`, `1:30`, `2 min`, or `not counted` (`non compté`) for a demo or a pause.
- A slide two people share: `Élodie et Marie-Hélène · 30 s` (also `&`, `and`, `,`) splits the time between them. Better still, give each their own slide.
- First paragraph: what the speaker says, word for word, as they'd say it. The checker compares it with the time at about 130 words a minute (`words_per_minute` changes that: slower for a nervous speaker or a slower language).
- Later paragraphs: answers to likely questions ("If asked ..."), stage directions ("Click when the film stops"), and where a number comes from.

The presenter view shows the first line and the spoken paragraph. The speaker-notes Markdown has everything, with each speaker's total time, so a team can rehearse to the clock.

## Transitions

| Move | Transition |
|---|---|
| Between slides | fade through black, 0.75 s (`fade`, the default) |
| Into a reveal or the product's first picture | fade through black, 1 s (`fade-slow`) |
| Between steps of one sequence | dissolve, fast (`dissolve`, automatic with `walk`) |
| Into a slide that continues exactly | none (`cut`) |

PowerPoint stores a transition on the slide being entered, so set `transition` on the slide that appears.

## Other languages

- Set `"lang": "fr"` (or `"fr-FR"`): PowerPoint then checks spelling in that language, and the builder writes its own words in it ("Source : ", "Références", "Merci.", the notes file). English and French are built in; for others, give `"words"` (see the `WORDS` table in the builder for the keys).
- Write numbers the language's way ("27 000 €", "38 %"), with a no-break space (U+00A0) inside them so they never split. Avoid the narrow no-break space (U+202F): many fonts draw it almost zero wide.

## Printing

For slides that will be printed or read on paper, use the light preset, skip full-bleed photos with a fade (the black fade prints as a dark slab), and print only the last slide of each `walk` (the others repeat it).

## Running orders

**A pitch** (the Ijwi talk, about five minutes plus a two-minute demo, four speakers):

1. **Title**: logo and name.
2. **An experience**: ask the room to do something for ten seconds ("10" / "seconds. No words.").
3. **A person**: one name and one line about them.
4. **Scale**: one or two numbers, sourced.
5. **The gap**: what today's tools get wrong, beside a photo of them.
6. **Reveal**: the product, a film on black, then a photo of it in use.
7. **How it works**: three steps, walked through.
8. **Proof**: how often it works, as numbers.
9. **Demo**, live or filmed.
10. **What's next**: limits today and what comes next.
11. **Vision**: a year and a line ("2030" / "Affordable. Across Rwanda.").
12. **Who else**: the same thing for more people, as photo tiles.
13. **Team**: photos, names, roles.
14. **The ask**: three short asks, a QR code to the waitlist.
15. **Thank you.** / Questions?
16. **References.**

For three minutes keep 1, 3, 4, 6, 7, 8, 14 and 15, about 20 seconds each.

**A technical talk** (one speaker, 15 to 30 minutes): title; the result as one number ("1,200 ms"); why it mattered; the cause as one statement; before and after (`numbers` with `highlight`, or `custom`); each change as a `walk` step with its picture; the evidence (a chart as a picture, one line under it); what you'd do differently; three takeaways as a `list`; thank you; references. Many slides, still one idea each.

## Before you hand it over

- [ ] Each slide says one thing; the checker reports no line, margin or overlap warnings.
- [ ] Every number has a source or `"cite": []`; no number was made up; no `[?]` is left, or the user knows each one.
- [ ] The accent marks one thing per slide.
- [ ] Photos are cropped on their subject; sets are graded alike.
- [ ] Every slide has notes with a speaker and a time, the words fit the time, and the total fits `minutes`.
- [ ] The contact sheet reads as one deck: same margins, same sizes, same colours.
