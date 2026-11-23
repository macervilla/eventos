import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.eventos import Evento
from app.models.proveedores import Proveedor
from app.models.slugs import RESERVED_SLUGS, SlugPublico
from app.services.proveedores import validate_requested_slug
from tests.test_administracion import auth
from tests.test_edicion_evento import datos


def test_resolucion_y_404(contexto):
    client, db, _, usuario, evento = contexto
    proveedor = Proveedor(nombre_comercial="Salon", slug="salon", usuario_id=usuario.id)
    db.add(proveedor); db.commit()
    assert client.get(f"/publico/{evento.slug}").json() == {"tipo": "evento", "slug": evento.slug}
    assert client.get("/publico/salon").json() == {"tipo": "proveedor", "slug": "salon"}
    assert client.get("/publico/inexistente").status_code == 404
    proveedor.activo = False; db.commit()
    assert client.get("/publico/salon").status_code == 404
    with pytest.raises(HTTPException) as exc:
        validate_requested_slug(db, "salon")
    assert exc.value.status_code == 409  # La baja logica no libera el slug.


@pytest.mark.parametrize("reservado", sorted(RESERVED_SLUGS))
def test_rutas_reservadas(contexto, reservado):
    _, db, *_ = contexto
    with pytest.raises(HTTPException) as exc:
        validate_requested_slug(db, reservado)
    assert exc.value.status_code == 422


def test_duplicados_entre_tipos(contexto):
    client, db, _, usuario, evento = contexto
    payload = {"nombre_comercial": "Duplicado", "slug": evento.slug,
               "email": usuario.email, "categorias": ["salon"],
               "direccion": "Calle 123", "localidad": "Rio Gallegos", "provincia": "Santa Cruz"}
    assert client.post("/proveedores", json=payload).status_code == 409
    db.add(Proveedor(nombre_comercial="Salon", slug="salon", usuario_id=usuario.id))
    db.commit()
    assert client.post("/eventos", json={**datos(), "nombre": "Evento", "slug": "salon",
                                         "email": usuario.email}).status_code == 409
    # La restriccion tambien protege inserciones que evitan el validador.
    db.add(Proveedor(nombre_comercial="Duplicado", slug=evento.slug, usuario_id=usuario.id))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
    assert db.scalar(select(SlugPublico).where(SlugPublico.slug == evento.slug)).tipo == "evento"


def test_proveedor_slug_inmutable(contexto):
    client, db, _, usuario, _ = contexto
    proveedor = Proveedor(nombre_comercial="Salon", slug="salon", usuario_id=usuario.id,
                          email=usuario.email)
    db.add(proveedor); db.commit()
    payload = {"nombre_comercial": "Salon", "slug": "otro", "email": usuario.email,
               "categorias": ["salon"], "direccion": "Calle 123",
               "localidad": "Rio Gallegos", "provincia": "Santa Cruz"}
    assert client.put("/proveedores/salon", json=payload, headers=auth(usuario)).status_code == 422
    db.refresh(proveedor)
    assert proveedor.slug == "salon"
    assert db.get(SlugPublico, "otro") is None
    payload["slug"] = "salon"
    assert client.put("/proveedores/salon", json=payload, headers=auth(usuario)).status_code == 200


def test_evento_nombre_y_slug_no_cambian_por_api(contexto):
    client, db, _, usuario, evento = contexto
    original = evento.nombre
    assert client.put(f"/eventos/{evento.slug}", json=datos(nombre="Otro", slug="otro"),
                      headers=auth(usuario)).status_code == 422
    db.refresh(evento)
    assert (evento.nombre, evento.slug) == (original, "prueba")


def test_enlaces_email_y_og_unificados(contexto, monkeypatch):
    from app.services import email
    from app.core.config import settings
    client, _, _, usuario, evento = contexto
    monkeypatch.setattr(settings, "frontend_public_url", "https://example.com/eventos")
    mensajes = []
    monkeypatch.setattr(email, "_send_email", lambda *args: mensajes.append(args))
    email.send_event_confirmation_email(evento, usuario.email)
    assert "https://example.com/eventos/prueba?confirmar=" in mensajes[0][3]
    html = client.get("/compartir/prueba").text
    assert 'content="https://example.com/eventos/prueba"' in html
    assert "/eventos/e/" not in html


def test_fastapi_no_ofrece_rutas_publicas_anteriores(contexto):
    client, *_ = contexto
    for path in ("/e/prueba", "/p/prueba"):
        respuesta = client.get(path, follow_redirects=False)
        assert respuesta.status_code == 404
        assert "location" not in respuesta.headers
