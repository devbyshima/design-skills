#!/usr/bin/env python3
"""Build a one-idea-a-slide deck as a PowerPoint file from a JSON spec.

    python build_deck.py deck.json                 # deck.pptx and "deck speaker notes.md" beside it
    python build_deck.py deck.json -o talk.pptx
    python build_deck.py deck.json --preview out/  # also a PNG per slide and out/contact.png
    python build_deck.py deck.json --check         # report problems, write nothing

Writing the .pptx needs python-pptx (pip install python-pptx), which brings
Pillow. --check runs on the standard library alone, with estimated line breaks.

Every slide is laid out on a 1920 x 1080 grid of pixels; a pixel is half a
point, so a 13.33 x 7.5 inch slide. The layout is computed once and drawn
twice: into the .pptx, and with Pillow into the preview PNGs.
"""

import argparse
import difflib
import io
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

W, H = 1920, 1080
EMU_PER_PX = 6350          # 12,192,000 EMU across 1920 px
MARGIN = 140               # left and right margin of words
LABEL_Y = 100              # a section label at the top left
CAPTION_Y = 920            # a small line under a slide's content
SOURCE_Y = 990             # the source line at the foot
LH = 1.12                  # line height, as a multiple of the font size
RADIUS = 28                # corners of photos and placeholders
PHOTO_TEXT = "#F5F5F7"     # words over a photo stay light on any theme
LONGEST = 3840             # pictures are scaled down to this many px on the long side

PRESETS = {
    "dark": dict(page="#171717", text="#F5F5F7", muted="#86868B", accent="#FDFC9B", dim="#48484A",
                 placeholder="#2C2C2E", font="Inter"),
    "light": dict(page="#FBFBFD", text="#1D1D1F", muted="#6E6E73", accent="#0071E3", dim="#C7C7CC",
                  placeholder="#E8E8ED", font="Inter"),
}
COLOUR_TOKENS = ("page", "text", "muted", "accent", "dim", "placeholder")

TRANSITIONS = {
    "fade": '<p:transition {ns} spd="med"><p:fade thruBlk="1"/></p:transition>',
    "fade-slow": '<p:transition {ns} spd="slow"><p:fade thruBlk="1"/></p:transition>',
    "dissolve": '<p:transition {ns} spd="fast"><p:dissolve/></p:transition>',
    "cut": None,
}

# The words the builder writes itself, per language; "words" in deck.json overrides any of them.
WORDS = {
    "en": dict(source="Source: ", sources="Sources: ", references="Reference list", nd="n.d.", thanks="Thank you.",
               questions="Questions?", notes_file="speaker notes",
               notes_intro="The same script as the presenter notes, with the backup lines.",
               talk="About {t} of talk, plus pauses between slides.", speaker="Speaker", time="Speaking time",
               all="All", on_screen="On screen", backup="Backup", film="a film", picture="a picture",
               nothing="nothing"),
    "fr": dict(source="Source : ", sources="Sources : ", references="Références", nd="s. d.", thanks="Merci.",
               questions="Des questions ?", notes_file="notes de présentation",
               notes_intro="Le même texte que les notes de l'orateur, avec les réponses en réserve.",
               talk="Environ {t} de parole, plus les pauses entre les diapositives.", speaker="Intervenant",
               time="Temps de parole", all="Total", on_screen="À l'écran", backup="En réserve", film="un film",
               picture="une image", nothing="rien"),
}
LANG_TAGS = {"en": "en-US", "fr": "fr-FR", "de": "de-DE", "es": "es-ES", "pt": "pt-PT", "it": "it-IT", "nl": "nl-NL",
             "rw": "rw-RW", "sw": "sw-KE"}
UNTIMED = ("not counted", "non compté", "non compte", "untimed")
TOP_FIELDS = {"title", "minutes", "theme", "references", "credits", "slides", "references_notes", "lang", "words",
              "words_per_minute"}


def language(deck):
    """(the deck's words, its language tag for PowerPoint, its base language)."""
    lang = str(deck.get("lang") or "en")
    base = lang.split("-")[0].lower()
    words = dict(WORDS.get(base, WORDS["en"]), **(deck.get("words") or {}))
    return words, (lang if "-" in lang else LANG_TAGS.get(base, lang)), base


# Kinds whose words the "one short sentence" check counts.
TERSE = {"title", "number", "numbers", "statement", "split", "photo", "media", "closing"}
TERSE_WORDS = 15


class SpecError(Exception):
    pass


# ---------------------------------------------------------------- measuring


FONT_DIRS = [Path.home() / "Library/Fonts", Path("/Library/Fonts"), Path("/System/Library/Fonts"),
             Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path.home() / ".fonts",
             Path.home() / ".local/share/fonts", Path("C:/Windows/Fonts"),
             Path.home() / "AppData/Local/Microsoft/Windows/Fonts"]


def _norm(s):
    return re.sub(r"[\s_\-]", "", s).lower()


class Measure:
    """Text widths in px, from the theme's font when Pillow can find it,
    otherwise estimated from the number of characters."""

    # stand-ins for the preview when the theme's font isn't installed
    FALLBACKS = ("Helvetica Neue", "Helvetica", "Arial", "Segoe UI", "DejaVu Sans", "Liberation Sans")

    def __init__(self, family, files=None):
        self.family = family
        self.files = files or {}
        self.faces = None          # {(bold, italic): (path, index, variation or None)}
        self.stand_in = None       # the family used instead, if the theme's isn't installed
        self.cache = {}
        try:
            from PIL import ImageFont  # noqa: F401
            self.pil = True
        except ImportError:
            self.pil = False

    def _scan(self):
        self.faces = {}
        for style, path in self.files.items():
            b, i = "bold" in style, "italic" in style
            self.faces[(b, i)] = (str(path), 0, None)
        if self.faces:
            return
        self.faces = self._faces(self.family)
        if not self.faces:
            for fam in self.FALLBACKS:
                self.stand_in = fam
                self.faces = self._faces(fam)
                if self.faces:
                    return
            self.stand_in = "Pillow's default"

    def _faces(self, family):
        from PIL import ImageFont
        faces = {}
        want = _norm(family)
        stem = want[:5]
        seen = set()
        for d in FONT_DIRS:
            if not d.is_dir():
                continue
            for p in d.rglob("*"):
                if p.suffix.lower() not in (".ttf", ".otf", ".ttc") or stem not in _norm(p.stem) or p in seen:
                    continue
                seen.add(p)
                for index in range(16 if p.suffix.lower() == ".ttc" else 1):
                    try:
                        f = ImageFont.truetype(str(p), 20, index=index)
                    except OSError:
                        break
                    fam, style = f.getname()
                    if _norm(fam or "") != want:
                        continue
                    st = (style or "").lower()
                    bold, italic = "bold" in st, "italic" in st or "oblique" in st
                    plain = st in ("regular", "bold", "italic", "bold italic", "roman")
                    key = (bold, italic)
                    if key not in faces or plain:
                        faces[key] = (str(p), index, None)
                    try:
                        names = [n.decode() if isinstance(n, bytes) else n for n in f.get_variation_names()]
                    except Exception:
                        names = []
                    for n in names:
                        nl = n.lower()
                        k = ("bold" in nl and "semi" not in nl and "extra" not in nl,
                             "italic" in nl)
                        if nl in ("regular", "bold", "italic", "bold italic") and k not in faces:
                            faces[k] = (str(p), index, n)
        return faces

    @property
    def found(self):
        """Pillow has a font to measure with: the theme's, or a stand-in."""
        if not self.pil:
            return False
        if self.faces is None:
            self._scan()
        return bool(self.faces)

    @property
    def missing(self):
        """The theme's font isn't installed here."""
        if not self.pil:
            return False
        if self.faces is None:
            self._scan()
        return self.stand_in is not None

    def font(self, size, bold=False, italic=False):
        """A Pillow font for the theme's family, or a stand-in."""
        from PIL import ImageFont
        key = (round(size), bold, italic)
        if key in self.cache:
            return self.cache[key]
        f = None
        if self.found:
            face = (self.faces.get((bold, italic)) or self.faces.get((bold, False))
                    or self.faces.get((False, False)) or next(iter(self.faces.values())))
            path, index, variation = face
            f = ImageFont.truetype(path, round(size), index=index)
            if variation:
                try:
                    f.set_variation_by_name(variation)
                except Exception:
                    pass
        if f is None:
            try:
                f = ImageFont.load_default(size=round(size))
            except TypeError:
                f = ImageFont.load_default()
        self.cache[key] = f
        return f

    def width(self, text, size, bold=False, italic=False):
        if self.pil:
            return self.font(size, bold, italic).getlength(text)
        return len(text) * size * (0.55 if bold else 0.52)

    def wrap(self, text, size, width, bold=False, italic=False):
        """Lines as PowerPoint would break them, near enough: greedy, on spaces."""
        lines = []
        for para in text.split("\n"):
            cur = ""
            for word in para.split(" "):
                trial = f"{cur} {word}" if cur else word
                if cur and self.width(trial, size, bold, italic) > width:
                    lines.append(cur)
                    cur = word
                else:
                    cur = trial
            lines.append(cur)
        return lines


# ---------------------------------------------------------------- primitives


