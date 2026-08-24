"""S3-compatible object storage for media assets (spec §18).

PostgreSQL stores metadata only; bytes go to object storage.
"""
from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path

import boto3
from botocore.client import Config


class StorageService:
    def __init__(self, endpoint: str, region: str, bucket: str, access_key: str, secret_key: str):
        if not all([bucket]):
            raise ValueError("StorageService requires S3_BUCKET at minimum")
        kwargs = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        }
        if endpoint:
            kwargs["endpoint_url"] = endpoint
        if region and region != "auto":
            kwargs["region_name"] = region
        self.bucket = bucket
        self.client = boto3.client("s3", **kwargs)

    def put_file(self, local_path: str | Path, key: str, *, metadata: dict | None = None) -> dict:
        data = Path(local_path).read_bytes()
        return self.put_bytes(data, key, content_type=self._guess_type(key), metadata=metadata)

    def put_bytes(self, data: bytes, key: str, *, content_type: str = "application/octet-stream",
                  metadata: dict | None = None) -> dict:
        checksum = hashlib.sha256(data).hexdigest()
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": checksum, **(metadata or {})},
        )
        return {
            "storage_key": key,
            "storage_uri": f"s3://{self.bucket}/{key}",
            "checksum": checksum,
            "size_bytes": len(data),
            "mime_type": content_type,
        }

    def get_bytes(self, key: str) -> bytes:
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except self.client.exceptions.ClientError:
            return False

    def presign_get(self, key: str, expires_seconds: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_seconds
        )

    @staticmethod
    def _guess_type(key: str) -> str:
        guessed, _ = mimetypes.guess_type(key)
        return guessed or "application/octet-stream"

    def health(self) -> dict:
        self.client.head_bucket(Bucket=self.bucket)
        return {"ok": True, "bucket": self.bucket}


class NullStorage:
    """Dry-run/test storage: keeps bytes in memory, never touches S3."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_file(self, local_path, key, *, metadata=None):
        return self.put_bytes(Path(local_path).read_bytes(), key)

    def put_bytes(self, data, key, *, content_type="application/octet-stream", metadata=None):
        self.objects[key] = data
        return {
            "storage_key": key,
            "storage_uri": "null://" + key,
            "checksum": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
            "mime_type": content_type,
        }

    def get_bytes(self, key):
        return self.objects[key]

    def exists(self, key):
        return key in self.objects

    def presign_get(self, key, expires_seconds=3600):
        return "null://" + key

    def health(self):
        return {"ok": True, "bucket": "<null-storage>"}
