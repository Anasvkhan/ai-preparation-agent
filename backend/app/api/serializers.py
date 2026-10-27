from app.core.config import get_settings


def user_out(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "storage_used_bytes": user.get("storage_used_bytes", 0),
        "quota_bytes": get_settings().quota_bytes,
        "created_at": user["created_at"],
    }


def project_out(project: dict) -> dict:
    return {
        "id": str(project["_id"]),
        "name": project["name"],
        "status": project.get("status", "active"),
        "created_at": project["created_at"],
        "updated_at": project["updated_at"],
    }
