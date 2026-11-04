from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError

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
        content = await file.read(settings.max_upload_bytes + 1)
        if not content:
            raise HTTPException(status_code=400, detail="Archivo vacio")
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="La imagen supera el tamano maximo permitido")

        mime_type, extension = self._detect_image(content)
        try:
            with Image.open(BytesIO(content)) as comprobacion:
                if comprobacion.width * comprobacion.height > 20_000_000:
                    raise HTTPException(status_code=413, detail="La imagen supera 20 megapixeles")
                comprobacion.verify()
            with Image.open(BytesIO(content)) as original:
                imagen = ImageOps.exif_transpose(original)
                imagen.load()
                if extension == ".jpg":
                    imagen = imagen.convert("RGB")
                salida = BytesIO()
                imagen.save(salida, format={".jpg": "JPEG", ".png": "PNG", ".webp": "WEBP"}[extension])
                content = salida.getvalue()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
            raise HTTPException(400, "Contenido de imagen invalido") from exc
        media_uuid = str(uuid4())
        object_key = f"{owner}/{owner_uuid}/{kind}/{media_uuid}{extension}"
        path = self._safe_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        if kind == "portada":
            self.imagen_compartida(object_key)

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

    def imagen_compartida(self, object_key: str) -> str:
        original = self._safe_path(object_key)
        destino = original.with_suffix(".share.jpg")
        if not destino.exists():
            with Image.open(original) as imagen:
                if imagen.width * imagen.height > 20_000_000:
                    raise HTTPException(413, "Portada demasiado grande")
                imagen = ImageOps.exif_transpose(imagen).convert("RGB")
                imagen.thumbnail((1200, 630))
                lienzo = Image.new("RGB", (1200, 630), "#163c2e")
                lienzo.paste(imagen, ((1200 - imagen.width) // 2, (630 - imagen.height) // 2))
                lienzo.save(destino, format="JPEG", quality=85, optimize=True)
        return self.get_public_url(destino.relative_to(self.root).as_posix())

    def portada_predeterminada(self):
        path = self._safe_path("sistema/evento.png")
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            imagen = Image.new("RGB", (1200, 630), "#163c2e")
            from PIL import ImageDraw
            ImageDraw.Draw(imagen).text((80, 280), "Eventos", fill="white", font_size=76)
            imagen.save(path, "PNG")


media_storage = LocalMediaStorage()
