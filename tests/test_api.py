import unittest
from fastapi.testclient import TestClient
from orchestrator.api.main import app, sanitize_extra_env

class TestApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["version"], "1.0.0")

    def test_metrics_endpoint(self):
        response = self.client.get("/api/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("memory", data)
        self.assertIn("active_sessions", data)

    def test_app_whitelist_validation(self):
        # Unlisted binary should be rejected with 400
        response = self.client.post("/api/sessions", json={"app_path": "cmd.exe"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("not permitted", response.json()["detail"])

        response = self.client.post("/api/sessions", json={"app_path": "powershell.exe"})
        self.assertEqual(response.status_code, 400)

        response = self.client.post("/api/sessions", json={"app_path": "../../evil.exe"})
        self.assertEqual(response.status_code, 400)

    def test_env_whitelist_sanitization(self):
        raw_env = {
            "LD_PRELOAD": "/evil.so",
            "PATH": "/evil/bin",
            "APP_CUSTOM_TITLE": "My Application",
            "WIN32_COLOR_THEME": "Dark",
            "PYTHONPATH": "/fake"
        }
        clean = sanitize_extra_env(raw_env)
        self.assertEqual(clean, {
            "APP_CUSTOM_TITLE": "My Application",
            "WIN32_COLOR_THEME": "Dark"
        })
        self.assertNotIn("LD_PRELOAD", clean)
        self.assertNotIn("PATH", clean)
        self.assertNotIn("PYTHONPATH", clean)

if __name__ == "__main__":
    unittest.main()
