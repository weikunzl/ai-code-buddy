#!/usr/bin/env python3
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEADER = ROOT / "src" / "wav_assets.h"
SOURCE = ROOT / "src" / "wav_assets.cpp"
MAIN = ROOT / "src" / "main.cpp"


def extract_function_body(text, func_name):
    markers = [f"static void {func_name}()", f"void {func_name}()"]
    start = None
    for marker in markers:
        try:
            start = text.index(marker)
            break
        except ValueError:
            continue
    if start is None:
        raise ValueError(f"missing function definition for {func_name}")
    brace = text.index("{", start)
    depth = 0
    for idx in range(brace, len(text)):
        ch = text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[brace + 1:idx]
    raise ValueError(f"unterminated function body for {func_name}")


def parse_wav_assets(text):
    pattern = re.compile(
        r"const uint8_t (?P<name>k(?:InputRequired|Complete)Wav)\[] = \{(?P<body>.*?)\};\s*"
        r"const size_t (?P<len_name>k(?:InputRequired|Complete)WavLen) = (?P<len_value>\d+);",
        re.S,
    )
    assets = {}
    for match in pattern.finditer(text):
        byte_values = [int(token, 16) for token in re.findall(r"0x[0-9a-fA-F]{2}", match.group("body"))]
        assets[match.group("name")] = {
            "bytes": byte_values,
            "len_name": match.group("len_name"),
            "len_value": int(match.group("len_value")),
        }
    return assets


class WavAssetTests(unittest.TestCase):
    def test_asset_unit_declares_both_wavs(self):
        text = HEADER.read_text()
        self.assertIn("kInputRequiredWav", text)
        self.assertIn("kInputRequiredWavLen", text)
        self.assertIn("kCompleteWav", text)
        self.assertIn("kCompleteWavLen", text)

    def test_asset_source_contains_two_valid_wav_assets_with_matching_lengths(self):
        assets = parse_wav_assets(SOURCE.read_text())
        self.assertEqual(set(assets), {"kInputRequiredWav", "kCompleteWav"})

        expected_lengths = {
            "kInputRequiredWav": "kInputRequiredWavLen",
            "kCompleteWav": "kCompleteWavLen",
        }
        for name, len_name in expected_lengths.items():
            with self.subTest(asset=name):
                asset = assets[name]
                data = asset["bytes"]
                self.assertEqual(asset["len_name"], len_name)
                self.assertEqual(asset["len_value"], len(data))
                self.assertGreater(len(data), 44)
                self.assertEqual(bytes(data[:4]), b"RIFF")
                self.assertEqual(bytes(data[8:12]), b"WAVE")

                data_offset = bytes(data).find(b"data")
                self.assertNotEqual(data_offset, -1)
                self.assertLess(data_offset, 128)
                self.assertGreaterEqual(len(data), data_offset + 8)
                payload_len = int.from_bytes(bytes(data[data_offset + 4:data_offset + 8]), "little")
                self.assertEqual(payload_len, len(data) - (data_offset + 8))
                self.assertGreater(payload_len, 0)

                samples = []
                for idx in range(data_offset + 8, len(data), 2):
                    if idx + 1 >= len(data):
                        break
                    sample = int.from_bytes(bytes(data[idx:idx + 2]), "little", signed=True)
                    samples.append(sample)
                self.assertTrue(samples)
                self.assertGreater(max(abs(v) for v in samples), 16000)

    def test_main_uses_wav_helpers_without_duplicate_same_tick_prompt_cues(self):
        text = MAIN.read_text()

        input_required_body = extract_function_body(text, "toneInputRequired")
        complete_body = extract_function_body(text, "toneComplete")
        self.assertIn("playWav(kInputRequiredWav, kInputRequiredWavLen, 1, 0, true)", input_required_body)
        self.assertIn("playWav(kCompleteWav, kCompleteWavLen, 1, 0, true)", complete_body)
        self.assertIn("beep(1200, 80);", input_required_body)
        self.assertIn("beep(1600, 60);", complete_body)
        self.assertIn("beep(2200, 60);", complete_body)
        self.assertIn("if (!played)", input_required_body)
        self.assertIn("if (!played)", complete_body)

        self.assertIn("samePromptAndPendingArrival", text)
        self.assertIn("bool samePromptAndPendingArrival = promptChanged", text)
        self.assertIn('strcmp(tama.promptId, tama.pending[0].id) == 0', text)

        pending_body = extract_function_body(text, "loop").split("if (pendingChanged)", 1)[1]
        self.assertIn("!samePromptAndPendingArrival", pending_body)


if __name__ == "__main__":
    unittest.main()
