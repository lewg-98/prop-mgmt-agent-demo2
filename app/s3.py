import boto3
import aioboto3
from botocore.exceptions import ClientError
import logging
from typing import Optional
import asyncio

logger = logging.getLogger(__name__)

class S3Handler:
    def __init__(self, aws_config: dict):
        self.config = aws_config
        self.upload_semaphore = asyncio.Semaphore(5)
        self._init_client()
    
    def _init_client(self):
        self.s3 = boto3.client('s3', **self.config)
        self.async_session = aioboto3.Session()
    
    async def upload_photo(self, photo: bytes, filename: str) -> Optional[str]:
        async with self.upload_semaphore:
            try:
                return await self._upload_with_retry(photo, filename)
            except Exception as e:
                logger.error(f"Failed to upload photo: {e}")
                return None
    
    async def _upload_with_retry(self, photo: bytes, filename: str, max_retries=3):
        for attempt in range(max_retries):
            try:
                async with self.async_session.client('s3', **self.config) as s3:
                    await s3.put_object(
                        Bucket=self.config['bucket'],
                        Key=f"maintenance_photos/{filename}",
                        Body=photo,
                        ContentType='image/jpeg'
                    )
                    return f"s3://{self.config['bucket']}/maintenance_photos/{filename}"
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)