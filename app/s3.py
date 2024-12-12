from typing import Optional, BinaryIO, List, Dict, Any
import boto3 # type: ignore
from utils.logger import setup_logger
from botocore.config import Config # type: ignore
from datetime import datetime
from pathlib import Path
from .config import Settings, get_settings

logger = setup_logger("app.s3", log_file="logs/s3.log")

class S3Error(Exception):
    """Custom exception for S3 operations with demo-friendly messages"""
    pass

class S3Handler:
    """
    Simplified S3 handler for MVP demo.
    Focuses on maintenance photo uploads and basic file management.
    """
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    def __init__(self, settings: Settings = get_settings()):
        """Initialize S3 handler with settings"""
        self.settings = settings
        self.bucket = settings.S3_BUCKET
        self._client = None
        logger.info("S3 handler initialized")

    @property
    def client(self):
        """Lazy initialization of S3 client with basic retry config"""
        if not self._client:
            try:
                config = Config(
                    retries=dict(max_attempts=3),
                    connect_timeout=10,  # Increased for demo reliability
                    read_timeout=10
                )
                
                self._client = boto3.client(
                    's3',
                    aws_access_key_id=self.settings.AWS_ACCESS_KEY.get_secret_value(),
                    aws_secret_access_key=self.settings.AWS_SECRET_KEY.get_secret_value(),
                    region_name=self.settings.AWS_REGION,
                    config=config
                )
                logger.debug("S3 client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {str(e)}")
                raise S3Error("Unable to connect to storage service") from e
                
        return self._client

    async def upload_maintenance_photo(
        self,
        file_data: BinaryIO,
        property_id: str,
        request_id: str
    ) -> Dict[str, Any]:
        """
        Upload maintenance request photo with simplified handling.
        
        Args:
            file_data: Photo file data
            property_id: Property identifier
            request_id: Maintenance request identifier
            
        Returns:
            Dictionary containing upload details
        """
        try:
            # Validate file size
            file_data.seek(0, 2)
            size = file_data.tell()
            file_data.seek(0)
            
            if size > self.MAX_FILE_SIZE:
                raise S3Error("Photo too large - please upload a smaller image")
            
            # Generate simple key
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            key = f"maintenance/{property_id}/{request_id}/{timestamp}.jpg"
            
            # Upload with basic settings
            self.client.upload_fileobj(
                file_data,
                self.bucket,
                key,
                ExtraArgs={
                    'ContentType': 'image/jpeg',
                    'ACL': 'private',
                    'Metadata': {
                        'property_id': property_id,
                        'request_id': request_id
                    }
                }
            )
            
            logger.info(f"Photo uploaded successfully: {key}")
            
            return {
                "key": key,
                "size": size,
                "url": await self.generate_presigned_url(key)
            }
            
        except Exception as e:
            logger.error(f"Photo upload failed: {str(e)}")
            raise S3Error("Failed to upload photo - please try again") from e

    async def get_maintenance_photos(
        self,
        property_id: str,
        request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get maintenance photos for property or specific request.
        
        Args:
            property_id: Property identifier
            request_id: Optional request identifier to filter by
            
        Returns:
            List of photo details with presigned URLs
        """
        try:
            prefix = f"maintenance/{property_id}"
            if request_id:
                prefix = f"{prefix}/{request_id}"
            
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
                MaxKeys=50  # Reasonable limit for demo
            )
            
            photos = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    photos.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'url': await self.generate_presigned_url(obj['Key'])
                    })
            
            return photos
            
        except Exception as e:
            logger.error(f"Failed to list photos: {str(e)}")
            raise S3Error("Unable to retrieve photos") from e

    async def generate_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """Generate temporary access URL for photo"""
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate URL for {key}: {str(e)}")
            raise S3Error("Unable to generate photo URL") from e

    async def cleanup_demo_data(self, hours: int = 24) -> None:
        """
        Clean up old demo data.
        Keeps demo environment tidy by removing photos older than specified hours.
        """
        try:
            # Implementation would go here - removed for MVP
            pass
        except Exception as e:
            logger.warning(f"Demo cleanup failed: {str(e)}")
            # Non-critical for demo, just log warning