def text(s, x, y, w, size, color, *, bold=True, italic=False, align="left", anchor="top", lines=1, role="main",
         runs=None):
    """Words in a box w px wide; y is its top, middle or bottom (anchor)."""
    return dict(t="text", text=str(s), x=x, y=y, w=w, size=size, color=color, bold=bold, italic=italic,
                align=align, anchor=anchor, max_lines=lines, role=role, runs=runs)


def ctext(s, cx, y, w, size, color, **kw):
    """Words centred on cx."""
    return text(s, cx - w / 2, y, w, size, color, align="center", **kw)


def picture(path, x, y, w, h, *, fit="cover", focus=(0.5, 0.5), radius=0, mono=False, label="", valign="middle"):
    return dict(t="image", path=path, x=x, y=y, w=w, h=h, fit=fit, focus=tuple(focus), radius=radius, mono=mono,
                label=label, valign=valign)


def film(path, x, y, w, h, *, poster=None, label=""):
    return dict(t="video", path=path, x=x, y=y, w=w, h=h, poster=poster, label=label)


def shade(x, y, w, h, color="#000000", alpha=(0, 0.92)):
    """A box of one colour, its opacity running from alpha[0] at the top to alpha[1] at the bottom."""
    return dict(t="rect", x=x, y=y, w=w, h=h, color=color, alpha=alpha)


def cover_crop(iw, ih, w, h, focus=(0.5, 0.5)):
    """Fractions (left, top, right, bottom) to cut off a picture so it fills w x h, keeping focus in view."""
    fx, fy = focus
    ai, ab = iw / ih, w / h
    if ai > ab:
        keep = ab / ai
        left = min(max(fx - keep / 2, 0), 1 - keep)
        return left, 0.0, 1 - keep - left, 0.0
    keep = ai / ab
    top = min(max(fy - keep / 2, 0), 1 - keep)
    return 0.0, top, 0.0, 1 - keep - top


def contain_box(iw, ih, x, y, w, h, valign="middle"):
    """Where a picture iw x ih sits when scaled to fit inside the box."""
    s = min(w / iw, h / ih)
    dw, dh = iw * s, ih * s
    dy = {"top": 0, "middle": (h - dh) / 2, "bottom": h - dh}[valign]
    return x + (w - dw) / 2, y + dy, dw, dh


# ---------------------------------------------------------------- the spec


def load(path):
    path = Path(path)
    try:
        deck = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SpecError(f"{path}: not valid JSON ({e})")
    if not isinstance(deck, dict) or not isinstance(deck.get("slides"), list):
        raise SpecError(f'{path}: needs an object with a "slides" list')
    deck["_base"] = path.resolve().parent
    deck["_name"] = path.stem
    return deck


def theme_of(deck):
    t = deck.get("theme") or {}
    if isinstance(t, str):
        t = {"preset": t}
    preset = t.get("preset", "dark")
    if preset not in PRESETS:
        raise SpecError(f"theme preset {preset!r}: use one of {', '.join(PRESETS)}")
    th = dict(PRESETS[preset], **{k: v for k, v in t.items() if k != "preset"})
    for k in COLOUR_TOKENS:
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(th[k])):
            raise SpecError(f"theme {k} {th[k]!r}: write colours as #RRGGBB")
    return th


def luminance(h):
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def light_page(th):
    return luminance(th["page"]) > 0.5


class Ctx:
    """What a slide's layout needs: the theme, measuring, and somewhere to put problems."""

    def __init__(self, deck, theme, measure):
        self.deck, self.th, self.m = deck, theme, measure
        self.base = deck["_base"]
        self.problems = []   # (level, slide number or None, message)
        self.words = language(deck)[0]
        self.n = None

    def warn(self, msg):
        self.problems.append(("warning", self.n, msg))

    def error(self, msg):
        self.problems.append(("error", self.n, msg))

    def path(self, p):
        if not p:
            return None
        q = Path(p).expanduser()
        return q if q.is_absolute() else self.base / q

    def colour(self, v, default):
        if v is None:
            return default
        if v in self.th and v in COLOUR_TOKENS:
            return self.th[v]
        if re.fullmatch(r"#[0-9A-Fa-f]{6}", str(v)):
            return v
        self.error(f"colour {v!r}: use #RRGGBB or one of {', '.join(COLOUR_TOKENS)}")
        return default

    def focus(self, v, default=(0.5, 0.5)):
        """[x, y] fractions of a picture to keep in view."""
        if v is None:
            return default
        if (isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(n, (int, float)) for n in v)
                and all(0 <= n <= 1 for n in v)):
            return tuple(v)
        self.error(f"focus {v!r}: write [x, y], fractions from 0 to 1, e.g. [0.5, 0.3]")
        return default

    def lines(self, s, size, w, bold=True):
        return len(self.m.wrap(str(s), size, w, bold))


def stack(parts, middle=540):
    """parts: (height, gap after, make(top) -> items). Places them top to bottom, the block's middle at middle."""
    total = sum(h for h, _, _ in parts) + sum(g for _, g, _ in parts[:-1])
    y = middle - total / 2
    out = []
    for h, gap, make in parts:
        out += make(y)
        y += h + gap
    return out


# ---------------------------------------------------------------- slide kinds
# Each returns the slide's items. Sizes and places come from the deck this
# style is modelled on; the preview shows whether a change still sits right.


def k_title(s, c):
    th, parts = c.th, []
    size = s.get("size", 170)
    if s.get("logo"):
        lw, lh = s.get("logo_size", [400, 260])
        logo = c.path(s["logo"])
        parts.append((lh, 40, lambda y: [picture(logo, 960 - lw / 2, y, lw, lh, fit="contain", label="logo")]))
    n = c.lines(s["text"], size, 1640)
    parts.append((n * size * LH, 6, lambda y: [ctext(s["text"], 960, y, 1640, size, th["text"], lines=2)]))
    if s.get("sub"):
        parts.append((48 * LH, 0, lambda y: [ctext(s["sub"], 960, y, 1640, 48, th["muted"], bold=False, lines=2)]))
    return stack(parts)


def number_size(num):
    return 300 if len(num) <= 2 else 280 if len(num) <= 4 else 220


def k_number(s, c):
    th = c.th
    num = str(s["number"])
    size = s.get("size") or number_size(num)
    parts = [(size * LH, 0, lambda y: [ctext(num, 960, y, 1700, size, c.colour(s.get("color"), th["accent"]))])]
    if s.get("text"):
        n = c.lines(s["text"], 52, 1600)
        parts.append((n * 52 * LH, 0, lambda y: [ctext(s["text"], 960, y, 1600, 52, th["text"], lines=2)]))
    return stack(parts, 530)


NUMBER_SIZES = {2: (220, 52), 3: (160, 44), 4: (110, 34)}   # the numbers' and their lines' px sizes


def k_numbers(s, c):
    th = c.th
    stats = s["numbers"]
    if len(stats) not in NUMBER_SIZES:
        c.error(f'"numbers" takes 2 to 4 numbers, not {len(stats)}')
        return []
    k = len(stats)
    step = (W - 2 * MARGIN) / k
    cxs = [MARGIN + step * (i + 0.5) for i in range(k)]
    cw = min(step - 60, 640)
    nsize, lsize = NUMBER_SIZES[k]
    nsize = s.get("size", nsize)
    hl = s.get("highlight")
    n = max(c.lines(st.get("text", ""), lsize, cw) for st in stats)
    items = []
    for i, (cx, st) in enumerate(zip(cxs, stats)):
        col = c.colour(st.get("color"), th["accent"] if hl in (None, i + 1) else th["text"])
        items += stack([(nsize * LH, 0, lambda y, cx=cx, st=st, col=col: [ctext(st["number"], cx, y, cw, nsize, col)]),
                        (n * lsize * LH, 0, lambda y, cx=cx, st=st: [ctext(st.get("text", ""), cx, y, cw, lsize,
                                                                           th["text"], lines=2)])], 530)
    return items


def k_statement(s, c):
    size = s.get("size", 96)
    return [ctext(s["text"], 960, 540, s.get("width", 1500), size, c.colour(s.get("color"), c.th["text"]),
                  anchor="middle", lines=4)]


def k_split(s, c):
    th = c.th
    iw, ih = 800, 840
    right = s.get("image_side", "right") != "left"
    ix = W - MARGIN - iw if right else MARGIN
    tx = MARGIN if right else MARGIN + iw + 80
    return [text(s["text"], tx, 540, 760, s.get("size", 64), th["text"], anchor="middle", lines=6),
            picture(c.path(s["image"]), ix, 120, iw, ih, focus=c.focus(s.get("focus")), radius=RADIUS,
                    mono=s.get("mono", True), label=s.get("alt", ""))]


def k_photo(s, c):
    items = [picture(c.path(s["image"]), 0, 0, W, H, focus=c.focus(s.get("focus")), mono=s.get("mono", False),
                     label=s.get("alt", ""))]
    if s.get("text"):
        if s.get("shade", True):
            items.append(shade(0, 440, W, 640))
        items.append(text(s["text"], MARGIN, 960, W - 2 * MARGIN, s.get("size", 60), PHOTO_TEXT, anchor="bottom",
                          lines=2))
    return items


