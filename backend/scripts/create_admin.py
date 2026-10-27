"""Create (or promote) an admin account.

Run: .venv/bin/python -m scripts.create_admin --email admin@example.com --name "Admin"
The password is asked for interactively so it never appears in shell history.
"""
import argparse
import getpass
from datetime import datetime, timezone

from app.core.security import hash_password
from app.db.mongo import get_sync_db


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Admin")
    args = parser.parse_args()

    password = getpass.getpass("Admin password: ")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters")

    db = get_sync_db()
    now = datetime.now(timezone.utc)
    db.users.update_one(
        {"email": args.email.lower()},
        {
            "$set": {"role": "admin", "status": "active", "password_hash": hash_password(password), "updated_at": now},
            "$setOnInsert": {"name": args.name, "storage_used_bytes": 0, "token_version": 0, "created_at": now},
        },
        upsert=True,
    )
    print(f"Admin ready: {args.email.lower()}")


if __name__ == "__main__":
    main()
