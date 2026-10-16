from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.core.config import settings


ALLOWED_IMAGE_SIGNATURES = {
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/webp": (b"RIFF", ".webp"),
}


@dataclass(frozen=True)
class StoredMedia:
    object_key: str
    public_url: str
    original_filename: str | None
    mime_type: str
    size_bytes: int


class LocalMediaStorage:
    provider = "local"

    def __init__(self, root: str | None = None, public_base: str | None = None) -> None:
        self.root = Path(root or settings.media_root).resolve()
        self.public_base = (public_base or settings.media_public_base).rstrip("/")

    def _detect_image(self, content: bytes) -> tuple[str, str]:
        if content.startswith(ALLOWED_IMAGE_SIGNATURES["image/jpeg"][0]):
            return "image/jpeg", ALLOWED_IMAGE_SIGNATURES["image/jpeg"][1]
        if content.startswith(ALLOWED_IMAGE_SIGNATURES["image/png"][0]):
            return "image/png", ALLOWED_IMAGE_SIGNATURES["image/png"][1]
        if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
            return "image/webp", ".webp"
        raise HTTPException(status_code=400, detail="Formato de imagen no permitido")

    def _safe_path(self, object_key: str) -> Path:
        path = (self.root / object_key).resolve()
        if self.root not in path.parents and path != self.root:
            raise HTTPException(status_code=400, detail="Ruta de media invalida")
        return path

    async def save_image(self, file: UploadFile, *, owner: str, owner_uuid: str, kind: str) -> StoredMedia:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Archivo vacio")
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="La imagen supera el tamano maximo permitido")

        mime_type, extension = self._detect_image(content)
        media_uuid = str(uuid4())
        object_key = f"{owner}/{owner_uuid}/{kind}/{media_uuid}{extension}"
        path = self._safe_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

        return StoredMedia(
            object_key=object_key,
            public_url=self.get_public_url(object_key),
            original_filename=file.filename,
            mime_type=mime_type,
            size_bytes=len(content),
        )

    def get_public_url(self, object_key: str) -> str:
        return f"{self.public_base}/{object_key}"

    def exists(self, object_key: str) -> bool:
        return self._safe_path(object_key).exists()


media_storage = LocalMediaStorage()
