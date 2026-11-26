import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config.env_config import get_settings


class R2Client:
    def __init__(self) -> None:
        settings = get_settings()
        self._bucket = settings.r2_bucket_name
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    def _document_path(self, user_id: str, document_id: str) -> str:
        return f"documents/{user_id}/{document_id}.pdf"

    async def upload_document(self, user_id: str, document_id: str, file_data: bytes) -> str:
        key = self._document_path(user_id, document_id)
        self._client.put_object(Bucket=self._bucket, Key=key, Body=file_data)
        return key

    async def get_document_url(self, user_id: str, document_id: str, expires_in: int = 3600) -> str:
        key = self._document_path(user_id, document_id)
        url = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url

    async def delete_document(self, user_id: str, document_id: str) -> None:
        key = self._document_path(user_id, document_id)
        self._client.delete_object(Bucket=self._bucket, Key=key)

    async def document_exists(self, user_id: str, document_id: str) -> bool:
        key = self._document_path(user_id, document_id)
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False


r2_client = R2Client()
