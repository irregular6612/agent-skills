import json
import tempfile
import unittest
from pathlib import Path

from collect import collect


class CollectTests(unittest.TestCase):
    def test_kst_date_and_prose_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            codex = root / "codex"
            claude = root / "claude"
            codex.mkdir()
            claude.mkdir()
            (codex / "one.jsonl").write_text(
                "\n".join(
                    json.dumps(row, ensure_ascii=False)
                    for row in [
                        {"timestamp": "2026-10-01T14:59:59Z", "type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "어제 말"}]}},
                        {"timestamp": "2026-10-01T15:00:00Z", "type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "오늘 질문"}]}},
                        {"timestamp": "2026-10-01T15:02:00Z", "type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "오늘 배움"}]}},
                        {"timestamp": "2026-10-01T15:03:00Z", "type": "response_item", "payload": {"type": "custom_tool_call_output", "output": "비밀 도구 출력"}},
                    ]
                ), encoding="utf-8"
            )
            (claude / "two.jsonl").write_text(
                "\n".join(
                    json.dumps(row, ensure_ascii=False)
                    for row in [
                        {"timestamp": "2026-10-02T01:00:00Z", "type": "user", "message": {"role": "user", "content": "클로드 질문"}},
                        {"timestamp": "2026-10-02T01:01:00Z", "type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "클로드 배움"}]}},
                        {"timestamp": "2026-10-02T01:02:00Z", "type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "비밀 결과"}]}},
                    ]
                ), encoding="utf-8"
            )
            result = collect("2026-10-02", codex, claude)
            texts = [message["text"] for message in result]
            self.assertEqual(texts, ["오늘 질문", "오늘 배움", "클로드 질문", "클로드 배움"])


if __name__ == "__main__":
    unittest.main()
