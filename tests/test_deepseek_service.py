"""DeepSeek contract tests: fake credentials and mocked HTTP only."""
import io
import json
import os
import socket
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock, patch

from services.llm_service import (
    DIAGNOSIS_SCHEMA, RESPONSES_URL, ROOT, SCHEMA_NAME,
    DiagnosisError, analyze_code, normalize_diagnosis,
)
from services.problem_service import get_problem


DIAGNOSIS = {
    "error_type": "边界条件错误",
    "knowledge": "列表索引与循环边界",
    "analysis": "最后一次循环访问了不存在的下一项。",
    "hints": ["检查最后一次循环。", "列出长度为一时的索引。", "让下一项索引始终小于列表长度。"],
}


def message_output(content):
    return [{
        "type": "message",
        "id": "msg_test",
        "status": "completed",
        "role": "assistant",
        "content": [{"type": "output_text", "text": content}],
    }]


def api_response(content=None, *, status="completed", output=None, **changes):
    if content is None and output is None:
        content = json.dumps(DIAGNOSIS, ensure_ascii=False)
    result = {
        "id": "resp_test",
        "object": "response",
        "created_at": 0,
        "model": "deepseek-flash",
        "status": status,
        "output": message_output(content) if output is None else output,
    }
    result.update(changes)
    return result


