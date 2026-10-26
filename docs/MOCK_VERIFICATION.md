# Volunteer / Admin mock verification

This report runs the real Flask routes and the real Account, Task, Assignment,
Announcement, and History classes against a shared in-memory Supabase substitute.
All network connections are blocked during the tests. **No real database rows,
Auth accounts, emails, or Storage objects were created.**

Fixture: [role_scenarios.json](../tests/fixtures/role_scenarios.json): one seeded
Admin, two seeded Volunteers, five tasks (open, assigned, completed, and deleted),
two assignments, and one announcement. All addresses and credentials are fictional.
Every test gets a fresh copy of the fixture.

## Result

23 / 23 scenario checks passed;
0 failed; 0 errors.

**Passing the checks below does not mean registration is enabled.** Some checks
verify and document a blocked or missing feature, as identified in this table.

| Feature | Volunteer | Admin | Level of verification |
| --- | --- | --- | --- |
| Public registration | BLOCKED: `/api/register` and `/api/signup` return 503 | BLOCKED: same 503; no separate Admin signup route | Actual Flask routes with mock data |
| Account creation method | Creates a Volunteer when Auth and profile writes succeed | Method always assigns `volunteer`; Admin is pre-seeded for other tests | Business module only; not public registration |
| Login and current identity | PASS for both seeded Volunteers | PASS for seeded Admin | Real routes and Account code, mock Auth |
| Task visibility | Only open, undeleted tasks | All undeleted tasks | Real route and Task queries |
| Pick / cancel | PASS, including reopening for another Volunteer | 403 for Volunteer-only routes | Real route and row mutations |
| Photo / submit | PASS; photo required before submit; mock Storage receives PNG and user token | 403 for Volunteer-only routes | Mock object bytes and assignment state checked |
| Delivery review | Cannot review: 403 | Approve, reject, resubmit, approve: PASS | Assignment and task states checked |
| Assignment scope | Can see own rows; cannot mutate another Volunteer's work | Can see everyone's assignments | Filters checked without simulated RLS hiding mistakes |
| Announcements | Can read; create/edit/delete return 403 | Create, edit, delete: PASS | Real routes and announcement rows |
| Task CRUD | Denied by business module | Module works; create/detail/edit/delete API routes are NOT EXPOSED (405/404) | Module and route availability checked separately |
| History / volunteer hours | Module scopes records to self | Module supports Admin lookup | Module only; `/api/history` and `/api/hours` return 404 |
| Profile edit | Partial update preserves omitted fields after fix | Same Account method | Module only; no profile-edit API is exposed |
| Password reset / logout | Mock reset call and logout route work | Logout route works | No real email, token revocation, or recovery page tested |

## Defects reproduced and fixed

1. `Account.update_profile(first_name=...)` previously included `None` for omitted
   email, last name, and phone. It now writes only supplied fields. The regression
   test verifies that existing profile values survive a first-name-only edit.
2. A Volunteer uploading to a task without their own active assignment previously
   received HTTP 500. The photo route now checks the active assignment and returns
   HTTP 409 before touching Storage. The regression test also checks that no image
   or assignment data is changed.

## Registration gap that remains

The public API deliberately remains paused. The mock also reproduces a separate
failure case in the existing Account method: Auth signup succeeds, profile insert
fails, and an Auth record remains without a profile. No rollback is implemented.
This is a simulated profile write failure, **not proof of the live project's RLS
or trigger configuration**. Admin enrollment and Auth/Profile synchronization
still need an explicit implementation before enabling registration.

## Limits

The mock models the repository's database calls and shared state, not Supabase's
actual RLS policies, mail delivery, email confirmation links, database constraints,
Storage bucket settings, concurrency, or browser dashboards. Seeded Admin/Volunteer
accounts do not establish that either role can publicly register. Live Auth/Storage
flows still need separate verification using confirmed test accounts.

## Reproduce

```sh
python -m scripts.verify_mock_roles
python -m unittest discover -s tests -v
node --test tests/api-client.test.cjs
```

Machine-readable observations: [mock_verification.json](mock_verification.json).

## Per-scenario evidence

| Scenario | Result |
| --- | --- |
| Module only: volunteer creation, profile normalization, and later API login work. | PASS |
| Admin can create/edit/delete announcements; Volunteer can read the changes. | PASS |
| Admin receives 403 for Volunteer-only pick/cancel/upload/submit actions. | PASS |
| Admin rejection returns assignment to assigned; Volunteer can resubmit and be approved. | PASS |
| Module CRUD works and enforces roles; task creation/detail/edit/delete APIs are missing. | PASS |
| Duplicate picking and picking deleted tasks do not create assignments. | PASS |
| Volunteer sees own assignments; Admin sees both volunteers' assignments. | PASS |
| Seeded Admin and Volunteer can log in and retrieve their own identity. | PASS |
| Cancellation preserves the old assignment and lets another volunteer pick the reopened task. | PASS |
| Duplicate email registration through the account module is rejected. | PASS |
| History/hours modules restrict Volunteer to own records and allow Admin lookup. | PASS |
| Invalid/expired tokens cannot read tasks or current identity. | PASS |
| Volunteer cannot cancel or submit another volunteer's assignment. | PASS |
| Defect check: editing first_name must preserve email, last_name, and phone. | PASS |
| Reset request reaches mock Auth; logout responds for either role without sending email. | PASS |
| Registration risk: failed profile insert leaves an Auth account without a profile. | PASS |
| No Admin signup exists; Account.create_account always assigns volunteer. | PASS |
| Registration status: both roles and both aliases return 503; no rows are created. | PASS |
| Volunteer sees open tasks; Admin sees all undeleted tasks. | PASS |
| Unconfirmed email, unknown email, and bad password cannot log in. | PASS |
| Defect check: uploading to another volunteer's task must return 403/409, not 500. | PASS |
| Volunteer receives 403 for every Admin-only action, with no data changes. | PASS |
| Complete workflow: pick, upload, submit, Admin approval, completed task and hours. | PASS |