def media_item(s, c, x, y, w, h, valign="middle", parent=None):
    """The picture or film of s, fitted inside the box ("fit": "cover" fills it, cropped on "focus").
    Settings missing from s come from parent (a column's from its slide)."""
    parent = parent or {}

    def get(k, default):
        return s.get(k, parent.get(k, default))

    if s.get("video"):
        return film(c.path(s["video"]), x, y, w, h, poster=c.path(s.get("poster")), label=s.get("alt", ""))
    fit = get("fit", "contain")
    if fit not in ("contain", "cover"):
        c.error(f'fit {fit!r}: use "contain" or "cover"')
        fit = "contain"
    if fit == "contain" and s.get("focus") is not None:
        c.warn('focus only crops with "fit": "cover"; the picture is shown whole')
    return picture(c.path(s["image"]), x, y, w, h, fit=fit, focus=c.focus(get("focus", None)),
                   radius=get("radius", RADIUS), mono=get("mono", False), label=s.get("alt", ""), valign=valign)


def k_steps(s, c):
    th = c.th
    steps = [st if isinstance(st, dict) else {"head": st} for st in s["steps"]]
    active = s.get("active")
    if active is not None and not (isinstance(active, int) and 1 <= active <= len(steps)):
        c.error(f"active {active!r}: the number of a step, 1 to {len(steps)}")
        active = None
    media = s.get("image") or s.get("video")
    hw = 720 if media else W - 2 * MARGIN - 60
    if len(steps) > 5:
        c.warn(f"{len(steps)} steps read as a list: keep to three to five, or split the slide")
    step = min(150, 700 / max(len(steps) - 1, 1))   # more steps sit closer
    top = max(540 - ((len(steps) - 1) * step + 44 * LH) / 2, 210 if s.get("label") else 80)
    items = []
    for i, st in enumerate(steps):
        y = top + i * step
        on = active is None or active == i + 1
        num = th["muted"] if active is None else th["accent"] if on else th["dim"]
        items += [text(str(i + 1), MARGIN, y, 60, 44, num),
                  text(st["head"], MARGIN + 60, y, hw, 44, th["text"] if on else th["dim"])]
        if on and st.get("tail"):
            items.append(text(st["tail"], MARGIN + 60, y + 62, hw, 30, th["muted"], bold=False, lines=2))
    if media:
        items.append(media_item(s, c, 1000, 90, 780, 900))
    return items


def k_columns(s, c):
    th = c.th
    cols = s["columns"]
    n = len(cols)
    if not 1 <= n <= 4:
        c.error(f'"columns" takes 1 to 4 columns, not {n}')
        return []
    stepx = (W - 2 * MARGIN) / n if n > 1 else 1000
    numbered = s.get("numbered", False)
    ih = 390 if numbered else 510
    heads = max(c.lines(col["head"], 44, stepx - 40) for col in cols)
    tails = max(c.lines(col.get("tail", ""), 32, stepx - 40, bold=False) if col.get("tail") else 0 for col in cols)
    block = ih + 36 + (88 * LH + 20 if numbered else 0) + min(heads, 2) * 44 * LH + (14 + tails * 32 * LH if tails else 0)
    top = max(540 - block / 2, 170 if s.get("label") else 80)
    items = []
    for i, col in enumerate(cols):
        cx = 960 + (i - (n - 1) / 2) * stepx
        y = top
        if col.get("image") or col.get("video"):
            items.append(media_item(col, c, cx - (stepx - 60) / 2, y, stepx - 60, ih, valign="bottom", parent=s))
        y += ih + 36
        if numbered:
            items.append(ctext(str(i + 1), cx, y, 200, 88, th["muted"]))
            y += 88 * LH + 20
        items.append(ctext(col["head"], cx, y, stepx - 40, 44, th["text"], lines=2))
        y += min(heads, 2) * 44 * LH + 14
        if col.get("tail"):
            items.append(ctext(col["tail"], cx, y, stepx - 40, 32, th["muted"], bold=False, lines=2))
    return items


def k_media(s, c):
    th = c.th
    if s.get("full"):
        if s.get("video"):
            return [film(c.path(s["video"]), 0, 0, W, H, poster=c.path(s.get("poster")), label=s.get("alt", ""))]
        return [picture(c.path(s["image"]), 0, 0, W, H, focus=c.focus(s.get("focus")), mono=s.get("mono", False),
                        label=s.get("alt", ""))]
    top = 170 if s.get("label") else 80
    bottom = SOURCE_Y - 20 if cites_of(s) else 1000
    if s.get("caption"):
        bottom = min(bottom, CAPTION_Y - 20)
    words = (40 * LH + 10 if s.get("head") else 0) + (28 * LH if s.get("tail") else 0)
    pic = media_item(s, c, MARGIN, top, W - 2 * MARGIN, bottom - top - (words + 28 if words else 0))
    items = [pic]
    y = picture_box(pic)[3] + 28
    if s.get("head"):
        items.append(ctext(s["head"], 960, y, 1600, 40, th["text"]))
        y += 40 * LH + 10
    if s.get("tail"):
        items.append(ctext(s["tail"], 960, y, 1600, 28, th["muted"], bold=False))
    return items


def k_list(s, c):
    th = c.th
    lines = s["items"]
    n = len(lines)
    if not isinstance(lines, list) or not lines:
        c.error('"items" must be a list of one or more lines')
        return []
    size = s.get("size") or (100 if n <= 3 else 80 if n <= 5 else 64)
    numbered = s.get("numbered", True)
    gap = round(1.36 * size) if numbered else 0
    step = round(1.5 * size)
    widest = max(c.m.width(str(line), size, True) for line in lines)
    block = gap + widest
    side = 440 if s.get("image") else 0
    total = block + (150 + side if side else 0)
    if total > W - 2 * MARGIN:
        c.warn(f"the list is {round(total - (W - 2 * MARGIN))} px wider than the margins allow at {size} px"
               f"{' beside the picture' if side else ''}: shorten the longest line")
    x0 = 960 - total / 2
    items = []
    for i, line in enumerate(lines):
        y = 540 + (i - (n - 1) / 2) * step
        if numbered:
            items.append(text(str(i + 1), x0, y, gap, size, th["muted"], anchor="middle"))
        items.append(text(line, x0 + gap, y, widest * 1.1 + 20, size, th["text"], anchor="middle"))
    if side:
        items.append(picture(c.path(s["image"]), x0 + block + 150, 540 - side / 2, side, side, fit="contain",
                             label=s.get("alt", "QR code")))
    return items


def k_tiles(s, c):
    th = c.th
    tiles = s["tiles"]
    n = len(tiles)
    if not 2 <= n <= 6:
        c.error(f'"tiles" takes 2 to 6 tiles, not {n}')
        return []
    tg = 30
    tw = min(300, (W - 2 * MARGIN - (n - 1) * tg) / n)
    th_ = round(tw * 520 / 300)
    line = s.get("text")
    lsize = 64
    line_h = c.lines(line, lsize, 1640) * lsize * LH + 90 if line else 0
    top = (H - (line_h + th_ + 30 + 30 * LH)) / 2
    x0 = (W - (n * tw + (n - 1) * tg)) / 2
    hl = s.get("highlight")
    items = [ctext(line, 960, top, 1640, lsize, th["text"], lines=2)] if line else []
    for i, tile in enumerate(tiles):
        x = x0 + i * (tw + tg)
        on = hl == i + 1
        items += [picture(c.path(tile.get("image")), x, top + line_h, tw, th_, focus=c.focus(tile.get("focus")),
                          radius=RADIUS, mono=s.get("mono", True), label=tile.get("caption", "")),
                  ctext(tile.get("caption", ""), x + tw / 2, top + line_h + th_ + 30, tw + tg, 30,
                        th["accent"] if on else th["muted"], bold=on, role="caption")]
    return items


def k_team(s, c):
    th = c.th
    people = s["people"]
    n = len(people)
    if not 1 <= n <= 6:
        c.error(f'"team" takes 1 to 6 people, not {n}')
        return []
    gap = 64 if n <= 4 else 48
    pw = 320 if n <= 4 else (W - 2 * MARGIN - (n - 1) * gap) / n
    bh = round(pw * 1.25)
    y0 = (H - (bh + 115)) / 2
    left = (W - (n * pw + (n - 1) * gap)) / 2
    items = []
    for i, p in enumerate(people):
        x = left + i * (pw + gap)
        cx = x + pw / 2
        items += [picture(c.path(p.get("photo")), x, y0, pw, bh, focus=c.focus(p.get("focus"), (0.5, 0.35)), radius=RADIUS,
                          mono=s.get("mono", True), label=p["name"]),
                  ctext(p["name"], cx, y0 + bh + 28, pw + gap - 10, 40, th["text"]),
                  ctext(p.get("role", ""), cx, y0 + bh + 86, pw + gap - 10, 26, th["muted"], bold=False, lines=2)]
    return items


def k_closing(s, c):
    th = c.th
    t, sub = s.get("text", c.words["thanks"]), s.get("sub", c.words["questions"])
    if not sub:
        return [ctext(t, 960, 540, 1640, 150, th["text"], anchor="middle")]
    return [ctext(t, 960, 560, 1640, 150, th["text"], anchor="bottom"),
            ctext(sub, 960, 600, 1640, 64, th["muted"], anchor="top")]


