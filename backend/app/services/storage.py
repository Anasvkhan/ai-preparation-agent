"""Private object storage over the S3 protocol (Supabase Storage, AWS S3 or MinIO)."""
import boto3
from botocore.config import Config

from app.core.config import get_settings


def _client():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.storage_endpoint or None,
        region_name=s.storage_region,
        aws_access_key_id=s.storage_access_key,
        aws_secret_access_key=s.storage_secret_key,
        config=Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
    )


def artifact_key(user_id: str, project_id: str, artifact_id: str, version: int, filename: str) -> str:
    return f"users/{user_id}/projects/{project_id}/artifacts/{artifact_id}/v{version}/{filename}"


def put_object(key: str, data: bytes, content_type: str) -> None:
    _client().put_object(Bucket=get_settings().storage_bucket, Key=key, Body=data, ContentType=content_type)


def get_object(key: str) -> bytes:
    return _client().get_object(Bucket=get_settings().storage_bucket, Key=key)["Body"].read()


def delete_object(key: str) -> None:
    _client().delete_object(Bucket=get_settings().storage_bucket, Key=key)


def presigned_download_url(key: str, expires_seconds: int = 300) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": get_settings().storage_bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )


def check_bucket() -> bool:
    _client().head_bucket(Bucket=get_settings().storage_bucket)
    return True
