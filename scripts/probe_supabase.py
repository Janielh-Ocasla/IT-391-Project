"""Read-only Supabase connectivity checks. Never prints keys or user records."""
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import dotenv_values


def main():
    config = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
    url = (config.get("SUPABASE_URL") or "").rstrip("/")
    key = config.get("SUPABASE_PUBLISHABLE_KEY") or ""
    if not url or not key:
        raise SystemExit("Supabase URL or publishable key is missing.")
    print(json.dumps({"host": urlsplit(url).netloc, "publishable_key_present": True}))
    with httpx.Client(base_url=url, headers={"apikey": key}, timeout=15) as client:
        health = client.get("/auth/v1/health")
        print(json.dumps({"check": "auth_health", "status": health.status_code}))
        settings = client.get("/auth/v1/settings")
        summary = {"check": "auth_settings", "status": settings.status_code}
        if settings.status_code == 200:
            data = settings.json()
            summary.update({name: data.get(name) for name in (
                "disable_signup", "mailer_autoconfirm", "phone_autoconfirm",
            )})
            summary["email_provider_enabled"] = data.get("external", {}).get("email")
        print(json.dumps(summary))
        for table, id_column in (
            ("profiles", "id"), ("tasks", "id"),
            ("assignments", "id"), ("announcements", "announcement_id"),
        ):
            response = client.get(f"/rest/v1/{table}", params={"select": id_column, "limit": 0})
            result = {"check": "table_access", "table": table, "status": response.status_code}
            if response.status_code >= 400:
                try:
                    error = response.json()
                    result.update(code=error.get("code"), message=error.get("message"))
                except ValueError:
                    pass
            print(json.dumps(result))


if __name__ == "__main__":
    main()
