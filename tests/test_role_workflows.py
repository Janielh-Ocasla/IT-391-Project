"""Real CIC routes/managers with shared mock rows; no real network or database."""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import base64
import io
import unittest
from unittest.mock import patch

from Backend import account, announcement, assignment, history, main, task
from tests.support.mock_supabase import MockDatabase


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aN9sAAAAASUVORK5CYII="
)


class RoleWorkflowTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.output = io.StringIO()
        stack.enter_context(redirect_stdout(self.output))
        stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("Network is forbidden in mock tests")))
        self.db = MockDatabase()
        for module in (account, announcement, assignment, history, task):
            stack.enter_context(patch.object(module, "create_client", self.db.client))
        stack.enter_context(patch.dict(main.app.config, TESTING=True))
        self.client = main.app.test_client()
        self.actors = {"admin": self.db.fixture["accounts"][0],
                       "alice": self.db.fixture["accounts"][1],
                       "bob": self.db.fixture["accounts"][2]}
        self.task_ids = [row["id"] for row in self.db.fixture["tasks"]]
        self.observations = []

    def call(self, method, path, actor=None, **kwargs):
        headers = kwargs.pop("headers", {})
        if actor:
            headers["Authorization"] = "Bearer " + self.db.token(self.actors[actor]["id"])
        response = self.client.open(path, method=method, headers=headers, **kwargs)
        self.observations.append(f"{actor or 'public'} {method} {path}: HTTP {response.status_code}")
        self.assertTrue(response.is_json, path)
        self.assertEqual(response.json["ok"], response.status_code < 400)
        return response

    def login(self, actor):
        credentials = self.actors[actor]
        response = self.call("POST", "/api/login", json={
            "email": credentials["email"], "password": credentials["password"],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["role"], credentials["role"])
        return {"Authorization": "Bearer " + response.json["access_token"]}

    def pick(self, actor="alice", index=0):
        response = self.call("POST", f"/api/tasks/{self.task_ids[index]}/pick", actor)
        self.assertEqual(response.status_code, 201)
        return response.json["assignment"][0]["id"]

    def photo(self, actor="alice", index=0):
        return self.call("POST", f"/api/tasks/{self.task_ids[index]}/photo", actor,
                         data={"photo": (io.BytesIO(PNG), "MOCK_CIC_evidence.png")})

    def submit(self, actor="alice", index=0):
        return self.call("POST", f"/api/tasks/{self.task_ids[index]}/submit", actor)

    def review(self, assignment_id, approved):
        return self.call("POST", f"/api/assignments/{assignment_id}/verify", "admin",
                         json={"approved": approved})

    def test_public_registration_creates_profile_and_requires_email_confirmation(self):
        """Both aliases create Auth/profile rows; confirmation enables login and identity lookup."""
        self.db.email_autoconfirm = False
        for index, path in enumerate(("/api/register", "/api/signup"), start=1):
            with self.subTest(path=path):
                email = f"new-{index}@cic-mock.example"
                credentials = {"email": email, "password": "MockOnly!2026"}
                response = self.call("POST", path, json={
                    **credentials, "first_name": " New ", "last_name": " Volunteer ",
                })
                self.assertEqual(response.status_code, 201)
                self.assertIn("check your email", response.json["message"])
                self.assertNotIn("access_token", response.json)
                auth_user = next(row for row in self.db.accounts.values() if row["email"] == email)
                self.assertFalse(auth_user["confirmed"])
                profile = self.db.row("profiles", auth_user["id"])
                self.assertEqual((profile["email"], profile["first_name"], profile["last_name"],
                                  profile["phone"], profile["role"]),
                                 (email, "New", "Volunteer", "", "volunteer"))
                self.assertEqual(len(self.db.accounts), 3 + index)
                self.assertEqual(len(self.db.tables["profiles"]), 3 + index)
                self.assertEqual(self.call("POST", "/api/login", json=credentials).status_code, 401)

                # Simulate email confirmation locally; no confirmation email is sent.
                auth_user["confirmed"] = True
                login = self.call("POST", "/api/login", json=credentials)
                self.assertEqual(login.status_code, 200)
                self.assertEqual(login.json["role"], "volunteer")
                identity = self.call("GET", "/api/me", headers={
                    "Authorization": "Bearer " + login.json["access_token"],
                })
                self.assertEqual(identity.status_code, 200)
                self.assertTrue(identity.json["logged_in"])
                self.assertEqual((identity.json["user_id"], identity.json["role"]),
                                 (auth_user["id"], "volunteer"))
        self.observations.append("Both aliases created matching Auth/volunteer profile rows; login required simulated email confirmation.")

    def test_account_method_sends_normalized_metadata_for_profile_trigger(self):
        """Account sends normalized signup metadata; the trigger creates the profile."""
        manager = account.Account()
        with patch.object(manager.supabase.auth, "sign_up", wraps=manager.supabase.auth.sign_up) as sign_up, \
             patch.object(manager.supabase, "table", wraps=manager.supabase.table) as table:
            created = manager.create_account(" NEW@CIC-MOCK.EXAMPLE ", "MockOnly!2026", " New ", " Volunteer ", " 555-0100 ")
            sign_up.assert_called_once_with({
                "email": "new@cic-mock.example", "password": "MockOnly!2026",
                "options": {"data": {"first_name": "New", "last_name": "Volunteer", "phone": "555-0100"}},
            })
            table.assert_not_called()
        self.assertTrue(created)
        profile = next(row for row in self.db.tables["profiles"] if row["email"] == "new@cic-mock.example")
        self.assertEqual((profile["first_name"], profile["last_name"], profile["phone"], profile["role"]),
                         ("New", "Volunteer", "555-0100", "volunteer"))
        self.assertEqual(self.db.accounts[profile["id"]]["email"], profile["email"])
        self.assertEqual(len(self.db.accounts), 4)
        self.assertEqual(len(self.db.tables["profiles"]), 4)
        response = self.call("POST", "/api/login", json={"email": profile["email"], "password": "MockOnly!2026"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["role"], "volunteer")
        self.observations.append("Account passed normalized names/phone as Auth metadata without inserting a profile; the mock trigger created it.")

    def test_public_registration_cannot_create_admin(self):
        """Caller-supplied Admin roles on either alias create volunteers without Admin access."""
        for index, path in enumerate(("/api/register", "/api/signup")):
            with self.subTest(path=path):
                credentials = {"email": f"new-admin-{index}@cic-mock.example", "password": "MockOnly!2026"}
                response = self.call("POST", path, json={
                    **credentials, "first_name": "New", "last_name": "Admin", "role": "admin",
                })
                self.assertEqual(response.status_code, 201)
                profile = next(row for row in self.db.tables["profiles"] if row["email"] == credentials["email"])
                self.assertEqual(profile["role"], "volunteer")
                login = self.call("POST", "/api/login", json=credentials)
                self.assertEqual(login.status_code, 200)
                self.assertEqual(login.json["role"], "volunteer")
                before = deepcopy(self.db.tables)
                denied = self.call("POST", "/api/announcements", headers={
                    "Authorization": "Bearer " + login.json["access_token"],
                }, json={"title": "Not allowed", "content": "Not allowed"})
                self.assertEqual(denied.status_code, 403)
                self.assertEqual(self.db.tables, before)
        self.assertEqual(self.call("POST", "/api/admin/register", json={}).status_code, 404)
        self.observations.append("Both aliases ignored caller-supplied Admin roles; newly registered volunteers were denied Admin actions.")

    def test_auth_profile_trigger_ignores_role_in_user_metadata(self):
        """Even direct mock Auth signup metadata cannot assign an Admin profile role."""
        response = self.db.client().auth.sign_up({
            "email": "metadata-admin@cic-mock.example", "password": "MockOnly!2026",
            "options": {"data": {"first_name": "New", "last_name": "User", "role": "admin"}},
        })
        profile = self.db.row("profiles", response.user.id)
        self.assertEqual(profile["role"], "volunteer")
        self.assertEqual(profile["phone"], "")

    def test_duplicate_email_does_not_create_a_second_account(self):
        """Duplicate email registration through the account module is rejected."""
        alice = self.actors["alice"]
        accounts_before, tables_before = deepcopy(self.db.accounts), deepcopy(self.db.tables)
        self.assertFalse(account.Account().create_account(alice["email"], alice["password"], "New", "Name", ""))
        self.assertEqual(self.db.accounts, accounts_before)
        self.assertEqual(self.db.tables, tables_before)
        self.observations.append("Duplicate Auth email rejected; existing Auth/profile data unchanged.")

    def test_duplicate_email_through_both_aliases_preserves_existing_account(self):
        """Case/whitespace variants of an existing email fail without changing its data."""
        alice = self.actors["alice"]
        accounts_before, tables_before = deepcopy(self.db.accounts), deepcopy(self.db.tables)
        for path in ("/api/register", "/api/signup"):
            with self.subTest(path=path):
                response = self.call("POST", path, json={
                    "email": " " + alice["email"].upper() + " ", "password": "Different!2026",
                    "first_name": "Replacement", "last_name": "Name", "role": "admin",
                })
                self.assertEqual(response.status_code, 500)
                self.assertEqual(response.json, {"ok": False, "error": "Registration failed"})
                self.assertEqual(self.db.accounts, accounts_before)
                self.assertEqual(self.db.tables, tables_before)
        self.login("alice")

    def test_profile_trigger_failure_rolls_back_auth_account(self):
        """Failed profile creation rolls back signup; retry creates one Auth/profile pair."""
        accounts_before, tables_before = deepcopy(self.db.accounts), deepcopy(self.db.tables)
        manager = account.Account()
        self.db.fail_profile_insert = True
        created = manager.create_account("partial@cic-mock.example", "MockOnly!2026", "Partial", "Account", "")
        self.assertFalse(created)
        self.assertEqual(self.db.accounts, accounts_before)
        self.assertEqual(self.db.tables, tables_before)
        self.assertIsNone(manager.supabase.user_id)
        self.db.fail_profile_insert = False
        self.assertTrue(manager.create_account("partial@cic-mock.example", "MockOnly!2026", "Partial", "Account", ""))
        self.assertEqual(len(self.db.accounts), 4)
        self.assertEqual(len(self.db.tables["profiles"]), 4)
        self.observations.append("Mock profile trigger failure rolled back signup entirely; retry created exactly one Auth/profile pair.")

    def test_public_registration_trigger_failure_is_atomic(self):
        """Both aliases report trigger failures without leaving orphaned Auth/profile rows."""
        self.db.fail_profile_insert = True
        accounts_before, tables_before = deepcopy(self.db.accounts), deepcopy(self.db.tables)
        for path in ("/api/register", "/api/signup"):
            with self.subTest(path=path):
                response = self.call("POST", path, json={
                    "email": "rollback@cic-mock.example", "password": "MockOnly!2026",
                    "first_name": "Rollback", "last_name": "User",
                })
                self.assertEqual(response.status_code, 500)
                self.assertEqual(response.json, {"ok": False, "error": "Registration failed"})
                self.assertEqual(self.db.accounts, accounts_before)
                self.assertEqual(self.db.tables, tables_before)

    def test_late_profile_trigger_failure_rolls_back_both_rows(self):
        """A trigger error after the profile write also restores the complete transaction."""
        accounts_before, tables_before = deepcopy(self.db.accounts), deepcopy(self.db.tables)
        create_profile = self.db.create_profile_for_auth_user

        def create_then_fail(auth_user):
            create_profile(auth_user)
            raise RuntimeError("Simulated failure after profile creation")

        with patch.object(self.db, "create_profile_for_auth_user", side_effect=create_then_fail):
            self.assertFalse(account.Account().create_account(
                "late-failure@cic-mock.example", "MockOnly!2026", "Late", "Failure", "",
            ))
        self.assertEqual(self.db.accounts, accounts_before)
        self.assertEqual(self.db.tables, tables_before)

    def test_unconfirmed_email_and_bad_password_cannot_login(self):
        """Unconfirmed email, unknown email, and bad password cannot log in."""
        alice = self.actors["alice"]
        for email, password in ((alice["email"], "bad"), ("unknown@cic-mock.example", "MockOnly!2026")):
            self.assertEqual(self.call("POST", "/api/login", json={"email": email, "password": password}).status_code, 401)
        self.db.accounts[alice["id"]]["confirmed"] = False
        self.assertEqual(self.call("POST", "/api/login", json={"email": alice["email"], "password": alice["password"]}).status_code, 401)

    def test_both_roles_login_and_me_uses_returned_token(self):
        """Seeded Admin and Volunteer can log in and retrieve their own identity."""
        for actor in ("admin", "alice", "bob"):
            headers = self.login(actor)
            response = self.call("GET", "/api/me", headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["user_id"], self.actors[actor]["id"])
            self.assertEqual(response.json["role"], self.actors[actor]["role"])

    def test_task_visibility_depends_on_role_and_excludes_deleted_rows(self):
        """Volunteer sees open tasks; Admin sees all undeleted tasks."""
        volunteer = self.call("GET", "/api/tasks", "alice")
        admin = self.call("GET", "/api/tasks", "admin")
        self.assertEqual({row["id"] for row in volunteer.json["tasks"]}, set(self.task_ids[:2]))
        self.assertEqual({row["id"] for row in admin.json["tasks"]}, set(self.task_ids[:4]))
        self.observations.append("Volunteer: 2 open tasks; Admin: 4 undeleted tasks; deleted task hidden from both.")

    def test_volunteer_upload_submit_and_admin_approval(self):
        """Complete workflow: pick, upload, submit, Admin approval, completed task and hours."""
        assignment_id = self.pick()
        self.assertEqual(self.db.row("tasks", self.task_ids[0])["status"], "in_progress")
        self.assertEqual(self.submit().status_code, 409)
        uploaded = self.photo()
        self.assertEqual(uploaded.status_code, 200)
        photo_path = uploaded.json["photo_path"]
        self.assertEqual(self.db.objects[("task-photo", photo_path)]["bytes"], PNG)
        self.assertEqual(self.db.row("assignments", assignment_id)["photo_path"], photo_path)
        self.assertEqual(self.submit().status_code, 200)
        self.assertEqual(self.db.row("assignments", assignment_id)["status"], "submitted")
        self.assertEqual(self.review(assignment_id, True).status_code, 200)
        row = self.db.row("assignments", assignment_id)
        self.assertEqual(row["status"], "completed")
        self.assertEqual(row["reviewed_by"], self.actors["admin"]["id"])
        self.assertEqual(self.db.row("tasks", self.task_ids[0])["status"], "completed")
        hours = history.History().track_volunteer_hours(self.actors["alice"]["id"])
        self.assertEqual(hours["total_hours"], 4.0)
        self.observations.append("Storage received PNG bytes with the volunteer's bearer token; completed hours changed from 1.5 to 4.0.")

    def test_admin_rejection_allows_reupload_and_resubmission(self):
        """Admin rejection returns assignment to assigned; Volunteer can resubmit and be approved."""
        assignment_id = self.pick()
        self.assertEqual(self.photo().status_code, 200)
        self.assertEqual(self.submit().status_code, 200)
        self.assertEqual(self.review(assignment_id, False).status_code, 200)
        self.assertEqual(self.db.row("assignments", assignment_id)["status"], "assigned")
        self.assertIsNone(self.db.row("assignments", assignment_id)["submitted_at"])
        self.assertEqual(self.db.row("tasks", self.task_ids[0])["status"], "in_progress")
        self.assertEqual(self.photo().status_code, 200)
        self.assertEqual(self.submit().status_code, 200)
        self.assertEqual(self.review(assignment_id, True).status_code, 200)

    def test_cancel_reopens_task_and_another_volunteer_can_pick_it(self):
        """Cancellation preserves the old assignment and lets another volunteer pick the reopened task."""
        assignment_id = self.pick(index=1)
        path = f"/api/tasks/{self.task_ids[1]}/cancel"
        self.assertEqual(self.call("POST", path, "alice").status_code, 200)
        self.assertEqual(self.db.row("assignments", assignment_id)["status"], "cancelled")
        self.assertIsNotNone(self.db.row("assignments", assignment_id)["cancelled_at"])
        self.assertEqual(self.db.row("tasks", self.task_ids[1])["status"], "open")
        self.assertEqual(self.call("POST", path, "alice").status_code, 409)
        new_assignment = self.pick(actor="bob", index=1)
        self.assertNotEqual(new_assignment, assignment_id)
        self.assertEqual(self.db.row("assignments", new_assignment)["volunteer_id"], self.actors["bob"]["id"])

    def test_already_assigned_or_deleted_task_cannot_be_picked(self):
        """Duplicate picking and picking deleted tasks do not create assignments."""
        self.pick()
        count = len(self.db.tables["assignments"])
        for index in (0, 4):
            self.assertEqual(self.call("POST", f"/api/tasks/{self.task_ids[index]}/pick", "bob").status_code, 400)
        self.assertEqual(len(self.db.tables["assignments"]), count)

    def test_assignment_lists_do_not_leak_other_volunteers_rows(self):
        """Volunteer sees own assignments; Admin sees both volunteers' assignments."""
        self.pick()
        for actor in ("alice", "bob"):
            response = self.call("GET", "/api/assignments/status", actor)
            self.assertTrue(response.json["assignments"])
            self.assertTrue(all(row["volunteer_id"] == self.actors[actor]["id"] for row in response.json["assignments"]))
        response = self.call("GET", "/api/assignments/status", "admin")
        self.assertEqual(len(response.json["assignments"]), 3)

    def test_other_volunteers_assignment_cannot_be_cancelled_or_submitted(self):
        """Volunteer cannot cancel or submit another volunteer's assignment."""
        before = deepcopy(self.db.tables["assignments"])
        for action in ("cancel", "submit"):
            self.assertEqual(self.call("POST", f"/api/tasks/{self.task_ids[2]}/{action}", "alice").status_code, 409)
        self.assertEqual(self.db.tables["assignments"], before)

    def test_uploading_to_another_volunteers_task_returns_a_client_error(self):
        """Defect check: uploading to another volunteer's task must return 403/409, not 500."""
        before = deepcopy(self.db.tables["assignments"])
        response = self.photo(index=2)
        self.assertEqual(self.db.tables["assignments"], before)
        self.assertEqual(len(self.db.objects), 0)
        self.observations.append("Upload rejected without writing data; expected HTTP 403/409 for this client mistake.")
        self.assertIn(response.status_code, (403, 409))

    def test_admin_announcement_create_edit_delete_and_volunteer_read(self):
        """Admin can create/edit/delete announcements; Volunteer can read the changes."""
        response = self.call("POST", "/api/announcements", "admin", json={"title": " [MOCK CIC] New ", "content": " Sample "})
        self.assertEqual(response.status_code, 201)
        listed = self.call("GET", "/api/announcements", "alice").json["announcements"]
        row = next(row for row in listed if row["title"] == "[MOCK CIC] New")
        announcement_id = row["announcement_id"]
        path = f"/api/announcements/{announcement_id}"
        self.assertEqual(self.call("PUT", path, "admin", json={"content": " Updated "}).status_code, 200)
        self.assertEqual(self.db.row("announcements", announcement_id)["content"], "Updated")
        self.assertEqual(self.call("DELETE", path, "admin").status_code, 200)
        self.assertFalse(any(row["announcement_id"] == announcement_id for row in self.db.tables["announcements"]))

    def test_volunteer_cannot_manage_announcements_or_review_assignments(self):
        """Volunteer receives 403 for every Admin-only action, with no data changes."""
        before = deepcopy(self.db.tables)
        announcement_id = self.db.tables["announcements"][0]["announcement_id"]
        for method, path in (("POST", "/api/announcements"), ("PUT", f"/api/announcements/{announcement_id}"),
                             ("DELETE", f"/api/announcements/{announcement_id}"),
                             ("POST", f"/api/assignments/{self.db.tables['assignments'][0]['id']}/verify")):
            self.assertEqual(self.call(method, path, "alice", json={"title": "bad", "approved": True}).status_code, 403)
        self.assertEqual(self.db.tables, before)

    def test_admin_cannot_use_volunteer_only_task_actions(self):
        """Admin receives 403 for Volunteer-only pick/cancel/upload/submit actions."""
        before = deepcopy(self.db.tables)
        for action in ("pick", "cancel", "photo", "submit"):
            self.assertEqual(self.call("POST", f"/api/tasks/{self.task_ids[0]}/{action}", "admin").status_code, 403)
        self.assertEqual(self.db.tables, before)

    def test_admin_task_crud_module_and_missing_api_routes(self):
        """Module CRUD works and enforces roles; task creation/detail/edit/delete APIs are missing."""
        manager = task.Task()
        admin_id, volunteer_id = self.actors["admin"]["id"], self.actors["alice"]["id"]
        self.assertFalse(manager.create_task(volunteer_id, "Not allowed"))
        self.assertTrue(manager.create_task(admin_id, " [MOCK CIC] Created task ", " Details "))
        row = next(row for row in self.db.tables["tasks"] if row["title"] == "[MOCK CIC] Created task")
        self.assertEqual(manager.task_info(row["id"])["description"], "Details")
        self.assertFalse(manager.edit_task(volunteer_id, row["id"], "bad"))
        self.assertTrue(manager.edit_task(admin_id, row["id"], "[MOCK CIC] Edited task"))
        self.assertFalse(manager.delete_task(volunteer_id, row["id"]))
        self.assertTrue(manager.delete_task(admin_id, row["id"]))
        self.assertIsNone(manager.task_info(row["id"]))
        self.assertIsNotNone(self.db.row("tasks", row["id"])["deleted_at"])
        self.assertEqual(self.call("POST", "/api/tasks", "admin", json={"title": "[MOCK CIC] API"}).status_code, 405)
        for method in ("GET", "PUT", "DELETE"):
            self.assertEqual(self.call(method, f"/api/tasks/{row['id']}", "admin", json={}).status_code, 404)

    def test_history_and_hours_modules_respect_volunteer_scope(self):
        """History/hours modules restrict Volunteer to own records and allow Admin lookup."""
        manager = history.History()
        alice_id, bob_id, admin_id = (self.actors[name]["id"] for name in ("alice", "bob", "admin"))
        self.assertEqual(manager.track_volunteer_hours(alice_id, volunteer_id=bob_id)["total_hours"], 1.5)
        self.assertEqual(manager.track_volunteer_hours(bob_id)["total_hours"], 0)
        self.assertEqual(manager.track_volunteer_hours(admin_id, volunteer_id=alice_id)["total_hours"], 1.5)
        self.assertIsNone(manager.track_volunteer_hours(admin_id))
        self.assertEqual(len(manager.service_history(alice_id, volunteer_id=bob_id)), 1)
        self.assertEqual(manager.service_history(bob_id), [])
        self.assertEqual(len(manager.service_history(admin_id)), 1)
        self.assertEqual(self.call("GET", "/api/history", "alice").status_code, 404)
        self.assertEqual(self.call("GET", "/api/hours", "alice").status_code, 404)

    def test_partial_profile_update_preserves_existing_fields(self):
        """Defect check: editing first_name must preserve email, last_name, and phone."""
        manager = account.Account()
        alice_id = self.actors["alice"]["id"]
        before = deepcopy(self.db.row("profiles", alice_id))
        self.assertTrue(manager.update_profile(alice_id, first_name="Updated"))
        after = self.db.row("profiles", alice_id)
        self.observations.append("After first_name-only update: " + str({key: after[key] for key in ("email", "first_name", "last_name", "phone")}))
        self.assertEqual(after["first_name"], "Updated")
        for key in ("email", "last_name", "phone"):
            self.assertEqual(after[key], before[key], f"Unspecified field {key} was overwritten")

    def test_password_reset_is_mocked_and_logout_route_responds(self):
        """Reset request reaches mock Auth; logout responds for either role without sending email."""
        email = self.actors["alice"]["email"]
        self.assertEqual(self.call("POST", "/api/reset-password", json={"email": email}).status_code, 200)
        self.assertEqual(self.db.reset_requests, [email])
        for actor in ("admin", "alice"):
            self.assertEqual(self.call("POST", "/api/logout", actor).status_code, 200)

    def test_invalid_and_expired_tokens_are_rejected(self):
        """Invalid/expired tokens cannot read tasks or current identity."""
        self.assertEqual(self.call("GET", "/api/tasks", headers={"Authorization": "Bearer invalid"}).status_code, 401)
        self.db.expired_tokens.add(self.db.token(self.actors["alice"]["id"]))
        self.assertEqual(self.call("GET", "/api/tasks", "alice").status_code, 401)
        self.assertEqual(self.call("GET", "/api/me", "alice").status_code, 401)


if __name__ == "__main__":
    unittest.main()