def k_custom(s, c):
    th, items = c.th, []
    for it in s["items"]:
        kind = it.get("type")
        if kind == "text":
            items.append(text(it["text"], it["x"], it["y"], it.get("w", 1640), it.get("size", 44),
                              c.colour(it.get("color"), th["text"]), bold=it.get("bold", True),
                              italic=it.get("italic", False), align=it.get("align", "left"),
                              anchor=it.get("anchor", "top"), lines=it.get("lines", 3), role="custom"))
            if items[-1]["align"] == "center":
                items[-1]["x"] -= items[-1]["w"] / 2
        elif kind == "image":
            items.append(picture(c.path(it["path"]), it["x"], it["y"], it["w"], it["h"], fit=it.get("fit", "contain"),
                                 focus=c.focus(it.get("focus")), radius=it.get("radius", 0),
                                 mono=it.get("mono", False), label=it.get("alt", "")))
        elif kind == "video":
            items.append(film(c.path(it["path"]), it["x"], it["y"], it["w"], it["h"], poster=c.path(it.get("poster"))))
        elif kind == "rect":
            a = it.get("opacity", 1)
            items.append(shade(it["x"], it["y"], it["w"], it["h"], c.colour(it.get("color"), th["text"]),
                               tuple(a) if isinstance(a, list) else (a, a)))
        else:
            c.error(f"custom item type {kind!r}: use text, image, video or rect")
    return items


KINDS = {
    "title": (k_title, ("text",)), "number": (k_number, ("number",)), "numbers": (k_numbers, ("numbers",)),
    "statement": (k_statement, ("text",)), "split": (k_split, ("text", "image")), "photo": (k_photo, ("image",)),
    "steps": (k_steps, ("steps",)), "columns": (k_columns, ("columns",)), "media": (k_media, ()),
    "list": (k_list, ("items",)), "tiles": (k_tiles, ("tiles",)), "team": (k_team, ("people",)),
    "closing": (k_closing, ()), "custom": (k_custom, ("items",)), "references": (None, ()),
}
DARK_GROUND = {"photo"}   # kinds that sit on black, so a missing photo or the edges stay dark


COMMON = {"kind", "notes", "label", "caption", "cite", "transition", "page", "title", "credit"}
FIELDS = {
    "title": {"text", "sub", "logo", "logo_size", "size"},
    "number": {"number", "text", "size", "color"},
    "numbers": {"numbers", "size", "highlight"},
    "statement": {"text", "size", "width", "color"},
    "split": {"text", "image", "image_side", "mono", "focus", "alt", "size"},
    "photo": {"image", "text", "focus", "mono", "alt", "shade", "size"},
    "steps": {"steps", "active", "walk", "image", "video", "poster", "alt", "fit", "focus", "radius", "mono"},
    "columns": {"columns", "numbered", "mono", "radius", "fit", "focus"},
    "media": {"image", "video", "poster", "full", "head", "tail", "alt", "mono", "radius", "fit", "focus"},
    "list": {"items", "image", "alt", "size", "numbered"},
    "tiles": {"tiles", "text", "highlight", "mono"},
    "team": {"people", "mono"},
    "closing": {"text", "sub"},
    "custom": {"items"},
    "references": {"text"},
}
ENTRY_FIELDS = {   # (slide field, the fields of each entry in it)
    "numbers": ("numbers", {"number", "text", "color"}),
    "steps": ("steps", {"head", "tail", "image", "video", "poster", "alt", "notes", "title", "transition", "cite",
                        "credit"}),
    "columns": ("columns", {"head", "tail", "image", "video", "poster", "alt", "mono", "radius", "fit", "focus",
                            "credit"}),
    "tiles": ("tiles", {"image", "caption", "focus", "credit"}),
    "team": ("people", {"name", "role", "photo", "focus", "credit"}),
}
CUSTOM_FIELDS = {
    "text": {"type", "text", "x", "y", "w", "size", "color", "bold", "italic", "align", "anchor", "lines"},
    "image": {"type", "path", "x", "y", "w", "h", "fit", "focus", "radius", "mono", "alt", "credit"},
    "video": {"type", "path", "x", "y", "w", "h", "poster"},
    "rect": {"type", "x", "y", "w", "h", "color", "opacity"},
}


def check_fields(c, s, kind):
    """Say which fields the builder doesn't know, with the nearest one it does."""
    def unknown(keys, allowed, where):
        for k in keys:
            if k.startswith("_") or k in allowed:
                continue
            near = difflib.get_close_matches(k, sorted(allowed), n=1)
            hint = f" (did you mean {near[0]!r}?)" if near else ""
            c.warn(f"{where} has no field {k!r}, so it does nothing{hint}")

    unknown(s, COMMON | FIELDS[kind], kind)
    if kind in ENTRY_FIELDS:
        field, allowed = ENTRY_FIELDS[kind]
        for e in s.get(field) or []:
            if isinstance(e, dict):
                unknown(e, allowed, f"each of {kind}'s {field}")
    if kind == "custom" and isinstance(s.get("items"), list):
        for it in s["items"]:
            if isinstance(it, dict) and it.get("type") in CUSTOM_FIELDS:
                unknown(it, CUSTOM_FIELDS[it["type"]], f"a custom {it['type']}")


def credits_of(s):
    """The picture credits a slide gives, in order."""
    if not isinstance(s, dict):
        return []
    out = [s["credit"]] if s.get("credit") else []
    for field in ("tiles", "people", "columns", "items"):
        for e in s.get(field) or [] if isinstance(s.get(field), list) else []:
            if isinstance(e, dict) and e.get("credit"):
                out.append(e["credit"])
    return out


# ---------------------------------------------------------------- references


def cites_of(s):
    v = s.get("cite", []) if isinstance(s, dict) else []
    return [v] if isinstance(v, str) else list(v) if isinstance(v, list) else []


def ref_order(deck, c):
    refs = deck.get("references") or []
    if not isinstance(refs, list):
        c.error('"references" must be a list of objects')
        refs = []
    by_key = {}
    for r in refs:
        if not isinstance(r, dict) or "key" not in r:
            c.error('each reference needs a "key"')
            continue
        by_key[r["key"]] = r
        if not r.get("entry") and (not r.get("author") or not r.get("title")):
            c.warn(f"reference {r['key']!r} has no {'author' if not r.get('author') else 'title'}")
    order = []
    for n, s in enumerate(deck["slides"], 1):
        for k in cites_of(s):
            if k not in by_key:
                c.problems.append(("error", n, f"cites {k!r}, which is not in references"))
            elif k not in order:
                order.append(k)
    uncited = [k for k in by_key if k not in order]
    if uncited:
        c.problems.append(("warning", None, f"never cited, so listed at the end: {', '.join(uncited)}"))
        order += uncited
    return [by_key[k] for k in order], {k: i for i, k in enumerate(order, 1)}


def cite_line(s, refs, number, words):
    keys = list(dict.fromkeys(k for k in cites_of(s) if k in number))
    if not keys:
        return None
    names = "; ".join(refs[number[k] - 1].get("cite") or refs[number[k] - 1].get("author", k) for k in keys)
    return (words["sources"] if len(keys) > 1 else words["source"]) + names


def reference_pages(s, refs, credits, c):
    """The Reference list, over as many slides as it needs."""
    th = c.th
    title = s.get("text", c.words["references"])
    pages, items, y = [], [], 180

    def new_page():
        return [text(title, MARGIN, 90, 1640, 56, th["text"])]

    items = new_page()
    for n, r in enumerate(refs, 1):
        if r.get("entry"):   # the whole entry as written, in whatever citation style is wanted
            plain, italic = f"[{n}] {r['entry']}", ""
        else:
            plain = f"[{n}] {r.get('author', '')} ({r.get('year') or c.words['nd']}) {r.get('title', '')}".rstrip()
            italic = f"{r['source']}." if r.get("source") else ""
        full = plain + (" " if italic else "") + italic
        rows = c.lines(full, 22, 1650, bold=False)
        url = re.sub(r"^https?://(www\.)?", "", r.get("url", ""))
        need = rows * 22 * LH + (16 * LH if url else 0) + 26
        if y + need > 1010 and len(items) > 1:
            pages.append(items)
            items, y = new_page(), 180
        items.append(text(full, MARGIN, y, 1650, 22, th["text"], bold=False, lines=rows, role="ref",
                          runs=[(plain + (" " if italic else ""), False), (italic, True)] if italic else None))
        y += rows * 22 * LH + 6
        if url:
            items.append(text(url, MARGIN, y, 1650, 16, th["muted"], bold=False, role="ref"))
            y += 16 * LH
        y += 20
    for line in credits:
        if y + 18 * LH > 1040:
            pages.append(items)
            items, y = new_page(), 180
        items.append(text(line, MARGIN, y, 1650, 18, th["muted"], bold=False, lines=2, role="ref"))
        y += c.lines(line, 18, 1650, False) * 18 * LH + 6
    pages.append(items)
    return pages


# ---------------------------------------------------------------- notes


HEAD_RE = re.compile(r"^(?P<who>[^\n·|]+?)\s*(?:·|\|| - )\s*(?P<time>.*(?:\d|not counted).*)$")


