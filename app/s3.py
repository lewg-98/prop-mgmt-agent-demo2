from typing import Optional, BinaryIO, List, Dict, Any
import boto3
import logging
import mimetypes
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
from botocore.config import Config
from .config import Settings, get_settings

# Configure logger
logger = logging.getLogger(__name__)

class S3Error(Exception):
    """Custom exception for S3 operations"""
    pass

class S3Handler:
    """
    Handles AWS S3 file operations for maintenance request attachments.
    Includes optimizations for demo environment and proper error handling.
    """
    
    # Allowed content types for maintenance photos
    ALLOWED_CONTENT_TYPES = [
        'image/jpeg',
        'image/png',
        'image/heic',
        'application/pdf'
    ]
    
    # Maximum file sizes (in bytes)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    def __init__(self, settings: Settings = get_settings()):
        """
        Initialize S3 handler with configuration settings.
        
        Args:
            settings: Application configuration settings
        """
        self.settings = settings
        self.bucket = settings.s3_bucket
        self._client = None
        self._resource = None
        
        # Initialize mime types
        mimetypes.init()
        logger.info("S3 handler initialized")

    @property
    def client(self):
        """
        Lazy initialization of S3 client with retry configuration.
        Uses connection pooling for better performance.
        """
        if not self._client:
            config = Config(
                retries=dict(
                    max_attempts=3,
                    mode='adaptive'
                ),
                max_pool_connections=10,
                connect_timeout=5,
                read_timeout=10
            )
            
            try:
                self._client = boto3.client(
                    's3',
                    aws_access_key_id=self.settings.aws_access_key.get_secret_value(),
                    aws_secret_access_key=self.settings.aws_secret_key.get_secret_value(),
                    region_name=self.settings.aws_region,
                    config=config
                )
                logger.debug("S3 client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {str(e)}")
                raise S3Error("S3 client initialization failed") from e
                
        return self._client

    @property
    def resource(self):
        """Lazy initialization of S3 resource for object operations"""
        if not self._resource:
            try:
                self._resource = boto3.resource(
                    's3',
                    aws_access_key_id=self.settings.aws_access_key.get_secret_value(),
                    aws_secret_access_key=self.settings.aws_secret_key.get_secret_value(),
                    region_name=self.settings.aws_region
                )
                logger.debug("S3 resource initialized")
            except Exception as e:
                logger.error(f"Failed to initialize S3 resource: {str(e)}")
                raise S3Error("S3 resource initialization failed") from e
                
        return self._resource

    def _get_content_type(self, filename: str) -> str:
        """
        Determine and validate content type from filename.
        
        Args:
            filename: Name of the file
            
        Returns:
            String containing the content type
            
        Raises:
            S3Error if content type is not allowed
        """
        content_type, _ = mimetypes.guess_type(filename)
        if content_type not in self.ALLOWED_CONTENT_TYPES:
            raise S3Error(f"Content type {content_type} not allowed")
        return content_type

    def _generate_file_hash(self, file_data: BinaryIO) -> str:
        """
        Generate SHA-256 hash for file deduplication.
        Resets file pointer to start after hashing.
        """
        try:
            sha256_hash = hashlib.sha256()
            for byte_block in iter(lambda: file_data.read(4096), b""):
                sha256_hash.update(byte_block)
            file_data.seek(0)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Failed to generate file hash: {str(e)}")
            raise S3Error("File hash generation failed") from e

    async def upload_file(
        self,
        file_data: BinaryIO,
        destination: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Upload file to S3 with optimizations and validation.
        
        Args:
            file_data: File-like object containing the data
            destination: Destination path in S3
            content_type: Optional content type override
            metadata: Optional metadata dictionary
            
        Returns:
            Dictionary containing upload details
            
        Example:
            >>> with open('photo.jpg', 'rb') as f:
            ...     result = await s3.upload_file(
            ...         f, 
            ...         'maintenance/photo.jpg',
            ...         metadata={'request_id': '123'}
            ...     )
        """
        try:
            # Validate file size
            file_data.seek(0, 2)
            size = file_data.tell()
            file_data.seek(0)
            
            if size > self.MAX_FILE_SIZE:
                raise S3Error(f"File size exceeds maximum of {self.MAX_FILE_SIZE/1024/1024}MB")
            
            # Generate unique file hash
            file_hash = self._generate_file_hash(file_data)
            
            # Validate and get content type
            actual_content_type = content_type or self._get_content_type(destination)
            
            # Construct key with hash for deduplication
            key = f"{Path(destination).stem}_{file_hash[:8]}{Path(destination).suffix}"
            
            # Prepare upload settings
            upload_args = {
                'ContentType': actual_content_type,
                'ACL': 'private',
                'CacheControl': 'max-age=86400',  # 24 hour cache
                'Metadata': metadata or {}
            }
            
            # Upload file
            self.client.upload_fileobj(
                file_data,
                self.bucket,
                key,
                ExtraArgs=upload_args
            )
            
            logger.info(f"Successfully uploaded file to {key}")
            
            return {
                "key": key,
                "size": size,
                "content_type": actual_content_type,
                "hash": file_hash,
                "url": await self.generate_presigned_url(key)
            }
            
        except S3Error:
            raise
        except Exception as e:
            logger.error(f"Failed to upload file: {str(e)}")
            raise S3Error("File upload failed") from e

    async def download_file(self, key: str) -> BinaryIO:
        """Download file from S3 with validation"""
        try:
            obj = self.resource.Object(self.bucket, key)
            response = obj.get()
            
            # Validate content type
            content_type = response['ContentType']
            if content_type not in self.ALLOWED_CONTENT_TYPES:
                raise S3Error(f"Invalid content type: {content_type}")
                
            return response['Body']
            
        except ClientError as e:
            logger.error(f"Failed to download file {key}: {str(e)}")
            raise S3Error("File download failed") from e

    async def generate_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        method: str = 'get_object'
    ) -> str:
        """Generate temporary access URL for S3 object"""
        try:
            url = self.client.generate_presigned_url(
                ClientMethod=method,
                Params={
                    'Bucket': self.bucket,
                    'Key': key
                },
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate URL for {key}: {str(e)}")
            raise S3Error("URL generation failed") from e

    async def delete_file(self, key: str) -> None:
        """Safely delete file from S3"""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            logger.info(f"Successfully deleted file {key}")
        except Exception as e:
            logger.error(f"Failed to delete file {key}: {str(e)}")
            raise S3Error("File deletion failed") from e

    async def list_files(self, prefix: str = "", max_items: int = 1000) -> List[Dict[str, Any]]:
        """
        List files in S3 bucket with prefix and pagination.
        
        Args:
            prefix: Optional prefix to filter files
            max_items: Maximum number of items to return
            
        Returns:
            List of file details
        """
        try:
            paginator = self.client.get_paginator('list_objects_v2')
            files = []
            
            async for page in paginator.paginate(
                Bucket=self.bucket,
                Prefix=prefix,
                PaginationConfig={'MaxItems': max_items}
            ):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        files.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat(),
                            'url': await self.generate_presigned_url(obj['Key'])
                        })
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
            raise S3Error("File listing failed") from e