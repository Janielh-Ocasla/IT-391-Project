"""Run offline role workflows and save inspectable evidence to docs/."""
import json
from pathlib import Path
import unittest

from tests.test_role_workflows import RoleWorkflowTests


class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.evidence = []

    def record(self, test, status, details=None):
        self.evidence.append({
            "test": test.id().rsplit(".", 1)[-1],
            "description": test.shortDescription(),
            "status": status,
            "observations": list(getattr(test, "observations", [])),
            **({"failure": details} if details else {}),
        })

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, "PASS")

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.record(test, "FAIL", self._exc_info_to_string(error, test))

    def addError(self, test, error):
        super().addError(test, error)
        self.record(test, "ERROR", self._exc_info_to_string(error, test))


def main():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RoleWorkflowTests)
    result = unittest.TextTestRunner(verbosity=1, resultclass=EvidenceResult).run(suite)
    docs = Path(__file__).resolve().parents[1] / "docs"
    evidence = {
        "mode": "offline_stateful_mock",
        "network_allowed": False,
        "real_database_writes": 0,
        "fixture": "tests/fixtures/role_scenarios.json",
        "tests_run": result.testsRun,
        "passed": len([row for row in result.evidence if row["status"] == "PASS"]),
        "failed": len(result.failures),
        "errors": len(result.errors),
        "tests": result.evidence,
    }
    (docs / "mock_verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
    report = f'''# Volunteer / Admin mock verification

This report runs the real Flask routes and the real Account, Task, Assignment,
Announcement, and History classes against a shared in-memory Supabase substitute.
All network connections are blocked during the tests. **No real database rows,
Auth accounts, emails, or Storage objects were created.**

Fixture: [role_scenarios.json](../tests/fixtures/role_scenarios.json): one seeded
Admin, two seeded Volunteers, five tasks (open, assigned, completed, and deleted),
two assignments, and one announcement. All addresses and credentials are fictional.
Every test gets a fresh copy of the fixture.

## Result

{evidence['passed']} / {result.testsRun} scenario checks passed;
{evidence['failed']} failed; {evidence['errors']} errors.

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
'''
    for row in result.evidence:
        report += f"| {row['description']} | {row['status']} |\n"
    (docs / "MOCK_VERIFICATION.md").write_text(report)
    print(f"Evidence written to {docs / 'MOCK_VERIFICATION.md'}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
