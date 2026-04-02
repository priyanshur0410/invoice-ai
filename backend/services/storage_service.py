"""
Supabase Storage Service
- Uploads invoice files to Supabase Storage bucket
- Returns public URL for storage in DB
- Handles file deduplication via SHA-256 hash
"""
import os
import hashlib
import mimetypes
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
BUCKET_NAME = os.getenv("SUPABASE_BUCKET", "invoices")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


class StorageService:

    def file_hash(self, file_bytes: bytes) -> str:
        return hashlib.sha256(file_bytes).hexdigest()[:16]

    async def upload(self, file_bytes: bytes, filename: str, user_id: str = "anon") -> dict:
        """
        Upload file to Supabase storage.
        Returns: {url, path, hash, size}
        """
        file_hash = self.file_hash(file_bytes)
        ext = filename.rsplit(".", 1)[-1].lower()
        storage_path = f"{user_id}/{file_hash}.{ext}"

        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        # Check if file already exists (dedup)
        try:
            existing = supabase.storage.from_(BUCKET_NAME).get_public_url(storage_path)
            if existing:
                return {
                    "url": existing,
                    "path": storage_path,
                    "hash": file_hash,
                    "size": len(file_bytes),
                    "duplicate": True,
                }
        except Exception:
            pass

        # Upload
        supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": content_type},
        )

        url = supabase.storage.from_(BUCKET_NAME).get_public_url(storage_path)

        return {
            "url": url,
            "path": storage_path,
            "hash": file_hash,
            "size": len(file_bytes),
            "duplicate": False,
        }

    async def delete(self, storage_path: str):
        supabase.storage.from_(BUCKET_NAME).remove([storage_path])


storage_service = StorageService()
