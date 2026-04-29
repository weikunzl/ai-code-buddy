#!/usr/bin/env python3
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEADER = ROOT / "src" / "wav_assets.h"
SOURCE = ROOT / "src" / "wav_assets.cpp"
MAIN = ROOT / "src" / "main.cpp"


class WavAssetTests(unittest.TestCase):
    def test_asset_unit_declares_both_wavs(self):
        text = HEADER.read_text()
        self.assertIn("kInputRequiredWav", text)
        self.assertIn("kInputRequiredWavLen", text)
        self.assertIn("kCompleteWav", text)
        self.assertIn("kCompleteWavLen", text)

    def test_asset_source_contains_riff_wave_signatures(self):
        text = SOURCE.read_text()
        self.assertIn("0x52, 0x49, 0x46, 0x46", text)
        self.assertIn("0x57, 0x41, 0x56, 0x45", text)

    def test_main_uses_playwav_for_two_named_helpers(self):
        text = MAIN.read_text()
        self.assertRegex(
            text,
            r"static void toneInputRequired\(\) \{\s*if \(settings\(\)\.sound\) M5\.Speaker\.playWav\(kInputRequiredWav, kInputRequiredWavLen\);\s*\}",
        )
        self.assertRegex(
            text,
            r"static void toneComplete\(\) \{\s*if \(settings\(\)\.sound\) M5\.Speaker\.playWav\(kCompleteWav, kCompleteWavLen\);\s*\}",
        )


if __name__ == "__main__":
    unittest.main()
