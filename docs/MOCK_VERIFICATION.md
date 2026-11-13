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

30 / 30 scenario checks passed;
0 failed; 0 errors.

Passing the checks below verifies the application against the mock; it does not
verify the configuration of a live Supabase project.

| Feature | Volunteer | Admin | Level of verification |
| --- | --- | --- | --- |
| Public registration | Both signup routes create a volunteer profile through the mocked Auth trigger | No separate Admin signup; public signup cannot grant Admin access | Actual Flask routes with mock data |
| Login and current identity | PASS for both seeded Volunteers | PASS for seeded Admin | Real routes and Account code, mock Auth |
| Task visibility | Only open, undeleted tasks | All undeleted tasks | Real route and Task queries |
| Pick / cancel | PASS, including reopening for another Volunteer | 403 for Volunteer-only routes | Real route and row mutations |
| Photo / submit | PASS; photo required before submit; mock Storage receives PNG and user token | 403 for Volunteer-only routes | Mock object bytes and assignment state checked |
| Delivery review | Cannot review: 403 | Approve, reject, resubmit, approve: PASS | Assignment and task states checked |
| Assignment scope | Can see own rows; cannot mutate another Volunteer's work | Can see everyone's assignments | Filters checked without simulated RLS hiding mistakes |
| Announcements | Can read; create/edit/delete return 403 | Create, edit, delete: PASS | Real routes and announcement rows |
| Task management | Can read open tasks; create/edit/delete return 403 | Can create, read, edit, and soft-delete tasks | Real routes and task rows |
| History / estimated hours | Own records only | Can look up volunteers; history also supports an unfiltered lookup | Real routes and assignment rows |
| Profile edit | Own name and phone; omitted fields are preserved | Same own-profile endpoint | Real route and profile rows |
| Password reset / logout | Mock reset call and logout route work | Logout route works | No real email, token revocation, or recovery page tested |

## Defects reproduced and fixed

1. `Account.update_profile(first_name=...)` previously included `None` for omitted
   email, last name, and phone. It now writes only supplied fields. The regression
   test verifies that existing profile values survive a first-name-only edit.
2. A Volunteer uploading to a task without their own active assignment previously
   received HTTP 500. The photo route now checks the active assignment and returns
   HTTP 409 before touching Storage. The regression test also checks that no image
   or assignment data is changed.

## Registration and profiles

The signup routes rely on the configured Supabase Auth trigger to create
volunteer profiles. The mock tests exercise email confirmation, duplicate
registration, and rollback when profile creation fails. Updating a profile's
name or phone does not modify the account's login email or role.

## Limits

The mock models the repository's database calls and shared state, not Supabase's
actual RLS policies, mail delivery, email confirmation links, database constraints,
Storage bucket settings, concurrency, or browser dashboards. Live Auth/Storage
flows still need separate verification using confirmed test accounts.

## Reproduce

```sh
python -m scripts.verify_mock_roles
python -m unittest discover -s tests -v
node --test tests/*.test.cjs
```

Machine-readable observations: [mock_verification.json](mock_verification.json).

## Per-scenario evidence

| Scenario | Result |
| --- | --- |
| Account sends normalized signup metadata; the trigger creates the profile. | PASS |
| Admin can create/edit/delete announcements; Volunteer can read the changes. | PASS |
| Admin receives 403 for Volunteer-only pick/cancel/upload/submit actions. | PASS |
| Admin rejection returns assignment to assigned; Volunteer can resubmit and be approved. | PASS |
| Admin can publish, view, edit, and soft-delete a task through the API. | PASS |
| Duplicate picking and picking deleted tasks do not create assignments. | PASS |
| Volunteer sees own assignments; Admin sees both volunteers' assignments. | PASS |
| Even direct mock Auth signup metadata cannot assign an Admin profile role. | PASS |
| Seeded Admin and Volunteer can log in and retrieve their own identity. | PASS |
| Cancellation preserves the old assignment and lets another volunteer pick the reopened task. | PASS |
| Duplicate email registration through the account module is rejected. | PASS |
| Case/whitespace variants of an existing email fail without changing its data. | PASS |
| Volunteers see only their own records; Admin can look up any volunteer. | PASS |
| Invalid/expired tokens cannot read tasks or current identity. | PASS |
| A trigger error after the profile write also restores the complete transaction. | PASS |
| Volunteer cannot cancel or submit another volunteer's assignment. | PASS |
| Profile editing changes only supplied fields on the authenticated user's own profile. | PASS |
| Reset request reaches mock Auth; logout responds for either role without sending email. | PASS |
| Profile edits reject account IDs, roles, login email, and empty names. | PASS |
| Failed profile creation rolls back signup; retry creates one Auth/profile pair. | PASS |
| Caller-supplied Admin roles on either alias create volunteers without Admin access. | PASS |
| Both aliases create Auth/profile rows; confirmation enables login and identity lookup. | PASS |
| Both aliases report trigger failures without leaving orphaned Auth/profile rows. | PASS |
| Only valid title and description updates reach the task manager. | PASS |
| Task details follow list visibility; Volunteer task management requests cannot change rows. | PASS |
| Volunteer sees open tasks; Admin sees all undeleted tasks. | PASS |
| Unconfirmed email, unknown email, and bad password cannot log in. | PASS |
| Defect check: uploading to another volunteer's task must return 403/409, not 500. | PASS |
| Volunteer receives 403 for every Admin-only action, with no data changes. | PASS |
| Complete workflow: pick, upload, submit, Admin approval, completed task and hours. | PASS |
