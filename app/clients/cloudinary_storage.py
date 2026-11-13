from __future__ import annotations

import asyncio
import io
from typing import Any


def _ensure_cloudinary_config() -> None:
    from app.config.cloudinary_config import CloudinaryConfig

    CloudinaryConfig.initialize()


def _get_uploader() -> Any:
    import cloudinary.uploader

    return cloudinary.uploader


def extract_storage_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metadata:
        return None

    if metadata.get("provider") == "cloudinary":
        return metadata

    storage = metadata.get("storage")
    if isinstance(storage, dict) and storage.get("provider") == "cloudinary":
        return storage

    return None


def storage_metadata_from_upload_response(
    response: dict[str, Any],
    *,
    user_id: str,
    document_id: str,
    filename: str,
    folder: str,
    content_type: str | None = None,
) -> dict[str, Any]:
    return {
        "provider": "cloudinary",
        "folder": folder,
        "public_id": response.get("public_id"),
        "asset_id": response.get("asset_id"),
        "version": response.get("version"),
        "resource_type": response.get("resource_type", "raw"),
        "format": response.get("format"),
        "secure_url": response.get("secure_url"),
        "url": response.get("url"),
        "bytes": response.get("bytes"),
        "original_filename": filename,
        "content_type": content_type,
        "user_id": user_id,
        "document_id": document_id,
    }


class CloudinaryStorageClient:
    def __init__(self, folder_root: str = "documents") -> None:
        self._folder_root = folder_root

    def _folder_for_user(self, user_id: str) -> str:
        return f"{self._folder_root}/{user_id}"

    async def upload_document(
        self,
        user_id: str,
        document_id: str,
        file_data: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        _ensure_cloudinary_config()
        uploader = _get_uploader()
        folder = self._folder_for_user(user_id)

        payload = io.BytesIO(file_data)

        def _upload() -> dict[str, Any]:
            payload.seek(0)
            return uploader.upload(
                payload,
                resource_type="raw",
                folder=folder,
                public_id=document_id,
                use_filename=False,
                unique_filename=False,
                overwrite=True,
                filename_override=filename,
            )

        response = await asyncio.to_thread(_upload)
        return storage_metadata_from_upload_response(
            response,
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            folder=folder,
            content_type=content_type,
        )

    async def delete_document_asset(self, metadata: dict[str, Any] | None) -> bool:
        storage = extract_storage_metadata(metadata)
        if not storage:
            return False

        public_id = storage.get("public_id")
        if not public_id:
            return False

        _ensure_cloudinary_config()
        uploader = _get_uploader()
        resource_type = storage.get("resource_type", "raw")

        def _destroy() -> dict[str, Any]:
            return uploader.destroy(public_id, resource_type=resource_type, invalidate=True)

        response = await asyncio.to_thread(_destroy)
        return response.get("result") in {"ok", "not found"}


cloudinary_storage_client = CloudinaryStorageClient()
