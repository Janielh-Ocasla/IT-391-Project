"""API contract checks without connecting to Supabase or sending email."""
import io
import runpy
import unittest
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit

from Backend import main

USER_ID = "00000000-0000-4000-8000-000000000001"
TASK_ID = "00000000-0000-4000-8000-000000000002"


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        url = attrs.get("src") if tag in {"img", "script"} else attrs.get("href") if tag == "link" else None
        if url and not urlsplit(url).scheme:
            self.urls.append(url)


class ApiTests(unittest.TestCase):
    def setUp(self):
        main.app.config.update(TESTING=True)
        self.client = main.app.test_client()
        self.manager = MagicMock()
        self.manager.supabase.options.headers = {}
        self.manager.supabase.auth.get_user.return_value = SimpleNamespace(
            user=SimpleNamespace(id=USER_ID)
        )
        query = self.manager.supabase.table.return_value
        query.select.return_value = query
        query.eq.return_value = query
        query.single.return_value = query
        query.limit.return_value = query
        query.execute.return_value = SimpleNamespace(data={"role": "volunteer"})
        self.headers = {"Authorization": "Bearer volunteer-token"}

    def check_json(self, response, status):
        self.assertEqual(response.status_code, status)
        self.assertTrue(response.is_json)
        self.assertEqual(response.json["ok"], status < 400)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        if status >= 400:
            self.assertIsInstance(response.json["error"], str)
        return response.json

    def test_pages_and_all_local_assets_are_served(self):
        for path in ("/", "/home.html", "/index.html", "/about", "/about.html", "/donate.html", "/volunteer.html"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn("/static/js/api.js", html)
                self.assertIn("/static/js/site.js", html)
                parser = Assets()
                parser.feed(html)
                for asset in parser.urls:
                    with self.client.get(asset) as asset_response:
                        self.assertEqual(asset_response.status_code, 200, asset)

    def test_legacy_entrypoint_uses_the_same_app(self):
        entry = Path(main.SITE_DIR) / "app.py"
        self.assertIs(runpy.run_path(str(entry))["app"], main.app)

    def test_public_endpoints_and_http_errors(self):
        self.check_json(self.client.get("/api/health"), 200)
        self.assertFalse(self.check_json(self.client.get("/api/me"), 200)["logged_in"])
        self.check_json(self.client.post("/api/logout"), 200)
        self.check_json(self.client.get("/api/missing"), 404)
        response = self.client.get("/api/login")
        self.check_json(response, 405)
        self.assertIn("POST", response.headers["Allow"])

    def test_protected_endpoints_require_token_before_client_creation(self):
        paths = (
            ("GET", "/api/tasks"), ("GET", "/api/announcements"),
            ("POST", "/api/announcements"), ("PUT", f"/api/announcements/{TASK_ID}"),
            ("DELETE", f"/api/announcements/{TASK_ID}"),
            ("GET", "/api/assignments/status"),
            *(('POST', f'/api/tasks/{TASK_ID}/{action}') for action in ('pick', 'cancel', 'submit', 'photo')),
            ("POST", f"/api/assignments/{TASK_ID}/verify"),
        )
        with patch.multiple(main, Task=MagicMock(), Announcement=MagicMock(), Assignment=MagicMock()):
            for method, path in paths:
                with self.subTest(path=path, method=method):
                    self.check_json(self.client.open(path, method=method), 401)
            main.Task.assert_not_called()
            main.Announcement.assert_not_called()
            main.Assignment.assert_not_called()

    def test_login_validation_and_token_response(self):
        with patch.object(main, "Account", return_value=self.manager):
            for body in (None, [], {}, {"email": 5, "password": "test"}):
                self.check_json(self.client.post("/api/login", json=body), 400)
            self.manager.login.return_value = (False, None, None)
            self.check_json(self.client.post("/api/login", json={"email": "v@example.com", "password": "bad"}), 401)
            self.manager.login.return_value = (True, "volunteer", SimpleNamespace(access_token="issued-token"))
            data = self.check_json(self.client.post("/api/login", json={"email": "v@example.com", "password": "password"}), 200)
            self.assertEqual(data["access_token"], "issued-token")
            self.assertEqual(data["role"], "volunteer")

    def test_me_checks_token_and_profile(self):
        with patch.object(main, "Account", return_value=self.manager):
            response = self.client.get("/api/me", headers=self.headers)
            data = self.check_json(response, 200)
            self.assertEqual((data["user_id"], data["role"]), (USER_ID, "volunteer"))
            self.manager.supabase.auth.get_user.assert_called_once_with("volunteer-token")
            self.manager.supabase.postgrest.auth.assert_called_once_with("volunteer-token")
            self.assertEqual(self.manager.supabase.options.headers["Authorization"], "Bearer volunteer-token")
            self.manager.supabase.auth.get_user.side_effect = ValueError("expired")
            self.check_json(self.client.get("/api/me", headers=self.headers), 401)
            self.check_json(self.client.get("/api/me", headers={"Authorization": "Basic abc"}), 401)

    def test_registration_alias_stays_paused(self):
        body = dict(email="v@example.com", password="password", first_name="Test", last_name="Volunteer")
        with patch.object(main, "Account") as account:
            first = self.client.post("/api/register", json=body)
            second = self.client.post("/api/signup", json=body)
            self.check_json(first, 503)
            self.assertEqual(first.json, second.json)
            account.assert_not_called()

    def test_reset_password_validates_body_and_hides_account_existence(self):
        with patch.object(main, "Account", return_value=self.manager):
            for body in ([], {}, {"email": 1}):
                self.check_json(self.client.post("/api/reset-password", json=body), 400)
            first = self.client.post("/api/reset-password", json={"email": "v@example.com"})
            self.check_json(first, 200)
            self.manager.reset_password.return_value = None
            second = self.client.post("/api/reset-password", json={"email": "missing@example.com"})
            self.assertEqual(first.json, second.json)

    def test_list_responses_use_named_arrays(self):
        for factory, method, path, key in (
            ("Task", "list_task", "/api/tasks", "tasks"),
            ("Announcement", "list_announcements", "/api/announcements", "announcements"),
            ("Assignment", "track_task_status", "/api/assignments/status", "assignments"),
        ):
            with self.subTest(path=path), patch.object(main, factory, return_value=self.manager):
                getattr(self.manager, method).return_value = []
                data = self.check_json(self.client.get(path, headers=self.headers), 200)
                self.assertEqual(data[key], [])

    def test_admin_routes_reject_volunteers(self):
        with patch.object(main, "Announcement", return_value=self.manager):
            self.check_json(self.client.post("/api/announcements", json={"title": "t", "content": "c"}, headers=self.headers), 403)
            self.manager.create_announcement.assert_not_called()
        with patch.object(main, "Assignment", return_value=self.manager):
            self.check_json(self.client.post(f"/api/assignments/{TASK_ID}/verify", json={"approved": True}, headers=self.headers), 403)
            self.manager.verify_delivery.assert_not_called()

    def test_admin_can_create_announcement_and_verify_assignment(self):
        query = self.manager.supabase.table.return_value
        query.execute.return_value = SimpleNamespace(data={"role": "admin"})
        with patch.object(main, "Announcement", return_value=self.manager):
            self.manager.create_announcement.return_value = True
            self.check_json(self.client.post("/api/announcements", json={"title": "Title", "content": "Content"}, headers=self.headers), 201)
        with patch.object(main, "Assignment", return_value=self.manager):
            self.manager.verify_delivery.return_value = [{"id": TASK_ID, "status": "completed"}]
            self.check_json(self.client.post(f"/api/assignments/{TASK_ID}/verify", json={"approved": True}, headers=self.headers), 200)
            self.manager.verify_delivery.assert_called_once_with(USER_ID, TASK_ID, True)
            self.check_json(self.client.post(f"/api/assignments/{TASK_ID}/verify", json={"approved": "true"}, headers=self.headers), 400)

    def test_photo_upload_validation_and_multipart_contract(self):
        with patch.object(main, "Assignment", return_value=self.manager):
            path = f"/api/tasks/{TASK_ID}/photo"
            self.check_json(self.client.post(path, headers=self.headers), 400)
            self.check_json(self.client.post(path, data={"photo": (io.BytesIO(b"data"), "photo.txt")}, headers=self.headers), 400)
            self.manager.upload_photo.return_value = f"{USER_ID}/{TASK_ID}/photo.png"
            data = self.check_json(self.client.post(path, data={"photo": (io.BytesIO(b"image"), "photo.png")}, headers=self.headers), 200)
            self.assertIn("photo_path", data)
            with patch.dict(main.app.config, MAX_CONTENT_LENGTH=100):
                self.check_json(self.client.post(path, data={"photo": (io.BytesIO(b"x" * 200), "photo.png")}, headers=self.headers), 413)

    def test_unexpected_failure_returns_json_without_details(self):
        with patch.dict(main.app.config, TESTING=False), patch.object(main, "Task", side_effect=RuntimeError("private detail")), self.assertLogs(main.app.logger, level="ERROR"):
            response = self.client.get("/api/tasks", headers=self.headers)
        data = self.check_json(response, 500)
        self.assertNotIn("private detail", data["error"])


if __name__ == "__main__":
    unittest.main()
