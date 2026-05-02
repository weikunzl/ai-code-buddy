#!/usr/bin/env python3
import json
import pathlib
import unittest

import hook_relay
import post_notification_prompt


ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs" / "examples"


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.body


class WorkflowExampleTests(unittest.TestCase):
    def load(self, name: str) -> bytes:
        return (EXAMPLES / name).read_bytes()

    def test_hook_user_prompt_submit_example_forwards_through_relay(self):
        seen = {}

        def fake_urlopen(req, timeout=0):
            seen["payload"] = json.loads(req.data.decode("utf-8"))
            return _FakeResponse(b"{}")

        rc = hook_relay.forward_hook(
            self.load("hook-user-prompt-submit.json"),
            url="http://127.0.0.1:9876",
            timeout=2.0,
            strict=True,
            stdout=_StringSink(),
            stderr=_StringSink(),
            urlopen=fake_urlopen,
        )

        self.assertEqual(rc, 0)
        self.assertEqual(seen["payload"]["hook_event_name"], "UserPromptSubmit")
        self.assertEqual(seen["payload"]["session_id"], "s_demo_hook")

    def test_hook_user_prompt_submit_zh_example_preserves_utf8(self):
        seen = {}

        def fake_urlopen(req, timeout=0):
            seen["payload"] = json.loads(req.data.decode("utf-8"))
            return _FakeResponse(b"{}")

        rc = hook_relay.forward_hook(
            self.load("hook-user-prompt-submit-zh.json"),
            url="http://127.0.0.1:9876",
            timeout=2.0,
            strict=True,
            stdout=_StringSink(),
            stderr=_StringSink(),
            urlopen=fake_urlopen,
        )

        self.assertEqual(rc, 0)
        self.assertEqual(seen["payload"]["prompt"], "请检查中文渲染和布局")

    def test_single_choice_prompt_example_wraps_and_forwards(self):
        seen = {}

        def fake_urlopen(req, timeout=0):
            seen["payload"] = json.loads(req.data.decode("utf-8"))
            return _FakeResponse(b'{"decision":"usb"}')

        rc = post_notification_prompt.forward_notification_prompt(
            self.load("prompt-single-choice.json"),
            url="http://127.0.0.1:9876",
            timeout=35.0,
            strict=True,
            stdout=_StringSink(),
            stderr=_StringSink(),
            urlopen=fake_urlopen,
        )

        self.assertEqual(rc, 0)
        self.assertEqual(seen["payload"]["hook_event_name"], "Notification")
        self.assertEqual(seen["payload"]["prompt"]["kind"], "single_choice")

    def test_single_choice_prompt_zh_example_wraps_and_forwards(self):
        seen = {}

        def fake_urlopen(req, timeout=0):
            seen["payload"] = json.loads(req.data.decode("utf-8"))
            return _FakeResponse(b'{"decision":"usb"}')

        rc = post_notification_prompt.forward_notification_prompt(
            self.load("prompt-single-choice-zh.json"),
            url="http://127.0.0.1:9876",
            timeout=35.0,
            strict=True,
            stdout=_StringSink(),
            stderr=_StringSink(),
            urlopen=fake_urlopen,
        )

        self.assertEqual(rc, 0)
        prompt = seen["payload"]["prompt"]
        self.assertEqual(prompt["title"], "传输方式")
        self.assertEqual(prompt["options"][1]["label"], "USB 串口直连")

    def test_multi_choice_prompt_ja_example_wraps_and_forwards(self):
        seen = {}

        def fake_urlopen(req, timeout=0):
            seen["payload"] = json.loads(req.data.decode("utf-8"))
            return _FakeResponse(b'{"choices":["ble","tone"]}')

        rc = post_notification_prompt.forward_notification_prompt(
            self.load("prompt-multi-choice-ja.json"),
            url="http://127.0.0.1:9876",
            timeout=35.0,
            strict=True,
            stdout=_StringSink(),
            stderr=_StringSink(),
            urlopen=fake_urlopen,
        )

        self.assertEqual(rc, 0)
        prompt = seen["payload"]["prompt"]
        self.assertEqual(prompt["kind"], "multi_choice")
        self.assertEqual(prompt["title"], "通知方法")
        self.assertEqual(prompt["options"][2]["label"], "効果音")

    def test_free_text_required_prompt_example_wraps_and_forwards(self):
        seen = {}

        def fake_urlopen(req, timeout=0):
            seen["payload"] = json.loads(req.data.decode("utf-8"))
            return _FakeResponse(b'{"decision":"here"}')

        rc = post_notification_prompt.forward_notification_prompt(
            self.load("prompt-free-text-required.json"),
            url="http://127.0.0.1:9876",
            timeout=35.0,
            strict=True,
            stdout=_StringSink(),
            stderr=_StringSink(),
            urlopen=fake_urlopen,
        )

        self.assertEqual(rc, 0)
        self.assertEqual(seen["payload"]["hook_event_name"], "Notification")
        self.assertEqual(seen["payload"]["prompt"]["kind"], "free_text_required")
        self.assertEqual(seen["payload"]["prompt"]["options"][0]["id"], "here")

    def test_free_text_required_prompt_ko_example_wraps_and_forwards(self):
        seen = {}

        def fake_urlopen(req, timeout=0):
            seen["payload"] = json.loads(req.data.decode("utf-8"))
            return _FakeResponse(b'{"decision":"tmp"}')

        rc = post_notification_prompt.forward_notification_prompt(
            self.load("prompt-free-text-required-ko.json"),
            url="http://127.0.0.1:9876",
            timeout=35.0,
            strict=True,
            stdout=_StringSink(),
            stderr=_StringSink(),
            urlopen=fake_urlopen,
        )

        self.assertEqual(rc, 0)
        prompt = seen["payload"]["prompt"]
        self.assertEqual(prompt["title"], "대상 확인")
        self.assertEqual(prompt["options"][1]["label"], "임시 디렉터리")


class _StringSink:
    def __init__(self) -> None:
        self.parts: list[str] = []

    def write(self, s: str) -> None:
        self.parts.append(s)

    def flush(self) -> None:
        return


if __name__ == "__main__":
    unittest.main()
