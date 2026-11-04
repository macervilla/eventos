from pydantic import BaseModel, Field


class ReferenciaGeograficaSchema(BaseModel):
    geoname_id: int | None = Field(default=None, gt=0)
    codigo_pais: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
