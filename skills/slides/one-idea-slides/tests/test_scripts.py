#!/usr/bin/env python3
"""Tests for one-idea-slides' build_deck.py.

Run: python3 tests/test_scripts.py
The layout, checks and notes run on the standard library alone. Building the
.pptx and the previews needs python-pptx (and its Pillow); those tests skip
without it, as does the film test without ffmpeg.
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
EXAMPLE = SKILL_DIR / "assets" / "example-deck.json"
spec = importlib.util.spec_from_file_location("build_deck", SKILL_DIR / "scripts" / "build_deck.py")
bd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bd)

try:
    import pptx  # noqa: F401
    HAVE_PPTX = True
except ImportError:
    HAVE_PPTX = False


def deck_file(root, slides=(), **top):
    path = Path(root) / "deck.json"
    path.write_text(json.dumps(dict(top, slides=list(slides))), encoding="utf-8")
    return path


def problems(path):
    _, _, _, found = bd.layout_deck(bd.load(path))
    return found


def quietly(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args)


class TestPieces(unittest.TestCase):
    def test_notes_split_speaker_spoken_and_backup(self):
        who, timing, spoken, backup = bd.split_notes("Ana · about 15 s\nOne.\nTwo.\n\nIf asked: three.")
        self.assertEqual((who, timing, spoken, backup), ("Ana", "about 15 s", ["One.", "Two."], ["If asked: three."]))
        self.assertEqual(bd.presenter_text("Ana · about 15 s\nOne.\n\nBackup."), "Ana · about 15 s\nOne.")

    def test_notes_without_a_heading_are_all_spoken(self):
        who, timing, spoken, _ = bd.split_notes("Just say this.")
        self.assertEqual((who, timing, spoken), (None, None, ["Just say this."]))

    def test_seconds(self):
        self.assertEqual(bd.seconds("about 15 s"), 15)
        self.assertEqual(bd.seconds("1:30"), 90)
        self.assertEqual(bd.seconds("2 min"), 120)
        self.assertIsNone(bd.seconds("2:00, not counted in the talk"))

    def test_cover_crop_keeps_the_focus_and_the_box_shape(self):
        l, t, r, b = bd.cover_crop(2000, 1000, 500, 500, (0.9, 0.5))
        self.assertAlmostEqual(1 - l - r, 0.5)          # half the width is kept
        self.assertAlmostEqual(r, 0.0)                    # pushed to the right edge, not past it
        self.assertEqual((t, b), (0.0, 0.0))
        l, t, r, b = bd.cover_crop(1000, 2000, 1000, 1000, (0.5, 0.0))
        self.assertEqual((l, t), (0.0, 0.0))
        self.assertAlmostEqual(b, 0.5)

    def test_contain_box(self):
        self.assertEqual(bd.contain_box(200, 100, 0, 0, 400, 400, "bottom"), (0, 200, 400, 200))


class TestLayout(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_example_has_no_errors_and_gets_a_reference_list(self):
        laid, _, _, found = bd.layout_deck(bd.load(EXAMPLE))
        self.assertEqual([p for p in found if p[0] == "error"], [])
        self.assertEqual(laid[-1]["kind"], "references")
        walks = sum(len(s["steps"]) - 1 for s in json.loads(EXAMPLE.read_text())["slides"] if s.get("walk"))
        self.assertEqual(len(laid), len(json.loads(EXAMPLE.read_text())["slides"]) + walks + 1)

    def test_example_words_fit(self):
        overflow = [p for p in problems(EXAMPLE) if "lines" in p[2] or "words on screen" in p[2]]
        self.assertEqual(overflow, [])

    def test_unknown_kind_and_missing_field_are_errors(self):
        path = deck_file(self.root, [{"kind": "bullets"}, {"kind": "number"}])
        msgs = [p[2] for p in problems(path) if p[0] == "error"]
        self.assertTrue(any("bullets" in m for m in msgs))
        self.assertTrue(any("number needs number" in m for m in msgs))

    def test_malformed_slides_are_errors_not_crashes(self):
        bad = [
            {"slides": []},
            {"slides": [{"kind": "numbers", "numbers": ["1", "2"]}]},
            {"slides": [{"kind": "numbers", "numbers": [{"text": "a"}, {"text": "b"}]}]},
            {"slides": [{"kind": "statement", "text": None}]},
            {"slides": [{"kind": "statement", "text": "a", "notes": ["x"]}]},
            {"slides": [{"kind": "photo", "image": "x.jpg", "focus": "center"}]},
            {"slides": [{"kind": "steps", "steps": ["a", "b"], "active": 9}]},
            {"slides": [{"kind": "list", "items": []}]},
            {"slides": [{"kind": "columns", "columns": [{"tail": "x"}]}]},
            {"slides": [{"kind": "team", "people": [{"role": "x"}]}]},
            {"slides": [{"kind": "custom", "items": [{"type": "text", "text": "a"}]}]},
            {"slides": [{"kind": "custom", "items": "x"}]},
            {"references": {"a": 1}, "slides": [{"kind": "closing"}]},
        ]
        for deck in bad:
            with self.subTest(deck=deck):
                path = deck_file(self.root, **deck)
                self.assertTrue(any(p[0] == "error" for p in problems(path)))

    def test_a_single_citation_can_be_a_string(self):
        refs = [{"key": "survey", "cite": "A, 2025", "author": "A", "title": "T."}]
        path = deck_file(self.root, [{"kind": "number", "number": "1", "cite": "survey"}], references=refs)
        self.assertEqual([p for p in problems(path) if p[0] == "error"], [])

    def test_timings_in_other_forms(self):
        cases = {"environ 1 min 10": 70, "1 min 30 s": 90, "environ 1,5 min": 90, "30 secondes": 30, "20 sec": 20}
        for timing, secs in cases.items():
            self.assertEqual(bd.seconds(timing), secs, timing)
        self.assertIsNone(bd.seconds("non compté"))
        self.assertEqual(bd.split_notes("Ana - 10 s\nHi.")[:2], ("Ana", "10 s"))
        self.assertEqual(bd.split_notes("Jean-Paul · 5 s\nHi.")[0], "Jean-Paul")

    def test_walk_makes_one_slide_per_step(self):
        path = deck_file(self.root, [{"kind": "steps", "walk": True, "label": "How",
                                      "steps": [{"head": "One.", "notes": "A · 5 s\nOne."},
                                                {"head": "Two.", "notes": "A · 5 s\nTwo."}]}])
        laid, _, _, _ = bd.layout_deck(bd.load(path))
        self.assertEqual([sl["transition"] for sl in laid], ["fade", "dissolve"])
        self.assertEqual([sl["title"] for sl in laid], ["How: One.", "How: Two."])
        self.assertTrue(laid[1]["notes"].endswith("Two."))

    def test_credits_get_their_slide_numbers(self):
        path = deck_file(self.root, [{"kind": "statement", "text": "A."},
                                     {"kind": "photo", "image": "x.jpg", "credit": "Photo: Ana"}])
        laid, _, _, _ = bd.layout_deck(bd.load(path))
        self.assertEqual(laid[-1]["kind"], "references")
        self.assertIn("Slide 2: Photo: Ana", [it["text"] for it in laid[-1]["items"]])

    def test_checks_that_catch_trial_mistakes(self):
        slides = [
            {"kind": "number", "number": "5", "captoin": "x"},
            {"kind": "list", "items": ["Introduce us to buyers in Kigali.", "Pilot."], "image": "qr.png"},
            {"kind": "numbers", "numbers": [{"number": "27 000 €"}, {"number": "4"}, {"number": "3"}]},
        ]
        path = deck_file(self.root, slides, theme={"preset": "light", "accent": "#FDFC9B"}, minutes=1)
        msgs = " | ".join(p[2] for p in problems(path))
        self.assertIn("did you mean 'caption'", msgs)
        self.assertIn("wider than the margins", msgs)
        self.assertIn("27 000 €", msgs)        # measured whole, despite the no-break spaces
        self.assertIn("contrast", msgs)
        self.assertIn("numbers with no source", msgs)

    def test_talk_time_against_words_and_slot(self):
        long = " ".join(["word"] * 80)
        path = deck_file(self.root, [{"kind": "statement", "text": "A.", "notes": f"Ana · 10 s\n{long}"},
                                     {"kind": "statement", "text": "B.", "notes": "Ana · 2 min\nHi."}], minutes=1)
        msgs = " | ".join(p[2] for p in problems(path))
        self.assertIn("more words than their time allows", msgs)
        self.assertIn("far fewer words", msgs)
        self.assertIn("for a 1-minute slot", msgs)

    def test_french_words(self):
        refs = [{"key": "a", "cite": "Insee, 2024", "author": "Insee", "title": "T."}]
        path = deck_file(self.root, [{"kind": "number", "number": "4 200", "cite": ["a"]}, {"kind": "closing"}],
                         references=refs, lang="fr")
        laid, _, _, _ = bd.layout_deck(bd.load(path))
        texts = [it["text"] for sl in laid for it in sl["items"] if it["t"] == "text"]
        for expected in ("Source : Insee, 2024", "Merci.", "Des questions ?", "Références"):
            self.assertIn(expected, texts)
        self.assertTrue(any("(s. d.)" in t for t in texts))

    def test_label_sits_above_a_full_slide_film(self):
        path = deck_file(self.root, [{"kind": "custom", "label": "How it works", "items": [
            {"type": "video", "path": "film.mp4", "x": 0, "y": 0, "w": 1920, "h": 1080}]}])
        laid, _, _, _ = bd.layout_deck(bd.load(path))
        self.assertEqual(laid[0]["items"][-1]["text"], "How it works")

    def test_unknown_citation_is_an_error(self):
        path = deck_file(self.root, [{"kind": "statement", "text": "Hi.", "cite": ["nope"]}])
        self.assertTrue(any(p[0] == "error" and "nope" in p[2] for p in problems(path)))

    def test_long_words_warn(self):
        long = " ".join(["word"] * 60)
        path = deck_file(self.root, [{"kind": "statement", "text": long, "notes": "A · about 5 s\nHi."}])
        msgs = [p[2] for p in problems(path)]
        self.assertTrue(any("runs to" in m for m in msgs))
        self.assertTrue(any("words on screen" in m for m in msgs))

    def test_notes_are_checked(self):
        path = deck_file(self.root, [{"kind": "statement", "text": "One."},
                                     {"kind": "statement", "text": "Two.", "notes": "No heading here."}])
        msgs = [p[2] for p in problems(path)]
        self.assertTrue(any("no presenter notes on slide 1" in m for m in msgs))
        self.assertTrue(any("slide 2" in m and "Speaker" in m for m in msgs))

    def test_cited_slide_gets_a_source_line(self):
        refs = [{"key": "a", "cite": "Author, 2025", "author": "Author, A.", "year": "2025", "title": "T."}]
        path = deck_file(self.root, [{"kind": "number", "number": "3", "text": "x", "cite": ["a"]}], references=refs)
        laid, _, _, _ = bd.layout_deck(bd.load(path))
        lines = [it["text"] for it in laid[0]["items"] if it["t"] == "text" and it["role"] == "source"]
        self.assertEqual(lines, ["Source: Author, 2025"])

    def test_check_exit_codes(self):
        good = deck_file(self.root, [{"kind": "closing"}])
        self.assertEqual(quietly(bd.main, [str(good), "--check"]), 0)
        bad = deck_file(self.root, [{"kind": "nope"}])
        self.assertEqual(quietly(bd.main, [str(bad), "--check"]), 1)

    def test_notes_markdown_totals_speakers(self):
        path = deck_file(self.root, [{"kind": "statement", "text": "One.", "notes": "Ana · about 20 s\nHi."},
                                     {"kind": "statement", "text": "Two.", "notes": "Ben · 1:10\nYo."},
                                     {"kind": "statement", "text": "Three.", "notes": "Ana · about 40 s\nBye."}])
        deck = bd.load(path)
        laid, _, _, _ = bd.layout_deck(deck)
        md = bd.notes_markdown(deck, laid)
        self.assertIn("| Ana | 1:00 |", md)
        self.assertIn("| Ben | 1:10 |", md)
        self.assertIn("**2:10**", md)


@unittest.skipUnless(HAVE_PPTX, "python-pptx not installed")
class TestBuild(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def photo(self, name, size=(1200, 800)):
        from PIL import Image
        im = Image.new("RGB", size, (200, 120, 40))
        im.paste((30, 60, 200), (0, 0, size[0] // 2, size[1]))
        im.save(self.root / name)
        return name

    def test_example_builds_with_notes_transitions_and_previews(self):
        out = self.root / "kibo.pptx"
        self.assertEqual(quietly(bd.main, [str(EXAMPLE), "-o", str(out), "--preview", str(self.root / "pv")]), 0)
        from pptx import Presentation
        prs = Presentation(str(out))
        slides = list(prs.slides)
        self.assertEqual(len(slides), 16)
        self.assertEqual(prs.slide_width, 12192000)
        self.assertTrue(slides[0].notes_slide.notes_text_frame.text.startswith("Ana · about 10 s"))
        from lxml import etree
        xml = etree.tostring(slides[7]._element).decode()
        self.assertIn("<p:dissolve", xml)
        self.assertIn('thruBlk="1"', etree.tostring(slides[1]._element).decode())
        self.assertTrue((self.root / "kibo speaker notes.md").read_text().startswith("# Kibo pitch: speaker notes"))
        self.assertTrue((self.root / "pv" / "contact.png").is_file())
        self.assertEqual(len(list((self.root / "pv").glob("slide-*.png"))), 16)

    def test_pictures_are_cropped_rounded_and_graded(self):
        self.photo("wide.jpg")
        path = deck_file(self.root, [{"kind": "split", "text": "Hi.", "image": "wide.jpg", "focus": [1, 0.5]}])
        out = self.root / "d.pptx"
        self.assertEqual(quietly(bd.main, [str(path), "-o", str(out)]), 0)
        from pptx import Presentation
        from PIL import Image
        pic = [s for s in Presentation(str(out)).slides[0].shapes if s.shape_type == 13][0]
        self.assertAlmostEqual(pic.crop_right, 0, places=3)
        self.assertGreater(pic.crop_left, 0.2)
        self.assertIn('prst="roundRect"', pic._element.xml)
        im = Image.open(io.BytesIO(pic.image.blob)).convert("RGB")
        r, g, b = im.getpixel((10, 10))
        self.assertTrue(r == g == b, "split photos are black and white by default")

    def test_language_tag_and_cmyk(self):
        from PIL import Image
        Image.new("CMYK", (400, 300), (0, 80, 80, 0)).save(self.root / "cmyk.jpg")
        path = deck_file(self.root, [{"kind": "photo", "image": "cmyk.jpg", "text": "Bonjour.",
                                      "notes": "Élodie · 5 s\nBonjour."}], lang="fr")
        out = self.root / "d.pptx"
        self.assertEqual(quietly(bd.main, [str(path), "-o", str(out)]), 0)
        from pptx import Presentation
        slide = Presentation(str(out)).slides[0]
        pic = [s for s in slide.shapes if s.shape_type == 13][0]
        self.assertEqual(Image.open(io.BytesIO(pic.image.blob)).mode, "RGB")
        self.assertIn('lang="fr-FR"', slide._element.xml)
        self.assertIn('lang="fr-FR"', slide.notes_slide._element.xml)
        self.assertTrue((self.root / "d notes de présentation.md").is_file())

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_film_gets_a_poster(self):
        clip = self.root / "clip.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=320x180:d=1", "-pix_fmt",
                        "yuv420p", str(clip)], check=True)
        path = deck_file(self.root, [{"kind": "media", "video": "clip.mp4", "full": True}])
        out = self.root / "d.pptx"
        self.assertEqual(quietly(bd.main, [str(path), "-o", str(out)]), 0)
        from pptx import Presentation
        shapes = list(Presentation(str(out)).slides[0].shapes)
        self.assertEqual(len(shapes), 1)
        self.assertIn("videoFile", shapes[0]._element.xml)


if __name__ == "__main__":
    os.chdir(SKILL_DIR)
    unittest.main(verbosity=1)