def split_notes(notes):
    """(speaker, timing, spoken lines, backup lines). The first line names the
    speaker and time ("Ana · about 20 s"); the first paragraph is what they say;
    later paragraphs are backup (If asked..., sources, stage directions)."""
    notes = (notes or "").strip()
    if not notes:
        return None, None, [], []
    head, _, rest = notes.partition("\n")
    m = HEAD_RE.match(head.strip())
    if not m:
        rest, who, timing = notes, None, None
    else:
        who, timing = m["who"].strip(), m["time"].strip()
    blocks = rest.strip().split("\n\n")
    spoken = [line.strip() for line in blocks[0].split("\n") if line.strip()] if blocks else []
    backup = [line.strip() for b in blocks[1:] for line in b.split("\n") if line.strip()]
    return who, timing, spoken, backup


def untimed(timing):
    return any(u in (timing or "").lower() for u in UNTIMED)


def seconds(timing):
    """Seconds in a timing like "about 20 s", "1:30", "2 min", "1 min 10", "1,5 min" or "30 secondes";
    None when it says "not counted"."""
    if not timing or untimed(timing):
        return None
    t = timing.lower().replace(",", ".")
    if m := re.search(r"(\d+):(\d{2})", t):
        return int(m[1]) * 60 + int(m[2])
    if m := re.search(r"(\d+(?:\.\d+)?)\s*min\w*\.?(?:\s*(?:and|et)?\s*(\d+)\s*(?:s|sec\w*)?\b)?", t):
        return round(float(m[1]) * 60) + (int(m[2]) if m[2] else 0)
    if m := re.search(r"(\d+)\s*(?:s|sec\w*)\b", t):
        return int(m[1])
    return None


def speakers(who):
    """The names in a heading shared by several speakers: "Ana & Ben", "Élodie et Marie-Hélène"."""
    return [n.strip() for n in re.split(r"\s*(?:&|\band\b|\bet\b|,|/)\s*", who) if n.strip()]


def presenter_text(notes):
    who, timing, spoken, _ = split_notes(notes)
    head = f"{who} · {timing}" if who else ""
    return "\n".join([head] * bool(head) + spoken)


def mmss(s):
    return f"{s // 60}:{s % 60:02d}"


def notes_markdown(deck, laid):
    title = deck.get("title") or deck["_name"]
    w = language(deck)[0]
    totals, order, body = {}, [], []
    for sl in laid:
        who, timing, spoken, backup = split_notes(sl["notes"])
        secs = seconds(timing)
        if who and secs is not None:
            names = speakers(who)
            for name in names:
                if name not in totals:
                    order.append(name)
                totals[name] = totals.get(name, 0) + secs / len(names)
        words = " / ".join(it["text"].replace("\n", " ") for it in sl["items"]
                           if it["t"] == "text" and it["role"] not in ("source", "ref"))
        kinds = {it["t"] for it in sl["items"]}
        shown = words or (w["film"] if "video" in kinds else w["picture"] if "image" in kinds else w["nothing"])
        body += [f"## {sl['n']}. {md(sl['title'])}", ""]
        if who:
            body.append(f"**{who}**, {timing}  ")
        body += [f"{w['on_screen']}: {md(shown)}", ""]
        if len(spoken) == 1:
            body.append(f"> {md(spoken[0])}")
        else:
            body += [f"- {md(line)}" for line in spoken]
        if backup:
            body += ["", f"{w['backup']}:", ""] + [f"- {md(line)}" for line in backup]
        body.append("")
    totals = {k: round(v) for k, v in totals.items()}
    total = sum(totals.values())
    head = [f"# {title}: {w['notes_file']}", "", w["notes_intro"], ""]
    if totals:
        head += [w["talk"].format(t=mmss(total)), "", f"| {w['speaker']} | {w['time']} |", "|---|---|"]
        head += [f"| {who} | {mmss(totals[who])} |" for who in order]
        head += [f"| **{w['all']}** | **{mmss(total)}** |", ""]
    return "\n".join(head + body).rstrip() + "\n"


# ---------------------------------------------------------------- the whole deck


def slide_title(s, items):
    """The slide's name in the speaker notes."""
    if s.get("title"):
        return s["title"]
    kind, label = s.get("kind"), s.get("label")
    if kind == "steps":
        steps = [st if isinstance(st, dict) else {"head": st} for st in s.get("steps", [])]
        a = s.get("active")
        head = steps[a - 1].get("head") if isinstance(a, int) and 1 <= a <= len(steps) else None
        t = ": ".join(x for x in (label, head) if x) or "Steps"
    elif kind == "team":
        t = "Team"
    elif kind == "list":
        t = " / ".join(map(str, s.get("items", [])))
    elif kind == "media":
        t = s.get("head") or s.get("alt") or ("A film" if s.get("video") else "A picture")
    elif kind == "photo":
        t = s.get("text") or s.get("alt") or "A photo"
    else:
        words = [it["text"].replace("\n", " ") for it in items if it["t"] == "text" and it["role"] == "main"]
        sep = " / " if kind in ("title", "closing", "custom", "columns", "tiles") else " "
        t = sep.join(words[:2]) or label or kind or "slide"
    return t if len(t) <= 70 else t[:67] + "..."


def md(t):
    """Text safe in Markdown: * and _ shown as they are."""
    return re.sub(r"([*_`])", r"\\\1", str(t))


def check_text(c, it):
    """Wrap a text item as measured, and say when it runs out of room."""
    if it["runs"]:
        it["lines"] = c.m.wrap(it["text"], it["size"], it["w"], it["bold"], it["italic"])
    else:
        it["lines"] = c.m.wrap(it["text"], it["size"], it["w"], it["bold"], it["italic"])
    n = len(it["lines"])
    snippet = it["text"].replace("\n", " ")
    snippet = snippet if len(snippet) <= 40 else snippet[:37] + "..."
    if n > it["max_lines"] and it["role"] != "ref":
        c.warn(f"'{snippet}' runs to {n} lines at {it['size']} px (room for {it['max_lines']}): shorten it")
    for word in re.split(r"[ \n]+", it["text"]):   # "27 000 €" with no-break spaces is one word
        if c.m.width(word, it["size"], it["bold"]) > it["w"] + 1:
            c.warn(f"'{word}' is wider than its box at {it['size']} px")
            break
    h = n * it["size"] * LH
    top = {"top": it["y"], "middle": it["y"] - h / 2, "bottom": it["y"] - h}[it["anchor"]]
    if top < -1 or top + h > H + 1:
        c.warn(f"'{snippet}' runs off the slide")
    last = it["lines"][-1].split() if it["lines"] else []
    if it["role"] == "main" and n > 1 and len(last) == 1 and len(it["text"].split()) > 3 and "\n" not in it["text"]:
        c.warn(f"'{last[0]}' sits alone on the last line of '{snippet}': break the line by hand with \\n")


def walked(s):
    """A steps slide with "walk": one slide per step, that step lit, its own picture and notes."""
    steps = s.get("steps")
    if not (isinstance(s, dict) and s.get("kind") == "steps" and s.get("walk") and isinstance(steps, list)):
        return [s]
    out = []
    for i, st in enumerate(steps):
        one = {k: v for k, v in s.items() if k not in ("walk", "active")}
        one["active"] = i + 1
        if isinstance(st, dict):
            for k in ("image", "video", "poster", "alt", "notes", "title", "credit"):
                if st.get(k):
                    one[k] = st[k]
            if "notes" not in st and i:
                one["notes"] = ""
        if i:
            one["transition"] = st.get("transition", "dissolve") if isinstance(st, dict) else "dissolve"
            one.pop("cite", None) if not (isinstance(st, dict) and "cite" in st) else None
        out.append(one)
    return out


def placeholders(deck):
    """Where "[?]" is still in the deck: (slide number or reference key, field)."""
    found = []

    def walk(v, where, field):
        if isinstance(v, str):
            if "[?]" in v:
                found.append((where, field))
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(x, where, k if field is None else field)
        elif isinstance(v, list):
            for x in v:
                walk(x, where, field)

    for n, s in enumerate(deck.get("slides") or [], 1):
        walk(s, f"slide {n}", None)
    for r in deck.get("references") or []:
        walk(r, f"reference {r.get('key', '?') if isinstance(r, dict) else '?'}", None)
    return found


def ink_box(c, it):
    """The box a text item's letters cover, as measured."""
    size, lines = it["size"], it["lines"]
    h = len(lines) * size * LH
    top = {"top": it["y"], "middle": it["y"] - h / 2, "bottom": it["y"] - h}[it["anchor"]]
    widths = [c.m.width(line, size, it["bold"], it["italic"]) for line in lines] or [0]
    lw = max(widths)
    left = {"left": it["x"], "center": it["x"] + (it["w"] - lw) / 2, "right": it["x"] + it["w"] - lw}[it["align"]]
    return left, top, left + lw, top + h


def picture_box(it):
    """The box a picture or film covers once fitted."""
    if it["t"] == "image" and it["fit"] == "contain" and it["path"] is not None and Path(it["path"]).is_file():
        try:
            from PIL import Image
            iw, ih = Image.open(it["path"]).size
            x, y, w, h = contain_box(iw, ih, it["x"], it["y"], it["w"], it["h"], it["valign"])
            return x, y, x + w, y + h
        except Exception:
            pass
    return it["x"], it["y"], it["x"] + it["w"], it["y"] + it["h"]


