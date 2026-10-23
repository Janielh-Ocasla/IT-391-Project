"""Stateful Supabase substitute used only by offline tests.

Runs the real CIC managers against shared in-memory rows. This models the
operations used by this repository, not the project's actual RLS policies.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from types import SimpleNamespace
from uuid import uuid4


def now():
    return datetime.now(timezone.utc).isoformat()


class MockDatabase:
    def __init__(self):
        self.fixture = json.loads((Path(__file__).parents[1] / "fixtures/role_scenarios.json").read_text())
        self.accounts = {
            account["id"]: dict(account, confirmed=True)
            for account in self.fixture["accounts"]
        }
        self.tables = {"profiles": []}
        for name in ("tasks", "assignments", "announcements"):
            self.tables[name] = [self.defaults(name, row) for row in self.fixture[name]]
        self.tables["profiles"] = [
            {key: value for key, value in account.items() if key != "password"}
            for account in self.fixture["accounts"]
        ]
        self.objects = {}
        self.expired_tokens = set()
        self.reset_requests = []
        self.email_autoconfirm = True
        self.fail_profile_insert = False

    def defaults(self, name, row):
        values = {"created_at": now(), "updated_at": None}
        if name == "tasks":
            values.update(description=None, status="open", estimated_hours=0, deleted_at=None, deleted_by=None)
        if name == "assignments":
            values.update(status="assigned", photo_path=None, assigned_at=now(), submitted_at=None,
                          cancelled_at=None, reviewed_at=None, reviewed_by=None)
        if name in {"tasks", "announcements"}:
            values["created_by"] = self.fixture["accounts"][0]["id"]
        values["announcement_id" if name == "announcements" else "id"] = str(uuid4())
        return {**values, **deepcopy(row)}

    def client(self, *_args, **_kwargs):
        return MockClient(self)

    def token(self, user_id):
        return f"mock-token-{user_id}"

    def user_for_token(self, token):
        for user_id, account in self.accounts.items():
            if token == self.token(user_id) and token not in self.expired_tokens and account["confirmed"]:
                return account
        raise ValueError("Invalid or expired mock token")

    def row(self, table, row_id):
        key = "announcement_id" if table == "announcements" else "id"
        return next(row for row in self.tables[table] if row[key] == row_id)


class MockClient:
    def __init__(self, database):
        self.database = database
        self.options = SimpleNamespace(headers={})
        self.user_id = None
        self.postgrest = SimpleNamespace(auth=self.set_auth)
        self.auth = MockAuth(self)
        self.storage = SimpleNamespace(from_=lambda bucket: MockBucket(self, bucket))

    def set_auth(self, token):
        self.user_id = self.database.user_for_token(token)["id"]

    def table(self, name):
        if name not in self.database.tables:
            raise ValueError(f"Unknown mock table: {name}")
        return MockQuery(self.database, name)


class MockAuth:
    def __init__(self, client):
        self.client = client
        self.database = client.database

    def get_user(self, token):
        account = self.database.user_for_token(token)
        return SimpleNamespace(user=SimpleNamespace(id=account["id"]))

    def sign_in_with_password(self, data):
        account = next((a for a in self.database.accounts.values() if a["email"] == data["email"]), None)
        if not account or account["password"] != data["password"] or not account["confirmed"]:
            raise ValueError("Invalid mock credentials or unconfirmed email")
        self.client.user_id = account["id"]
        token = self.database.token(account["id"])
        self.client.options.headers["Authorization"] = f"Bearer {token}"
        user = SimpleNamespace(id=account["id"])
        return SimpleNamespace(user=user, session=SimpleNamespace(access_token=token, user=user))

    def sign_up(self, data):
        if any(account["email"] == data["email"] for account in self.database.accounts.values()):
            raise ValueError("Mock email already registered")
        user_id = str(uuid4())
        self.database.accounts[user_id] = dict(data, id=user_id, confirmed=self.database.email_autoconfirm)
        user = SimpleNamespace(id=user_id)
        session = None
        if self.database.email_autoconfirm:
            self.client.user_id = user_id
            session = SimpleNamespace(access_token=self.database.token(user_id), user=user)
        return SimpleNamespace(user=user, session=session)

    def reset_password_for_email(self, email):
        self.database.reset_requests.append(email)
        return SimpleNamespace()

    def sign_out(self):
        self.client.user_id = None

    def update_user(self, values):
        if self.client.user_id is None:
            raise ValueError("Mock login required")
        self.database.accounts[self.client.user_id].update(values)


class MockBucket:
    def __init__(self, client, bucket):
        self.client = client
        self.bucket = bucket

    def upload(self, path, file, file_options):
        header = self.client.options.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise ValueError("Storage did not receive the user's bearer token")
        user = self.client.database.user_for_token(header[7:])
        if not path.startswith(user["id"] + "/"):
            raise ValueError("Storage path does not belong to this mock user")
        if self.bucket != "task-photo":
            raise ValueError("Unexpected mock bucket")
        self.client.database.objects[(self.bucket, path)] = {
            "bytes": file.read() if hasattr(file, "read") else file,
            "content_type": file_options["content-type"],
        }
        return SimpleNamespace(path=path)


class MockQuery:
    def __init__(self, database, table):
        self.database = database
        self.name = table
        self.filters = []
        self.action = "select"
        self.columns = "*"
        self.one = False
        self.max_rows = None
        self.sort = None

    def select(self, columns):
        self.columns = columns
        return self

    def eq(self, column, value):
        self.filters.append(lambda row: row.get(column) == value)
        return self

    def is_(self, column, value):
        if value != "null":
            raise ValueError("Only is null is implemented by this mock")
        self.filters.append(lambda row: row.get(column) is None)
        return self

    def in_(self, column, values):
        self.filters.append(lambda row: row.get(column) in values)
        return self

    def order(self, column, desc=False):
        self.sort = (column, desc)
        return self

    def limit(self, count):
        self.max_rows = count
        return self

    def single(self):
        self.one = True
        return self

    def insert(self, values):
        self.action, self.values = "insert", values
        return self

    def update(self, values):
        self.action, self.values = "update", values
        return self

    def delete(self):
        self.action = "delete"
        return self

    def project(self, row):
        fields = [field.strip() for field in re.split(r",(?![^()]*\))", self.columns)]
        result = deepcopy(row) if "*" in fields else {}
        for field in fields:
            if field.startswith("tasks("):
                task = self.database.row("tasks", row["task_id"])
                result["tasks"] = {key.strip(): deepcopy(task.get(key.strip())) for key in field[6:-1].split(",")}
            elif field != "*":
                result[field] = deepcopy(row.get(field))
        return result

    def execute(self):
        table = self.database.tables[self.name]
        rows = [row for row in table if all(check(row) for check in self.filters)]
        if self.action == "insert":
            if self.name == "profiles" and self.database.fail_profile_insert:
                raise PermissionError("Simulated profile insert failure")
            values = self.values if isinstance(self.values, list) else [self.values]
            rows = [self.database.defaults(self.name, value) for value in values]
            key = "announcement_id" if self.name == "announcements" else "id"
            if any(any(existing[key] == row[key] for existing in table) for row in rows):
                raise ValueError("Duplicate mock primary key")
            table.extend(rows)
        elif self.action == "update":
            for row in rows:
                row.update(deepcopy(self.values))
        elif self.action == "delete":
            for row in rows:
                table.remove(row)
        if self.sort:
            column, desc = self.sort
            rows = sorted(rows, key=lambda row: row.get(column) or "", reverse=desc)
        if self.max_rows is not None:
            rows = rows[:self.max_rows]
        result = [self.project(row) for row in rows]
        if self.one:
            if len(result) != 1:
                raise LookupError(f"Expected one mock row, received {len(result)}")
            return SimpleNamespace(data=result[0])
        return SimpleNamespace(data=result)
