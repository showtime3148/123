import base64
import io
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.main import app, DATABASE, INDEX


class StudyDeskTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_import_keeps_sources_and_multiline_answer(self):
        self.assertEqual(len(DATABASE["entries"]), 62)
        self.assertEqual(len(DATABASE["tasks"]), 3)
        row = next(r for r in DATABASE["entries"] if r["id"] == "l1-9")
        self.assertIn("View access", row["original_answer"])
        self.assertIn("ChromeVox", row["answer"])
        self.assertEqual(row["verification"], "editorial_suggestion")
        self.assertEqual(len([r for r in DATABASE["entries"] if r.get("correction_reason")]), 13)

    def test_all_questions_with_options_match_correctly(self):
        for entry in INDEX.entries:
            with self.subTest(entry=entry["id"]):
                result = self.client.post("/api/answer", json={
                    "text": entry["question"] + "\n" + "\n".join(reversed(entry["options"]))
                }).json()
                self.assertEqual(result["mode"], "local")
                self.assertEqual(result["match"]["id"], entry["id"])

    def test_ocr_like_typo(self):
        row = INDEX.entries[0]
        query = row["question"].replace("educator", "educat0r").replace("Google", "GoogIe")
        matches, confident = INDEX.search(query)
        self.assertTrue(confident)
        self.assertEqual(matches[0]["id"], "l1-1")

    def test_unrelated_and_answer_only_do_not_auto_match(self):
        for text in ["What is the mass of Jupiter and its moons?", "Google Meet", "Pivot table, Column stats"]:
            with self.subTest(text=text), patch.dict("os.environ", {"GCE_OPENAI_API_KEY": ""}):
                result = self.client.post("/api/answer", json={"text": text}).json()
                self.assertEqual(result["mode"], "needs_key")

    def test_real_screenshot_ocr_then_retrieval(self):
        lines = [
            "An educator wants to update the font of their entire Google Site.",
            "Which of these features would accomplish this?",
            "Preview", "Pages", "Settings", "Theme",
        ]
        image = Image.new("RGB", (1500, 500), "white")
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
        draw = ImageDraw.Draw(image)
        for i, line in enumerate(lines):
            draw.text((30, 30 + i * 65), line, font=font, fill="black")
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        response = self.client.post("/api/ocr", json={"image": base64.b64encode(stream.getvalue()).decode()})
        self.assertEqual(response.status_code, 200, response.text)
        result = self.client.post("/api/answer", json={"text": response.json()["text"]}).json()
        self.assertEqual(result["match"]["id"], "l1-1")
        self.assertEqual(result["match"]["answer"], "Theme")

    def test_reject_invalid_image_and_cross_origin(self):
        self.assertEqual(self.client.post("/api/ocr", json={"image": "not-a-picture"}).status_code, 400)
        self.assertEqual(self.client.post("/api/answer", json={"text": "Google Meet"},
                                         headers={"Origin": "https://other.example"}).status_code, 403)
        self.assertEqual(self.client.get("/", headers={"Host": "attacker.example"}).status_code, 400)

    def test_web_fallback_requires_search_and_sources(self):
        fake = {
            "status": "completed",
            "output": [
                {"type": "web_search_call", "status": "completed"},
                {"type": "message", "content": [
                    {"type": "output_text", "text": "공식 문서에 따른 답변입니다.",
                     "annotations": [{"type": "url_citation", "url": "https://support.google.com/",
                                      "title": "Google 도움말"}]}
                ]}
            ]
        }
        async def post(*args, **kwargs):
            self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-only-placeholder")
            self.assertFalse(kwargs["json"]["store"])
            self.assertEqual(kwargs["json"]["tool_choice"], "required")
            return httpx.Response(200, json=fake)
        with patch("app.main.httpx.AsyncClient.post", side_effect=post):
            response = self.client.post("/api/answer", json={"text": "An entirely new question about Gemini."},
                                        headers={"X-API-Key": "test-only-placeholder"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "web")
        self.assertEqual(len(response.json()["sources"]), 1)
        fake["output"][1]["content"][0]["annotations"] = []
        with patch("app.main.httpx.AsyncClient.post", side_effect=post):
            response = self.client.post("/api/answer", json={"text": "An entirely new question about Gemini."},
                                        headers={"X-API-Key": "test-only-placeholder"})
        self.assertEqual(response.status_code, 502)

    def test_forced_web_and_auth_error(self):
        with patch("app.main.httpx.AsyncClient.post", return_value=httpx.Response(401)):
            response = self.client.post("/api/answer", json={
                "text": INDEX.entries[0]["question"], "force_web": True
            }, headers={"X-API-Key": "test-only-placeholder"})
        self.assertEqual(response.status_code, 502)
        self.assertIn("API 키", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