def check_overlaps(c, kind, items):
    """Words that touch a picture, and anything past the slide's edges."""
    pics = [picture_box(it) for it in items if it["t"] in ("image", "video") and it["w"] * it["h"] < 0.9 * W * H]
    for it in items:
        if it["t"] != "text" or not it["text"].strip():
            continue
        l, t, r, b = it["ink"]
        snippet = it["text"].replace("\n", " ")[:37]
        if l < 40 or r > W - 40:
            c.warn(f"'{snippet}' runs past the side of the slide")
        if kind in ("custom", "photo"):
            continue
        for pl, pt, pr, pb in pics:
            if l < pr - 4 and r > pl + 4 and t + it["size"] * 0.2 < pb - 4 and b - it["size"] * 0.2 > pt + 4:
                c.warn(f"'{snippet}' overlaps a picture")
                break
    if kind not in ("custom", "photo"):
        texts = [it for it in items if it["t"] == "text" and it["text"].strip()]
        for i, a in enumerate(texts):
            for b in texts[i + 1:]:
                al, at_, ar, ab = a["ink"]
                bl, bt, br, bb = b["ink"]
                ta, tb = a["size"] * 0.15, b["size"] * 0.15
                if al < br - 2 and ar > bl + 2 and at_ + ta < bb - tb - 2 and ab - ta > bt + tb + 2:
                    c.warn(f"'{a['text'][:30]}' and '{b['text'][:30]}' overlap")
    for pl, pt, pr, pb in pics:
        if pl < -1 or pt < -1 or pr > W + 1 or pb > H + 1:
            c.warn("a picture runs off the slide")


def caption_item(s, c, kind, items):
    """The caption, under the part of the slide it belongs to."""
    cap = s["caption"]
    pics = [it for it in items if it["t"] in ("image", "video") and it["w"] * it["h"] < 0.9 * W * H]
    if kind == "list" and pics:
        l, t, r, b = picture_box(pics[0])
        return ctext(cap, (l + r) / 2, b + 24, max(r - l + 160, 400), 26, c.th["muted"], bold=False, role="caption")
    if kind in ("steps", "split") and pics:
        x = MARGIN if pics[0]["x"] > W / 2 else MARGIN + 800 + 80
        return text(cap, x, CAPTION_Y, 760, 30, c.th["muted"], bold=False, role="caption")
    return ctext(cap, 960, CAPTION_Y, 1600, 30, c.th["muted"], bold=False, role="caption")


def layout_deck(deck):
    """Every slide's items, laid out and checked. Returns (slides, theme, measure, problems)."""
    th = theme_of(deck)
    files = {k: (Path(v) if Path(v).is_absolute() else deck["_base"] / v)
             for k, v in (th.get("font_files") or {}).items()}
    gone = [str(f) for f in files.values() if not f.is_file()]
    files = {k: f for k, f in files.items() if f.is_file()}
    m = Measure(th["font"], files)
    c = Ctx(deck, th, m)
    if gone:
        c.warn(f"font file not found, so it is left out: {', '.join(gone)}")
    for token, least in (("text", 4.5), ("accent", 3), ("muted", 3)):
        r = contrast(th[token], th["page"])
        if r < least:
            c.warn(f"theme {token} {th[token]} on page {th['page']} has a contrast of {r:.1f}:1 (needs {least}:1 "
                   "to read from the back of a room)")
    if not deck["slides"]:
        c.error("the deck has no slides")
    for k in deck:
        if not k.startswith("_") and k not in TOP_FIELDS:
            near = difflib.get_close_matches(k, sorted(TOP_FIELDS), n=1)
            c.warn(f"deck.json has no field {k!r}, so it does nothing" + (f" (did you mean {near[0]!r}?)" if near else ""))
    theme_keys = {"preset", "font", "font_files", *COLOUR_TOKENS}
    for k in deck.get("theme") or {} if isinstance(deck.get("theme"), dict) else {}:
        if k not in theme_keys:
            c.warn(f"theme has no field {k!r}, so it does nothing")
    if language(deck)[2] not in WORDS and not deck.get("words"):
        c.warn(f"no built-in words for lang {deck.get('lang')!r}: set \"words\" for the source line, reference list "
               "and closing (see references/spec.md)")
    if m.missing:
        c.problems.append(("warning", None, f"font {th['font']!r} is not installed here, so the preview and line "
                                            f"checks use {m.stand_in}, and PowerPoint will swap in a font too. "
                                            "Install it, or set theme.font to a font you have."))
    refs, number = ref_order(deck, c)
    manual = [str(x) for x in deck.get("credits") or []]
    specs = [one for s in deck["slides"] for one in walked(s)]
    given = [credits_of(sp) for sp in specs]
    if (refs or manual or any(given)) and not any(isinstance(s, dict) and s.get("kind") == "references"
                                                  for s in specs):
        specs.append({"kind": "references", "notes": deck.get("references_notes", ""), "transition": "fade"})
        given.append([])
    at = next((i for i, sp in enumerate(specs) if isinstance(sp, dict) and sp.get("kind") == "references"), None)

    def credit_lines(pages):
        """Picture credits with the slide numbers they end up on, the references taking `pages` slides."""
        lines = []
        for i, cr in enumerate(given):
            if cr:
                n = i + 1 + (pages - 1 if at is not None and i > at else 0)
                lines.append(f"Slide {n}: {'; '.join(map(str, cr))}")
        return manual + lines

    credits = credit_lines(1)
    if at is not None:
        pages = len(reference_pages(specs[at], refs, credits, c))
        credits = credit_lines(pages)
    laid, no_notes, no_time, unsourced = [], [], [], []
    for s in specs:
        c.n = len(laid) + 1
        if not isinstance(s, dict):
            c.error("a slide must be an object")
            continue
        kind = s.get("kind")
        if kind not in KINDS:
            c.error(f"kind {kind!r}: use one of {', '.join(KINDS)}")
            continue
        fn, required = KINDS[kind]
        missing = [f for f in required if s.get(f) is None or s.get(f) == "" or s.get(f) == []]
        if kind == "media" and not (s.get("image") or s.get("video")):
            missing.append("image or video")
        if missing:
            c.error(f"{kind} needs {', '.join(missing)}")
            continue
        check_fields(c, s, kind)
        if s.get("transition", "fade") not in TRANSITIONS:
            c.error(f"transition {s['transition']!r}: use one of {', '.join(TRANSITIONS)}")
        try:
            pages = reference_pages(s, refs, credits, c) if kind == "references" else [fn(s, c)]
        except KeyError as e:
            c.error(f"{kind}: an entry is missing {e} (see references/spec.md)")
            continue
        except (TypeError, AttributeError, ValueError) as e:
            c.error(f"{kind}: a field has the wrong shape ({e}); see references/spec.md")
            continue
        for items in pages:
            c.n = len(laid) + 1
            if s.get("label"):
                items.insert(0, text(s["label"], MARGIN, LABEL_Y, 1640, 40, c.th["muted"], role="label"))
            if s.get("caption"):
                items.append(caption_item(s, c, kind, items))
            line = cite_line(s, refs, number, c.words)
            if line:
                items.append(text(line, MARGIN, SOURCE_Y, 1640, 24, c.th["muted"], bold=False, role="source"))
            missing_files = []
            for it in items:
                if it["t"] == "text":
                    check_text(c, it)
                elif it["t"] in ("image", "video") and (it["path"] is None or not Path(it["path"]).is_file()):
                    if it["path"] is not None:
                        missing_files.append(it["path"])
                    if it["t"] == "video" or it["fit"] == "contain":
                        shape = (16, 9) if it["t"] == "video" else (4, 3)
                        x, y, w, h = contain_box(*shape, it["x"], it["y"], it["w"], it["h"], it.get("valign", "middle"))
                        it.update(x=x, y=y, w=w, h=h)
                if it["t"] == "video" and it.get("poster") and not Path(it["poster"]).is_file():
                    missing_files.append(it["poster"])
                    it["poster"] = None
            for it in items:
                if it["t"] == "text":
                    it["ink"] = ink_box(c, it)
            check_overlaps(c, kind, items)
            if kind in ("number", "numbers") and "cite" not in s:
                unsourced.append(c.n)
            if missing_files:
                shown = ", ".join(os.path.relpath(p, c.base) for p in missing_files)
                c.warn(f"not found, so a placeholder stands in: {shown}")
            words = sum(len(it["text"].split()) for it in items if it["t"] == "text" and it["role"] == "main")
            if kind in TERSE and words > TERSE_WORDS:
                c.warn(f"{words} words on screen: say it in the notes and keep one short sentence on the slide")
            page = c.colour(s.get("page"), "#000000" if kind in DARK_GROUND or (kind == "media" and s.get("full"))
                            else th["page"])
            notes = s.get("notes", "")
            if not isinstance(notes, str):
                c.error('notes must be one string, with "\\n" between lines')
                notes = ""
            if kind != "references":
                who, timing, _, _ = split_notes(notes)
                if not notes.strip():
                    no_notes.append(c.n)
                elif who is None or seconds(timing) is None and not untimed(timing):
                    no_time.append(c.n)
            laid.append(dict(n=c.n, kind=kind, spec=s, items=items, page=page, notes=notes,
                             transition=s.get("transition", "fade"), title=slide_title(s, items)))
    c.n = None
    if unsourced:
        c.warn(f"numbers with no source on slide{'s' * (len(unsourced) > 1)} {', '.join(map(str, unsourced))}: "
               'add "cite", or "cite": [] for an ask, a target or your own count')
    left = placeholders(deck)
    if left:
        where = {}
        for w, f in left:
            where.setdefault(w, []).append(f)
        c.warn("placeholders still to fill: " + "; ".join(f"{w} ({', '.join(dict.fromkeys(fs))})"
                                                          for w, fs in where.items()))
    if no_notes:
        c.warn(f"no presenter notes on slide{'s' * (len(no_notes) > 1)} {', '.join(map(str, no_notes))}")
    crowded, padded = [], []
    rate = deck.get("words_per_minute", 130)     # spoken words a minute
    for sl in laid:
        _, timing, spoken, _ = split_notes(sl["notes"])
        secs, words = seconds(timing), len(" ".join(spoken).split())
        if secs and words:
            fits = secs * rate / 60
            if words > fits * 1.5 + 6:
                crowded.append(sl["n"])
            elif secs >= 20 and words < fits * 0.4:
                padded.append(sl["n"])
    if crowded:
        c.warn(f"more words than their time allows (about {rate} a minute) on slide{'s' * (len(crowded) > 1)} "
               f"{', '.join(map(str, crowded))}: cut words or give more time")
    if padded:
        c.warn(f"far fewer words than their time on slide{'s' * (len(padded) > 1)} {', '.join(map(str, padded))}: "
               "write out what is said, or shorten the time")
    total = sum(seconds(split_notes(sl["notes"])[1]) or 0 for sl in laid)
    minutes = deck.get("minutes")
    if isinstance(minutes, (int, float)) and total:
        if total > minutes * 60 * 1.05:
            c.warn(f"about {mmss(total)} of talk for a {minutes}-minute slot: cut a beat or two")
        elif total < minutes * 60 * 0.6:
            c.warn(f"only about {mmss(total)} of talk for a {minutes}-minute slot")
    deck["_talk"] = total
    if no_time:
        c.warn(f"notes without a 'Speaker · about N s' first line on slide{'s' * (len(no_time) > 1)} "
               f"{', '.join(map(str, no_time))}: talk time can't be counted")
    return laid, th, m, c.problems


