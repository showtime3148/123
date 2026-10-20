import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from app.access import AccessControl, COOKIE
from app.main import app


class VercelTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "VERCEL": "1",
            "GCE_ACCESS_PASSWORD": "test-only-password",
            "GCE_OPENAI_API_KEY": "test-only-api-key",
            "VERCEL_URL": "example-preview.vercel.app",
            "VERCEL_PROJECT_PRODUCTION_URL": "example.vercel.app",
        }
        self.original = app.state.access
        self.access = AccessControl(self.env)
        app.state.access = self.access
        self.client = TestClient(app, base_url="https://testserver")

    def tearDown(self):
        self.client.close()
        app.state.access = self.original

    def login(self):
        response = self.client.post("/api/login", json={"password": self.env["GCE_ACCESS_PASSWORD"]})
        self.assertEqual(response.status_code, 200)
        return self.client.cookies.get(COOKIE)

    def test_no_filesystem_or_extra_database_required(self):
        with patch("app.access.Path.mkdir", side_effect=AssertionError("No writes allowed")):
            instance = AccessControl(self.env)
            token = instance.create_session()
        self.assertIsNone(instance.database)
        self.assertIsNone(instance.usage())
        self.assertTrue(AccessControl(self.env).authenticated(token))
        self.assertIn("example.vercel.app", instance.hosts)
        self.assertIn("example-preview.vercel.app", instance.hosts)

    def test_signature_tampering_expiry_and_password_rotation(self):
        token = self.access.create_session()
        self.assertTrue(self.access.authenticated(token))
        expiry, nonce, signature = token.split(".")
        self.assertFalse(self.access.authenticated(f"{int(expiry)+100}.{nonce}.{signature}"))
        self.assertFalse(self.access.authenticated(token[:-1]))
        self.assertFalse(self.access.authenticated("invalid"))
        with patch("app.access.time.time", return_value=int(expiry) + 1):
            self.assertFalse(self.access.authenticated(token))
        for key in ["GCE_ACCESS_PASSWORD", "GCE_OPENAI_API_KEY"]:
            changed = AccessControl({**self.env, key: "different-test-value"})
            self.assertFalse(changed.authenticated(token))

    def test_login_and_browser_ocr_configuration(self):
        self.assertEqual(self.client.get("/api/library").status_code, 401)
        token = self.login()
        self.assertNotIn(self.env["GCE_ACCESS_PASSWORD"], token)
        result = self.client.get("/api/config")
        self.assertEqual(result.json()["ocr_mode"], "browser")
        self.assertEqual(result.json()["key_mode"], "shared")
        self.assertIsNone(result.json()["usage"])
        self.assertNotIn(self.env["GCE_OPENAI_API_KEY"], result.text)
        self.assertTrue(self.client.get("/api/health").json()["ocr"])
        with patch("app.main.recognize", side_effect=AssertionError("Native OCR must not run")):
            self.assertEqual(self.client.post("/api/ocr", json={"image": "data"}).status_code, 400)

    def test_closing_time_blocks_login_and_paid_requests(self):
        self.login()
        app.state.access = AccessControl({**self.env, "GCE_CLOSE_AT": "2020-01-01T00:00:00+09:00"})
        with patch("app.main.web_answer", new_callable=AsyncMock) as web:
            response = self.client.post("/api/answer", json={"text": "A question not in the library"})
            self.assertEqual(response.status_code, 410)
            web.assert_not_awaited()
        self.assertEqual(self.client.post("/api/login", json={"password": self.env["GCE_ACCESS_PASSWORD"]}).status_code, 410)
        self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_expiry_is_bounded_by_close_time(self):
        now = datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp()
        end = now + 600
        close = datetime.fromtimestamp(end, timezone.utc).isoformat()
        with patch("app.access.time.time", return_value=now):
            access = AccessControl({**self.env, "GCE_CLOSE_AT": close})
            token = access.create_session()
            self.assertEqual(int(token.split(".")[0]), int(end))
        with self.assertRaises(RuntimeError):
            AccessControl({**self.env, "GCE_CLOSE_AT": "2030-01-01T12:00:00"})

    def test_logout_clears_browser_cookie(self):
        self.login()
        response = self.client.post("/api/logout")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Max-Age=0", response.headers["set-cookie"])
        self.assertIsNone(self.client.cookies.get(COOKIE))

    def test_shared_key_and_fixed_model_still_used(self):
        self.login()
        response = {"mode": "web", "answer": "mock", "sources": []}
        with patch.dict("os.environ", {"GCE_OPENAI_API_KEY": "test-only-api-key"}), \
                patch("app.main.web_answer", AsyncMock(return_value=response)) as web:
            result = self.client.post("/api/answer", json={"text": "A new question about Google Education", "model": "user-selected"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(web.call_args.args[0].model, "gpt-4.1-mini")
        self.assertEqual(web.call_args.args[1], "test-only-api-key")
        self.assertIsNone(result.json()["usage"])

    def test_missing_configuration_fails_closed(self):
        for key in ["GCE_ACCESS_PASSWORD", "GCE_OPENAI_API_KEY"]:
            env = dict(self.env)
            del env[key]
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                AccessControl(env)
