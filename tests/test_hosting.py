import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.access import AccessControl, COOKIE
from app.main import app, INDEX


class HostingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = {
            "GCE_PUBLIC": "1", "GCE_KEY_MODE": "shared",
            "GCE_ACCESS_PASSWORD": "test-only-password",
            "GCE_SESSION_SECRET": "test-only-session-secret-32-characters-long",
            "GCE_OPENAI_API_KEY": "test-only-api-placeholder",
            "GCE_STATE_DIR": self.temp.name, "GCE_DAILY_WEB_LIMIT": "2",
        }
        self.access = AccessControl(self.env)
        self.original = app.state.access
        app.state.access = self.access
        self.key_patch = patch.dict("os.environ", {"GCE_OPENAI_API_KEY": self.env["GCE_OPENAI_API_KEY"]})
        self.key_patch.start()
        self.client = TestClient(app, base_url="https://testserver")

    def tearDown(self):
        self.client.close()
        self.key_patch.stop()
        app.state.access = self.original
        self.temp.cleanup()

    def login(self):
        response = self.client.post("/api/login", json={"password": self.env["GCE_ACCESS_PASSWORD"]})
        self.assertEqual(response.status_code, 200)
        return response

    def test_login_required_and_health_public(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.get("/api/library").status_code, 401)
        self.assertEqual(self.client.get("/api/config").status_code, 401)
        self.assertEqual(self.client.post("/api/ocr", json={"image": "x"}).status_code, 401)
        self.assertEqual(self.client.post("/api/answer", json={"text": "example question"}).status_code, 401)
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.headers["location"], "/login")
        self.assertEqual(self.client.get("/static/login.css").status_code, 200)
        self.assertEqual(self.client.post("/api/login", json={"password": "wrong"}).status_code, 401)

    def test_secure_session_logout_and_revocation(self):
        response = self.login()
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("Secure", response.headers["set-cookie"])
        self.assertIn("SameSite=strict", response.headers["set-cookie"])
        token = self.client.cookies.get(COOKIE)
        self.assertEqual(self.client.get("/api/library").status_code, 200)
        self.assertEqual(self.client.post("/api/logout").status_code, 200)
        self.assertFalse(self.access.authenticated(token))
        self.assertEqual(self.client.get("/api/library").status_code, 401)

    def test_no_key_exposure_and_locked_model(self):
        self.login()
        response = self.client.get("/api/config")
        self.assertNotIn(self.env["GCE_OPENAI_API_KEY"], response.text)
        self.assertNotIn(self.env["GCE_ACCESS_PASSWORD"], response.text)
        self.assertEqual(response.json()["key_mode"], "shared")
        mock = AsyncMock(return_value={"mode": "web", "answer": "mock", "sources": []})
        with patch("app.main.web_answer", mock):
            response = self.client.post("/api/answer", json={
                "text": "A new question outside the local library", "model": "expensive-user-choice",
            }, headers={"X-API-Key": "untrusted-key"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock.call_args.args[0].model, "gpt-4.1-mini")
        self.assertEqual(mock.call_args.args[1], self.env["GCE_OPENAI_API_KEY"])
        self.assertEqual(response.json()["usage"]["used"], 1)

    def test_budget_is_shared_durable_and_local_search_still_works(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            allowed = list(pool.map(lambda _: self.access.reserve_web_request(), range(8)))
        self.assertEqual(sum(allowed), 2)
        reloaded = AccessControl(self.env)
        self.assertFalse(reloaded.reserve_web_request())
        self.assertEqual(reloaded.usage()["used"], 2)
        self.login()
        with patch("app.main.web_answer", new_callable=AsyncMock) as api:
            result = self.client.post("/api/answer", json={"text": "A new question outside the local library"})
            self.assertEqual(result.status_code, 429)
            api.assert_not_awaited()
        result = self.client.post("/api/answer", json={"text": INDEX.entries[0]["question"]})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["mode"], "local")

    def test_rate_limit_and_password_change(self):
        self.login()
        token = self.client.cookies.get(COOKIE)
        for _ in range(15):
            self.client.post("/api/login", json={"password": "wrong"})
        self.assertEqual(self.client.post("/api/login", json={"password": "wrong"}).status_code, 429)
        changed = AccessControl({**self.env, "GCE_ACCESS_PASSWORD": "changed-test-password"})
        self.assertFalse(changed.authenticated(token))

    def test_session_expiry_and_cross_origin(self):
        self.login()
        token = self.client.cookies.get(COOKIE)
        with patch("app.access.time.time", return_value=10**12):
            self.assertFalse(self.access.authenticated(token))
        result = self.client.post("/api/logout", headers={"Origin": "https://elsewhere.example"})
        self.assertEqual(result.status_code, 403)
        self.assertTrue(self.access.authenticated(token))

    def test_public_mode_refuses_missing_credentials(self):
        for name in ["GCE_ACCESS_PASSWORD", "GCE_SESSION_SECRET", "GCE_STATE_DIR", "GCE_OPENAI_API_KEY"]:
            env = dict(self.env)
            del env[name]
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                AccessControl(env)
