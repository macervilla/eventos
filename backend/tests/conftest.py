"""Fixtures compartidas explicitas para toda la suite de Eventos."""
import pytest

from tests.test_administracion import contexto  # noqa: F401
from tests.test_google_oauth import claves, google  # noqa: F401


@pytest.fixture(autouse=True)
def sin_avisos_reales_de_agasajados(monkeypatch):
    monkeypatch.setattr("app.services.agasajados._send_email", lambda *args, **kwargs: None)