# ---------------------------------------------------------------- pictures


def prepared(path, mono, keep_original=True, top=255):
    """(bytes, (w, h), Pillow image) of a picture ready to place: turned upright,
    graded black and white if mono, no larger than LONGEST px."""
    from PIL import Image, ImageEnhance, ImageOps
    raw = Path(path).read_bytes()
    im = Image.open(io.BytesIO(raw))
    rotated = im.getexif().get(0x0112, 1) not in (1, None)
    if (keep_original and not mono and not rotated and max(im.size) <= LONGEST and im.format in ("PNG", "JPEG", "GIF")
            and im.mode in ("RGB", "RGBA", "L", "LA", "P", "1")):
        return raw, im.size, im
    im = ImageOps.exif_transpose(im)
    alpha = im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info
    im = im.convert("RGBA" if alpha else "RGB")
    if mono:
        # graded alike, so photos from different places read as one set
        g = ImageOps.autocontrast(im.convert("L"), cutoff=0.5)
        g = ImageEnhance.Contrast(g).enhance(1.12)
        if top < 255:   # on a light page, white would melt into the page
            g = g.point(lambda v: v * top // 255)
        if alpha:
            g = Image.merge("RGBA", (g, g, g, im.getchannel("A")))
        im = g.convert("RGBA" if alpha else "RGB")
    if max(im.size) > LONGEST:
        im.thumbnail((LONGEST, LONGEST), Image.LANCZOS)
    buf = io.BytesIO()
    if alpha:
        im.save(buf, "PNG")
    else:
        im.save(buf, "JPEG", quality=90)
    return buf.getvalue(), im.size, im


def first_frame(path, tmp):
    """The film's first frame as a PNG (needs ffmpeg), or None."""
    if not shutil.which("ffmpeg"):
        return None
    out = Path(tmp) / f"poster-{abs(hash(str(path)))}.png"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-frames:v", "1", str(out)],
                       capture_output=True)
    if r.returncode or not out.exists():
        return None
    try:
        from PIL import Image
        Image.open(out).convert("RGB").save(out)   # drops colour tags some apps darken
    except Exception:
        pass
    return out


def film_size(path, poster):
    if shutil.which("ffprobe"):
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
        try:
            w, h = (int(v) for v in r.stdout.strip().split(",")[:2])
            return w, h
        except ValueError:
            pass
    if poster:
        from PIL import Image
        return Image.open(poster).size
    return 1920, 1080


# ---------------------------------------------------------------- PowerPoint


def write_pptx(deck, laid, th, out):
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
    from pptx.oxml import parse_xml
    from pptx.oxml.ns import nsdecls, qn
    from pptx.util import Emu, Pt

    def E(px):
        return Emu(round(px * EMU_PER_PX))

    def rgb(h):
        return RGBColor.from_string(h.lstrip("#").upper())

    align = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
    anchor = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM}

    prs = Presentation()
    prs.slide_width, prs.slide_height = E(W), E(H)
    prs.core_properties.title = deck.get("title", "")
    blank = prs.slide_layouts[6]
    tmp = tempfile.mkdtemp(prefix="deck-")
    tag = language(deck)[1]

    def frame(tf, a="middle"):
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.NONE
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = anchor[a]

    def run(p, s, size, color, bold, italic):
        r = p.add_run()
        r.text = s
        f = r.font
        f.name, f.size, f.bold, f.italic = th["font"], Pt(size / 2), bold, italic
        r._r.get_or_add_rPr().set("lang", tag)   # so PowerPoint checks the spelling in the deck's language
        f.color.rgb = rgb(color)

    def add_text(slide, it):
        size = it["size"]
        h = max(len(it["lines"]), 1) * size * LH
        top = {"top": it["y"], "middle": it["y"] - h / 2, "bottom": it["y"] - h}[it["anchor"]]
        tf = slide.shapes.add_textbox(E(it["x"]), E(top), E(it["w"]), E(h)).text_frame
        frame(tf, it["anchor"])
        paras = [it["runs"]] if it["runs"] else [[(line, it["italic"])] for line in it["text"].split("\n")]
        for i, runs in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align[it["align"]]
            p.line_spacing = Pt(size / 2 * LH)
            p.space_before = p.space_after = Pt(0)
            for s, italic in runs:
                run(p, s, size, it["color"], it["bold"], italic)

    def no_outline(shp):
        shp.line.fill.background()
        shp.shadow.inherit = False

    def add_placeholder(slide, it, word):
        x, y, w, h = it["x"], it["y"], it["w"], it["h"]
        r = it.get("radius", 0)
        shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if r else MSO_SHAPE.RECTANGLE, E(x), E(y), E(w), E(h))
        if r:
            shp.adjustments[0] = min(r / min(w, h), 0.5)
        shp.fill.solid()
        shp.fill.fore_color.rgb = rgb(th["placeholder"])
        no_outline(shp)
        tf = shp.text_frame
        frame(tf)
        for i, (s, size, bold) in enumerate([(word, 20, True)] + [(it["label"], 30, False)] * bool(it["label"])):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.CENTER
            run(p, s, size, th["muted"], bold, False)

    def round_corners(shape, frac):
        geom = shape._element.spPr.find(qn("a:prstGeom"))
        geom.set("prst", "roundRect")
        av = geom.find(qn("a:avLst"))
        if av is None:
            av = geom.makeelement(qn("a:avLst"), {})
            geom.append(av)
        for gd in list(av):
            av.remove(gd)
        av.append(parse_xml(f'<a:gd {nsdecls("a")} name="adj" fmla="val {round(min(frac, 0.5) * 100000)}"/>'))

    def add_image(slide, it):
        if it["path"] is None or not Path(it["path"]).is_file():
            return add_placeholder(slide, it, "PHOTO")
        data, (iw, ih), _ = prepared(it["path"], it["mono"], top=236 if light_page(th) else 255)
        x, y, w, h = it["x"], it["y"], it["w"], it["h"]
        if it["fit"] == "contain":
            x, y, w, h = contain_box(iw, ih, x, y, w, h, it["valign"])
        pic = slide.shapes.add_picture(io.BytesIO(data), E(x), E(y), E(w), E(h))
        if it["fit"] == "cover":
            pic.crop_left, pic.crop_top, pic.crop_right, pic.crop_bottom = cover_crop(iw, ih, w, h, it["focus"])
        if it["radius"]:
            round_corners(pic, it["radius"] / min(w, h))

    def add_video(slide, it):
        if it["path"] is None or not Path(it["path"]).is_file():
            return add_placeholder(slide, dict(it, radius=0), "VIDEO")
        poster = it["poster"] or first_frame(it["path"], tmp)
        x, y, w, h = contain_box(*film_size(it["path"], poster), it["x"], it["y"], it["w"], it["h"])
        mime = mimetypes.guess_type(str(it["path"]))[0] or "video/mp4"
        slide.shapes.add_movie(str(it["path"]), E(x), E(y), E(w), E(h),
                               poster_frame_image=str(poster) if poster else None, mime_type=mime)

    def add_rect(slide, it):
        shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, E(it["x"]), E(it["y"]), E(it["w"]), E(it["h"]))
        no_outline(shp)
        spPr = shp._element.spPr
        for tag in ("a:solidFill", "a:gradFill", "a:noFill", "a:pattFill", "a:blipFill"):
            for e in spPr.findall(qn(tag)):
                spPr.remove(e)
        a0, a1 = it["alpha"]
        hexv = it["color"].lstrip("#").upper()
        stops = ""
        for pos in (0, 0.25, 0.5, 0.75, 1):
            t = pos * pos * (3 - 2 * pos)          # eases in and out, as a fade does
            stops += (f'<a:gs pos="{round(pos * 100000)}"><a:srgbClr val="{hexv}">'
                      f'<a:alpha val="{round((a0 + (a1 - a0) * t) * 100000)}"/></a:srgbClr></a:gs>')
        grad = parse_xml(f'<a:gradFill {nsdecls("a")} rotWithShape="1"><a:gsLst>{stops}</a:gsLst>'
                         '<a:lin ang="5400000" scaled="0"/></a:gradFill>')
        spPr.find(qn("a:prstGeom")).addnext(grad)

    draw = {"text": add_text, "image": add_image, "video": add_video, "rect": add_rect}
    for sl in laid:
        slide = prs.slides.add_slide(blank)
        bg = slide.background.fill
        bg.solid()
        bg.fore_color.rgb = rgb(sl["page"])
        for it in sl["items"]:
            draw[it["t"]](slide, it)
        notes = presenter_text(sl["notes"])
        if notes:
            tf = slide.notes_slide.notes_text_frame
            tf.text = notes
            for para in tf.paragraphs:
                for r in para.runs:
                    r._r.get_or_add_rPr().set("lang", tag)
        xml = TRANSITIONS[sl["transition"]]
        if xml:
            tr = parse_xml(xml.format(ns=nsdecls("p")))
            sld = slide._element
            after = sld.find(qn("p:clrMapOvr"))
            (after if after is not None else sld.find(qn("p:cSld"))).addnext(tr)
    prs.save(str(out))
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- preview


