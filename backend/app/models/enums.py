from enum import StrEnum


class EventoEstado(StrEnum):
    BORRADOR = "BORRADOR"
    PUBLICADO = "PUBLICADO"
    EN_CURSO = "EN_CURSO"
    FINALIZADO = "FINALIZADO"
    ARCHIVADO = "ARCHIVADO"


class EventoPrivacidad(StrEnum):
    PRIVADO = "PRIVADO"
    CON_ENLACE = "CON_ENLACE"
    PUBLICO = "PUBLICO"


class Plan(StrEnum):
    GRATIS = "GRATIS"
    PREMIUM = "PREMIUM"


class RolEvento(StrEnum):
    PROPIETARIO = "PROPIETARIO"
    ENCARGADO = "ENCARGADO"
    MODERADOR = "MODERADOR"
    DJ = "DJ"
    INVITADO = "INVITADO"


class EstadoConfirmacion(StrEnum):
    PENDIENTE = "PENDIENTE"
    CONFIRMADO = "CONFIRMADO"
    NO_ASISTE = "NO_ASISTE"


class MediaTipo(StrEnum):
    FOTO = "FOTO"
    VIDEO = "VIDEO"
    PORTADA = "PORTADA"
    LOGO = "LOGO"
    GALERIA = "GALERIA"


class MediaEstado(StrEnum):
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    OCULTO = "OCULTO"


class ProveedorCategoria(StrEnum):
    DJ = "DJ"
    SALON = "SALON"
    CATERING = "CATERING"
    FOTOGRAFIA = "FOTOGRAFIA"
    VIDEO = "VIDEO"
    ANIMACION = "ANIMACION"
    DECORACION = "DECORACION"
    SONIDO = "SONIDO"
    ILUMINACION = "ILUMINACION"
    OTROS = "OTROS"


class LocationPreferenceOrigen(StrEnum):
    GEOLOCATION = "GEOLOCATION"
    MANUAL = "MANUAL"
    EVENTO = "EVENTO"
