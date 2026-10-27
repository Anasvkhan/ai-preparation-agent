"""Create MongoDB indexes. Run once: python -m app.db.indexes"""
from pymongo import ASCENDING, DESCENDING

from app.db.mongo import get_sync_db

INDEXES = {
    "users": [([("email", ASCENDING)], {"unique": True})],
    "projects": [([("user_id", ASCENDING), ("name", ASCENDING)], {})],
    "artifacts": [([("user_id", ASCENDING), ("project_id", ASCENDING), ("is_active", ASCENDING)], {})],
    "chunks": [([("artifact_id", ASCENDING), ("artifact_version", ASCENDING)], {})],
    "jobs": [
        ([("status", ASCENDING), ("created_at", ASCENDING)], {}),
        ([("heartbeat_at", ASCENDING)], {}),
    ],
    "sessions": [([("user_id", ASCENDING), ("project_id", ASCENDING), ("created_at", DESCENDING)], {})],
    "questions": [([("session_id", ASCENDING), ("order", ASCENDING)], {})],
    "usage_logs": [([("created_at", DESCENDING)], {}), ([("model", ASCENDING), ("created_at", DESCENDING)], {})],
    "audit_logs": [([("created_at", DESCENDING)], {})],
}


def main() -> None:
    db = get_sync_db()
    for collection, specs in INDEXES.items():
        for keys, opts in specs:
            name = db[collection].create_index(keys, **opts)
            print(f"{collection}: {name}")


if __name__ == "__main__":
    main()