class DeepSeekTests(unittest.TestCase):
    def setUp(self):
        # Never load the real .env or allow a request to escape the mock.
        self.env = patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fake-test-key", "DEEPSEEK_MODEL": "deepseek-flash"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.dotenv = patch("services.llm_service.load_dotenv")
        self.load_dotenv = self.dotenv.start()
        self.addCleanup(self.dotenv.stop)
        self.http = patch("services.llm_service.urlopen")
        self.urlopen = self.http.start()
        self.addCleanup(self.http.stop)

    def reply(self, body):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.urlopen.return_value = response

    def test_structured_output_request_and_response_parsing(self):
        self.reply(api_response())
        code = "# 检查下一项\nfor i in range(len(nums)):\n    print(nums[i + 1])"
        result = normalize_diagnosis(analyze_code(code, get_problem(1)))
        self.assertEqual(result["hints"], DIAGNOSIS["hints"])
        self.assertEqual(result["error_type"], "边界条件错误")
        self.assertIs(result["is_mock"], False)
        self.assertEqual(result["source"], "deepseek")
        self.assertEqual(result["model"], "deepseek-flash")

        self.urlopen.assert_called_once()
        request = self.urlopen.call_args.args[0]
        self.assertEqual(request.full_url, RESPONSES_URL)
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "deepseek-flash")
        self.assertEqual(payload["reasoning"], {"effort": "none"})
        self.assertEqual(payload["max_output_tokens"], 1800)
        self.assertIs(payload["stream"], False)
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertEqual(payload["text"]["format"]["name"], SCHEMA_NAME)
        self.assertEqual(payload["text"]["format"]["schema"], DIAGNOSIS_SCHEMA)
        self.assertEqual(DIAGNOSIS_SCHEMA["required"],
                         ["error_type", "knowledge", "analysis", "hints"])
        self.assertIs(DIAGNOSIS_SCHEMA["additionalProperties"], False)
        self.assertEqual(DIAGNOSIS_SCHEMA["properties"]["hints"],
                         {"type": "array", "items": {"type": "string"}})
        self.assertNotIn("minItems", DIAGNOSIS_SCHEMA["properties"]["hints"])
        self.assertNotIn("maxItems", DIAGNOSIS_SCHEMA["properties"]["hints"])
        for absent in ("response_format", "thinking", "max_tokens", "tools"):
            self.assertNotIn(absent, payload)

        prompt = payload["instructions"]
        self.assertEqual(prompt, (ROOT / "prompts" / "diagnose_prompt.txt").read_text(encoding="utf-8"))
        self.assertIn("JSON", prompt)
        self.assertNotIn("fake-test-key", prompt)
        user = json.loads(payload["input"])
        self.assertEqual(user["code"], code)
        self.assertEqual(user["problem"]["title_zh"], "两数之和")
        for field in ("summary", "examples", "constraints", "tags"):
            self.assertEqual(user["problem"][field], get_problem(1)[field])
        self.assertIn("Authorization", request.headers)
        self.assertGreater(self.urlopen.call_args.kwargs["timeout"], 0)

    def test_reasoning_items_are_ignored_and_multiple_output_parts_are_joined(self):
        content = json.dumps(DIAGNOSIS, ensure_ascii=False)
        self.reply(api_response(output=[
            {"type": "reasoning", "content": [{"type": "reasoning_text", "text": "not used"}]},
            {"type": "message", "content": [
                {"type": "output_text", "text": content[:12]},
                {"type": "output_text", "text": content[12:]},
            ]},
        ]))
        result = analyze_code("pass")
        self.assertEqual(result["hints"], DIAGNOSIS["hints"])
        self.assertEqual(result["source"], "deepseek")

    def test_dotenv_is_rooted_at_project_and_does_not_override_environment(self):
        self.reply(api_response())
        analyze_code("pass")
        self.load_dotenv.assert_called_once_with(ROOT / ".env", override=False, encoding="utf-8")

    def test_single_argument_is_supported_and_source_is_never_executed(self):
        self.reply(api_response(json.dumps({**DIAGNOSIS, "source": "rules", "is_mock": True})))
        with patch("builtins.print", side_effect=AssertionError("student code executed")):
            result = analyze_code("print('never execute')")
        self.assertEqual(result["source"], "deepseek")
        self.assertIs(result["is_mock"], False)
        payload = json.loads(self.urlopen.call_args.args[0].data)
        self.assertEqual(json.loads(payload["input"])["problem"], {})

    def test_missing_credentials_empty_or_invalid_code_make_no_http_request(self):
        os.environ["DEEPSEEK_API_KEY"] = ""
        with self.assertRaisesRegex(DiagnosisError, "DEEPSEEK_API_KEY"):
            analyze_code("pass")
        with self.assertRaises(DiagnosisError):
            analyze_code("  ")
        with self.assertRaises(TypeError):
            analyze_code(None)
        self.urlopen.assert_not_called()

    def test_http_failures_are_actionable_sanitized_and_never_retried(self):
        for status, message in ((401, "认证"), (402, "余额"), (429, "频繁"), (500, "暂不可用"),
                                (400, "模型"), (422, "参数")):
            with self.subTest(status=status):
                self.urlopen.reset_mock()
                self.urlopen.side_effect = HTTPError(RESPONSES_URL, status, "fake-test-key",
                                                     {}, io.BytesIO(b'fake-test-key'))
                with self.assertRaises(DiagnosisError) as caught:
                    analyze_code("pass")
                self.assertIn(str(status), str(caught.exception))
                self.assertIn(message, str(caught.exception))
                self.assertNotIn("fake-test-key", str(caught.exception))
                self.assertIsNone(caught.exception.__cause__)
                self.urlopen.assert_called_once()

    def test_network_and_read_timeouts_do_not_leak_transport_details(self):
        for error, message in ((TimeoutError("fake-test-key"), "超时"),
                               (URLError(socket.timeout("fake-test-key")), "超时"),
                               (URLError("fake-test-key"), "连接"),
                               (OSError("fake-test-key"), "未能完成")):
            with self.subTest(error=type(error).__name__):
                self.urlopen.reset_mock()
                self.urlopen.side_effect = error
                with self.assertRaises(DiagnosisError) as caught:
                    analyze_code("pass")
                self.assertIn(message, str(caught.exception))
                self.assertNotIn("fake-test-key", str(caught.exception))
                self.urlopen.assert_called_once()
        self.urlopen.side_effect = None
        self.reply(api_response())
        self.urlopen.return_value.__enter__.return_value.read.side_effect = TimeoutError("fake-test-key")
        with self.assertRaisesRegex(DiagnosisError, "超时"):
            analyze_code("pass")

    def test_empty_invalid_or_truncated_envelopes_are_rejected(self):
        content = json.dumps(DIAGNOSIS)
        bodies = (
            {}, [], {"output": message_output(content)}, {"status": "completed"},
            {"status": "completed", "output": []},
            api_response(status="incomplete"), api_response(status="failed"),
            {"status": "completed", "output": [None]},
            {"status": "completed", "output": [{"type": "message"}]},
            {"status": "completed", "output": [{"type": "message", "content": []}]},
            api_response(content=""), api_response(output=[
                {"type": "message", "content": [{"type": "output_text", "text": None}]}]),
            api_response(content="not JSON"),
            {"status": "completed", "output": [{"type": "reasoning", "content": [
                {"type": "reasoning_text", "text": content}]}]},
        )
        for body in bodies:
            with self.subTest(body=body):
                self.reply(body)
                with self.assertRaises(DiagnosisError):
                    analyze_code("pass")
        for raw in (b"", b"bad JSON", b"\xff"):
            with self.subTest(raw=raw):
                self.reply({})
                self.urlopen.return_value.__enter__.return_value.read.return_value = raw
                with self.assertRaises(DiagnosisError):
                    analyze_code("pass")

    def test_ai_diagnosis_requires_all_fields_and_exactly_three_nonempty_hints(self):
        invalid = [None, [], {}, {**DIAGNOSIS, "error_type": " "},
                   {**DIAGNOSIS, "knowledge": []}, {**DIAGNOSIS, "analysis": None}]
        invalid += [{key: value for key, value in DIAGNOSIS.items() if key != missing}
                    for missing in DIAGNOSIS]
        invalid += [{**DIAGNOSIS, "hints": hints} for hints in
                    ([], ["one"], ["one", "two"], ["one", "two", "three", "four"],
                     ["one", None, "three"], ["one", "  ", "three"], "one, two, three")]
        for value in invalid:
            with self.subTest(value=value):
                self.reply(api_response(content=json.dumps(value, ensure_ascii=False)))
                with self.assertRaises(DiagnosisError):
                    analyze_code("pass")
                if isinstance(value, dict):
                    self.assertIsNone(normalize_diagnosis({**value, "source": "deepseek"}))

    def test_reasoning_is_disabled_and_unsupported_models_are_rejected(self):
        self.reply(api_response())
        analyze_code("pass")
        payload = json.loads(self.urlopen.call_args.args[0].data)
        self.assertEqual(payload["reasoning"], {"effort": "none"})
        self.assertNotIn("thinking", payload)

        os.environ["DEEPSEEK_MODEL"] = "deepseek-v4-pro"
        self.reply(api_response())
        analyze_code("pass")
        payload = json.loads(self.urlopen.call_args.args[0].data)
        self.assertEqual(payload["model"], "deepseek-v4-pro")
        self.assertEqual(payload["reasoning"], {"effort": "none"})

        os.environ["DEEPSEEK_MODEL"] = "previously-verified-model"
        self.urlopen.reset_mock()
        with self.assertRaisesRegex(DiagnosisError, "仅支持"):
            analyze_code("pass")
        self.urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
