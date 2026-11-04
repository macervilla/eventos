"""Contrato para integrar un proveedor oficial sin simular mensajes enviados."""

from typing import Protocol


class ProveedorValidacionTelefono(Protocol):
    def enviar_codigo(self, telefono: str, referencia: str) -> str:
        """Devuelve una referencia verificable del proveedor, nunca un envio ficticio."""
        ...

    def verificar_codigo(self, referencia_proveedor: str, codigo: str) -> bool: ...


proveedor: ProveedorValidacionTelefono | None = None
