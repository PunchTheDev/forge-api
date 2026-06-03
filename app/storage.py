"""Optional S3-compatible STEP file storage.

When S3_BUCKET is set, STEP files are uploaded to S3 and retrieved via
presigned URLs. When unset, the caller falls back to SQLite BLOB storage.

Required env vars when S3 is configured:
  S3_BUCKET               — bucket name
  AWS_ACCESS_KEY_ID       — access key (also works for R2 / MinIO)
  AWS_SECRET_ACCESS_KEY   — secret key

Optional env vars:
  S3_ENDPOINT_URL         — custom endpoint for R2 / MinIO (omit for AWS)
  AWS_REGION              — defaults to "auto" (R2) or "us-east-1" (AWS)

Object keys follow the pattern: steps/<submission_id>.step
"""

import asyncio
import os

import boto3
from botocore.config import Config

_PRESIGN_TTL = 3600  # 1 hour — balances cache-ability against secret leakage


def is_configured() -> bool:
    return bool(os.environ.get("S3_BUCKET"))


def _client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT_URL"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )


def _object_key(submission_id: str) -> str:
    return f"steps/{submission_id}.step"


async def upload(submission_id: str, data: bytes) -> str:
    """Upload STEP bytes to S3. Returns the object key (not a URL)."""
    key = _object_key(submission_id)

    def _put():
        client = _client()
        client.put_object(
            Bucket=os.environ["S3_BUCKET"],
            Key=key,
            Body=data,
            ContentType="application/octet-stream",
        )

    await asyncio.to_thread(_put)
    return key


async def presign(key: str) -> str:
    """Return a presigned GET URL for an existing S3 object key."""

    def _sign():
        client = _client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": os.environ["S3_BUCKET"], "Key": key},
            ExpiresIn=_PRESIGN_TTL,
        )

    return await asyncio.to_thread(_sign)