def hex_rgb(h, a=255):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def render_png(sl, th, m, tmp):
    """The slide drawn with Pillow: a proof of the layout, not PowerPoint's own rendering."""
    from PIL import Image, ImageDraw

    im = Image.new("RGBA", (W, H), hex_rgb(sl["page"]))

    def rounded(pic, r):
        if not r:
            return pic
        mask = Image.new("L", (pic.width * 2, pic.height * 2), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, mask.width - 1, mask.height - 1), radius=r * 2, fill=255)
        pic = pic.convert("RGBA")
        a = pic.getchannel("A")
        from PIL import ImageChops
        pic.putalpha(ImageChops.multiply(a, mask.resize(pic.size, Image.LANCZOS)))
        return pic

    def placeholder(it, word):
        x, y, w, h = (round(it[k]) for k in ("x", "y", "w", "h"))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=it.get("radius", 0), fill=hex_rgb(th["placeholder"]))
        rows = [(word, m.font(20, True))] + [(it["label"], m.font(30, False))] * bool(it["label"])
        hs = [f.getbbox(s)[3] - f.getbbox(s)[1] for s, f in rows]
        yy = y + (h - sum(hs) - 16 * (len(rows) - 1)) / 2
        for (s, f), hh in zip(rows, hs):
            d.text((x + w / 2, yy), s, font=f, fill=hex_rgb(th["muted"]), anchor="mt")
            yy += hh + 16

    def place(pic, it, fit):
        x, y, w, h = it["x"], it["y"], it["w"], it["h"]
        if fit == "contain":
            x, y, w, h = contain_box(pic.width, pic.height, x, y, w, h, it.get("valign", "middle"))
        else:
            l, t, r, b = cover_crop(pic.width, pic.height, w, h, it.get("focus", (0.5, 0.5)))
            pic = pic.crop((round(l * pic.width), round(t * pic.height),
                            round((1 - r) * pic.width), round((1 - b) * pic.height)))
        pic = pic.convert("RGBA").resize((max(round(w), 1), max(round(h), 1)), Image.LANCZOS)
        pic = rounded(pic, it.get("radius", 0))
        im.alpha_composite(pic, (round(x), round(y)))
        return x, y, w, h

    for it in sl["items"]:
        if it["t"] == "rect":
            g = Image.new("RGBA", (round(it["w"]), round(it["h"])))
            a0, a1 = it["alpha"]
            for yy in range(g.height):
                t = yy / max(g.height - 1, 1)
                t = t * t * (3 - 2 * t)
                g.paste(hex_rgb(it["color"], round(255 * (a0 + (a1 - a0) * t))), (0, yy, g.width, yy + 1))
            im.alpha_composite(g, (round(it["x"]), round(it["y"])))
        elif it["t"] == "image":
            if it["path"] is None or not Path(it["path"]).is_file():
                placeholder(it, "PHOTO")
            else:
                _, _, pic = prepared(it["path"], it["mono"], keep_original=False, top=236 if light_page(th) else 255)
                place(pic, it, it["fit"])
        elif it["t"] == "video":
            poster = it.get("poster") or (first_frame(it["path"], tmp) if it["path"] and Path(it["path"]).is_file()
                                          else None)
            if not poster:
                placeholder(it, "VIDEO")
                continue
            x, y, w, h = place(Image.open(poster), it, "contain")
            d = ImageDraw.Draw(im)
            cx, cy, r = x + w / 2, y + h / 2, 40
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(0, 0, 0, 140))
            d.polygon([(cx - 12, cy - 20), (cx - 12, cy + 20), (cx + 22, cy)], fill=(255, 255, 255, 230))
        elif it["t"] == "text":
            size, lines = it["size"], it["lines"]
            f = m.font(size, it["bold"], it["italic"])
            lh = size * LH
            h = len(lines) * lh
            top = {"top": it["y"], "middle": it["y"] - h / 2, "bottom": it["y"] - h}[it["anchor"]]
            asc, desc = f.getmetrics()
            d = ImageDraw.Draw(im)
            plain = len(it["runs"][0][0]) if it["runs"] else None   # where the italic run starts
            fi = m.font(size, it["bold"], True)
            offset = 0
            for i, line in enumerate(lines):
                lw = f.getlength(line)
                x = {"left": it["x"], "center": it["x"] + (it["w"] - lw) / 2, "right": it["x"] + it["w"] - lw}[it["align"]]
                base = top + i * lh + (lh - (asc + desc)) / 2 + asc
                cut = len(line) if plain is None else min(max(plain - offset, 0), len(line))
                d.text((x, base), line[:cut], font=f, fill=hex_rgb(it["color"]), anchor="ls")
                if cut < len(line):
                    d.text((x + f.getlength(line[:cut]), base), line[cut:], font=fi, fill=hex_rgb(it["color"]),
                           anchor="ls")
                offset += len(line) + 1
    return im.convert("RGB")


def write_previews(laid, th, m, out_dir):
    from PIL import Image, ImageDraw
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("slide-*.png"):
        old.unlink()
    tmp = tempfile.mkdtemp(prefix="deck-")
    thumbs = []
    for sl in laid:
        im = render_png(sl, th, m, tmp)
        im.save(out_dir / f"slide-{sl['n']:02d}.png")
        thumbs.append(im.resize((480, 270), Image.LANCZOS))
    shutil.rmtree(tmp, ignore_errors=True)
    cols = 4
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 492 + 12, rows * 304 + 12), (64, 64, 66))
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(thumbs):
        r, col = divmod(i, cols)
        x, y = 12 + col * 492, 12 + r * 304
        sheet.paste(t, (x, y))
        d.text((x, y + 274), str(i + 1), fill=(220, 220, 224), font=m.font(20, True))
    sheet.save(out_dir / "contact.png")
    return out_dir / "contact.png"


# ---------------------------------------------------------------- command line


def report(problems):
    order = {"error": 0, "warning": 1}
    for level, n, msg in sorted(problems, key=lambda p: (order[p[0]], p[1] or 0)):
        where = f"slide {n}: " if n else ""
        print(f"{level}: {where}{msg}", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a one-idea-a-slide deck as a .pptx from a JSON spec.")
    ap.add_argument("spec", help="the deck's JSON file")
    ap.add_argument("-o", "--out", help="the .pptx to write (default: beside the spec)")
    ap.add_argument("--preview", metavar="DIR", help="also draw each slide as a PNG, and contact.png, into DIR")
    ap.add_argument("--check", action="store_true", help="only report problems")
    args = ap.parse_args(argv)
    try:
        deck = load(args.spec)
        laid, th, m, problems = layout_deck(deck)
    except SpecError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    report(problems)
    errors = sum(1 for p in problems if p[0] == "error")
    if errors:
        print(f"{errors} error(s): nothing written", file=sys.stderr)
        return 1
    if args.check:
        print(f"{len(laid)} slides, {len(problems)} warning(s)")
        return 0
    try:
        import pptx  # noqa: F401
    except ImportError:
        print("error: writing the deck needs python-pptx: pip install python-pptx", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else Path(args.spec).with_suffix(".pptx")
    out.parent.mkdir(parents=True, exist_ok=True)
    write_pptx(deck, laid, th, out)
    notes = out.with_name(f"{out.stem} {language(deck)[0]['notes_file']}.md")
    notes.write_text(notes_markdown(deck, laid), encoding="utf-8")
    print(out)
    print(notes)
    if args.preview:
        print(write_previews(laid, th, m, args.preview))
    return 0


if __name__ == "__main__":
    sys.exit(main())
