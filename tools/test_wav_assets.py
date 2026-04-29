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


def parse_pcm_assets(text):
    pattern = re.compile(
        r"const int16_t (?P<name>k(?:InputRequired|Complete)Pcm)\[] = \{(?P<body>.*?)\};\s*"
        r"const size_t (?P<len_name>k(?:InputRequired|Complete)PcmSamples) = sizeof\((?P<count_name>k(?:InputRequired|Complete)Pcm)\) / sizeof\((?P=count_name)\[0\]\);\s*"
        r"const uint32_t (?P<rate_name>k(?:InputRequired|Complete)PcmSampleRate) = (?P<rate_value>\d+);",
        re.S,
    )
    assets = {}
    for match in pattern.finditer(text):
        sample_values = [int(token) for token in re.findall(r"-?\d+", match.group("body"))]
        assets[match.group("name")] = {
            "samples": sample_values,
            "len_name": match.group("len_name"),
            "len_value": len(sample_values),
            "rate_name": match.group("rate_name"),
            "rate_value": int(match.group("rate_value")),
        }
    return assets


class WavAssetTests(unittest.TestCase):
    def test_asset_unit_declares_both_pcm_arrays(self):
        text = HEADER.read_text()
        self.assertIn("kInputRequiredPcm", text)
        self.assertIn("kInputRequiredPcmSamples", text)
        self.assertIn("kInputRequiredPcmSampleRate", text)
        self.assertIn("kCompletePcm", text)
        self.assertIn("kCompletePcmSamples", text)
        self.assertIn("kCompletePcmSampleRate", text)

    def test_asset_source_contains_two_loud_pcm_arrays_with_matching_lengths(self):
        assets = parse_pcm_assets(SOURCE.read_text())
        self.assertEqual(set(assets), {"kInputRequiredPcm", "kCompletePcm"})

        expected_lengths = {
            "kInputRequiredPcm": "kInputRequiredPcmSamples",
            "kCompletePcm": "kCompletePcmSamples",
        }
        for name, len_name in expected_lengths.items():
            with self.subTest(asset=name):
                asset = assets[name]
                data = asset["samples"]
                self.assertEqual(asset["len_name"], len_name)
                self.assertEqual(asset["len_value"], len(data))
                self.assertGreater(len(data), 1000)
                self.assertEqual(asset["rate_name"], name.replace("Pcm", "PcmSampleRate"))
                self.assertEqual(asset["rate_value"], 22050)
                self.assertGreater(max(abs(v) for v in data), 16000)
                self.assertGreater(sum(abs(v) for v in data) / len(data), 1000)

    def test_main_uses_wav_helpers_without_duplicate_same_tick_prompt_cues(self):
        text = MAIN.read_text()

        input_required_body = extract_function_body(text, "toneInputRequired")
        complete_body = extract_function_body(text, "toneComplete")
        self.assertIn("playRaw(kInputRequiredPcm, kInputRequiredPcmSamples, kInputRequiredPcmSampleRate, false, 1, 0, true)", input_required_body)
        self.assertIn("playRaw(kCompletePcm, kCompletePcmSamples, kCompletePcmSampleRate, false, 1, 0, true)", complete_body)
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
