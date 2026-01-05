import asyncio
from datetime import datetime
from functools import partial

import boto3
from botocore.config import Config

from src.config import settings


class StorageService:
    """Service for uploading files to Cloudflare R2 (S3-compatible)."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                config=Config(signature_version="s3v4"),
            )
        return self._client

    async def _run_sync(self, func, *args, **kwargs):
        """Run synchronous boto3 calls in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def upload_receipt(
        self,
        file_bytes: bytes,
        telegram_id: int,
        file_id: str,
    ) -> str:
        """Upload receipt photo to R2 and return pre-signed URL."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        key = f"receipts/{telegram_id}/{timestamp}_{file_id[:8]}.jpg"

        def _upload():
            client = self._get_client()
            client.put_object(
                Bucket=settings.r2_bucket_name,
                Key=key,
                Body=file_bytes,
                ContentType="image/jpeg",
            )
            # Use public URL if configured, otherwise return key for reference
            if settings.r2_public_url:
                return f"{settings.r2_public_url}/{key}"
            return f"r2://{settings.r2_bucket_name}/{key}"

        return await self._run_sync(_upload)

    async def get_receipt_url(self, key: str) -> str:
        """Generate a fresh pre-signed URL for an existing receipt."""
        def _get_url():
            client = self._get_client()
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.r2_bucket_name, "Key": key},
                ExpiresIn=15768000,
            )
        return await self._run_sync(_get_url)


storage_service = StorageService()
