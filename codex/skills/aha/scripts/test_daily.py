import unittest

from daily import format_post, validate_post


class DailyTests(unittest.TestCase):
    def test_short_post_with_frontmatter(self):
        post = {"publish": True, "title": "작은 실험부터", "body": "큰 질문도 작은 실험으로 나누면 확인할 수 있다.\n\n예를 들어 버튼 하나만 바꿔 반응을 본다.", "reason": ""}
        validate_post(post)
        self.assertEqual(format_post("2026-10-02", post), '---\ntitle: "작은 실험부터"\ndate: 2026-10-02\ntags:\n  - aha\n---\n\n# 작은 실험부터\n\n큰 질문도 작은 실험으로 나누면 확인할 수 있다.\n\n예를 들어 버튼 하나만 바꿔 반응을 본다.\n')

    def test_private_data_is_rejected(self):
        for body in ("연락처는 me@example.com", "키는 sk-example12345678901234567890", "파일은 /Users/name/private.txt"):
            with self.subTest(body=body):
                with self.assertRaises(ValueError):
                    validate_post({"publish": True, "title": "제목", "body": body, "reason": ""})


if __name__ == "__main__":
    unittest.main()
