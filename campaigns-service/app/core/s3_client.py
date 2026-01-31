import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

s3_client = boto3.client(
    's3',
    endpoint_url=settings.S3_ENDPOINT_URL,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION
)

def ensure_bucket_exists():
    try:
        s3_client.head_bucket(Bucket=settings.S3_BUCKET_NAME)
        logger.info(f"bucket {settings.S3_BUCKET_NAME} already exists")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            try:
                s3_client.create_bucket(Bucket=settings.S3_BUCKET_NAME)
                logger.info(f"created bucket {settings.S3_BUCKET_NAME}")
            except ClientError as create_error:
                logger.error(f"failed to create bucket: {create_error}")
                raise
        else:
            logger.error(f"error checking bucket: {e}")
            raise


def upload_file(file_content: bytes, file_key: str, content_type: str) -> str:
    ensure_bucket_exists()
    
    try:
        s3_client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=file_key,
            Body=file_content,
            ContentType=content_type
        )
        
        file_url = f"{settings.S3_PUBLIC_URL}/{settings.S3_BUCKET_NAME}/{file_key}"
        logger.info(f"file uploaded successfully: {file_url}")
        return file_url
    except ClientError as e:
        logger.error(f"failed to upload file: {e}")
        raise Exception(f"Failed to upload file to S3: {str(e)}")


def delete_file(file_key: str) -> None:
    try:
        s3_client.delete_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=file_key
        )
        logger.info(f"file deleted successfully: {file_key}")
    except ClientError as e:
        error_msg = str(e) if e else f"ClientError: {type(e).__name__}"
        logger.error(f"failed to delete file {file_key}: {error_msg}")
        raise Exception(f"Failed to delete file from S3: {error_msg}")
    except Exception as e:
        error_msg = str(e) if e else f"Error: {type(e).__name__}"
        logger.error(f"unexpected error deleting file {file_key}: {error_msg}")
        raise Exception(f"Failed to delete file from S3: {error_msg}")


def get_file(file_key: str) -> tuple[bytes, str]:
    """Download file from S3. Returns (body, content_type)."""
    ensure_bucket_exists()
    try:
        resp = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=file_key)
        body = resp["Body"].read()
        content_type = resp.get("ContentType") or "application/octet-stream"
        return body, content_type
    except ClientError as e:
        logger.error("failed to get file %s: %s", file_key, e)
        raise Exception(f"Failed to get file from S3: {e}") from e


def normalize_file_url(url: str) -> str:
    if not url:
        return url
    
    if "localstack:4566" in url:
        return url.replace("http://localstack:4566", settings.S3_PUBLIC_URL)
    
    return url

