from pydantic import BaseModel


class MediaRead(BaseModel):
    id: int
    uuid: str
    tipo: str
    object_key: str
    public_url: str
    original_filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
