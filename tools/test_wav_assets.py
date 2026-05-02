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
        r"const int16_t (?P<name>k\w+Pcm)\[] = \{(?P<body>.*?)\};\s*"
        r"const size_t (?P<len_name>k\w+PcmSamples) = sizeof\((?P<count_name>k\w+Pcm)\) / sizeof\((?P=count_name)\[0\]\);\s*"
        r"const uint32_t (?P<rate_name>k\w+PcmSampleRate) = (?P<rate_value>\d+);",
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
    def test_asset_header_declares_pcm_arrays(self):
        text = HEADER.read_text()
        self.assertIn("kInputRequiredPcm", text)
        self.assertIn("kInputRequiredPcmSamples", text)
        self.assertIn("kInputRequiredPcmSampleRate", text)
        self.assertIn("kUiClickPcm", text)
        self.assertIn("kUiClickPcmSamples", text)
        self.assertIn("kUiClickPcmSampleRate", text)
        self.assertIn("kAnswerSentPcm", text)
        self.assertIn("kAnswerSentPcmSamples", text)
        self.assertIn("kAnswerSentPcmSampleRate", text)
        self.assertIn("kCompletePcm", text)
        self.assertIn("kCompletePcmSamples", text)
        self.assertIn("kCompletePcmSampleRate", text)

    def test_asset_source_contains_four_converted_openpeon_clips(self):
        assets = parse_pcm_assets(SOURCE.read_text())
        self.assertEqual(set(assets), {"kInputRequiredPcm", "kUiClickPcm", "kAnswerSentPcm", "kCompletePcm"})
        for name in ("kInputRequiredPcm", "kUiClickPcm", "kAnswerSentPcm", "kCompletePcm"):
            with self.subTest(asset=name):
                asset = assets[name]
                data = asset["samples"]
                self.assertGreater(len(data), 700)
                self.assertLessEqual(len(data), 4096)
                self.assertEqual(asset["rate_value"], 11025)
                self.assertGreater(max(abs(v) for v in data), 2000)
                self.assertGreater(sum(abs(v) for v in data) / len(data), 100)

    def test_main_uses_pcm_assets_and_single_input_cue_dispatch(self):
        text = MAIN.read_text()
        input_required_body = extract_function_body(text, "toneInputRequired")
        ui_click_body = extract_function_body(text, "toneUiClick")
        answer_sent_body = extract_function_body(text, "toneAnswerSent")
        complete_body = extract_function_body(text, "toneComplete")
        denied_body = extract_function_body(text, "toneDenied")
        warning_body = extract_function_body(text, "toneWarning")
        event_error_body = extract_function_body(text, "toneEventError")
        event_neutral_body = extract_function_body(text, "toneEventNeutral")
        reset_confirm_body = extract_function_body(text, "toneResetConfirm")
        pairing_body = extract_function_body(text, "tonePairing")

        self.assertIn("playRaw(kInputRequiredPcm, kInputRequiredPcmSamples, kInputRequiredPcmSampleRate, false, 1, 0, true)", input_required_body)
        self.assertIn("playRaw(kUiClickPcm, kUiClickPcmSamples, kUiClickPcmSampleRate, false, 1, 0, true)", ui_click_body)
        self.assertIn("playRaw(kAnswerSentPcm, kAnswerSentPcmSamples, kAnswerSentPcmSampleRate, false, 1, 0, true)", answer_sent_body)
        self.assertIn("playRaw(kCompletePcm, kCompletePcmSamples, kCompletePcmSampleRate, false, 1, 0, true)", complete_body)
        self.assertIn("waitForSpeakerStart(30)", input_required_body)
        self.assertIn("waitForSpeakerStart(30)", ui_click_body)
        self.assertIn("waitForSpeakerStart(30)", answer_sent_body)
        self.assertIn("waitForSpeakerStart(30)", complete_body)
        self.assertIn("beep(600, 60);", denied_body)
        self.assertIn("beep(1400, 60);", warning_body)
        self.assertIn("beep(500, 120);", event_error_body)
        self.assertIn("beep(1000, 60);", event_neutral_body)
        self.assertIn("beep(800, 200);", reset_confirm_body)
        self.assertIn("beep(1800, 60);", pairing_body)
        self.assertIn("M5.Speaker.setVolume(255);", text)
        self.assertIn("M5.Speaker.setAllChannelVolume(255);", text)
        self.assertGreaterEqual(text.count("toneUiClick();"), 8)
        self.assertIn("toneWarning();", text)
        self.assertIn("toneResetConfirm();", text)
        self.assertIn("tonePairing();", text)
        self.assertIn("bool inputRequiredCue = false;", text)
        self.assertIn("if (!samePromptAndPendingArrival) inputRequiredCue = true;", text)
        self.assertIn("if (tama.nPending > 0) {", text)
        self.assertIn("if (inputRequiredCue) toneInputRequired();", text)
        self.assertIn("bool awaitingPromptClear = responseSent && (tama.promptId[0] || tama.nPending > 0);", text)
        self.assertGreaterEqual(text.count("if (awaitingPromptClear) {"), 2)


if __name__ == "__main__":
    unittest.main()
