"""Create the demo student account used for local testing and the Week 16 demo.

Run: .venv/bin/python -m scripts.seed_demo
Test-only credentials (local development database only):
  email:    demo.student@example.com
  password: DemoStudent123
"""
from datetime import datetime, timezone

from app.core.security import hash_password
from app.db.mongo import get_sync_db

DEMO_EMAIL = "demo.student@example.com"
DEMO_PASSWORD = "DemoStudent123"


def main() -> None:
    db = get_sync_db()
    now = datetime.now(timezone.utc)
    db.users.update_one(
        {"email": DEMO_EMAIL},
        {
            "$set": {"password_hash": hash_password(DEMO_PASSWORD), "status": "active", "updated_at": now},
            "$setOnInsert": {"name": "Demo Student", "role": "student", "storage_used_bytes": 0,
                             "token_version": 0, "created_at": now},
        },
        upsert=True,
    )
    print(f"Demo student ready: {DEMO_EMAIL}")


if __name__ == "__main__":
    main()
