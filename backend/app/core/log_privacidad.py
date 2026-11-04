import logging
import re


class OcultarCredenciales(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            cliente, metodo, ruta, protocolo, estado = record.args
            ruta = re.sub(r"(/i/)[^/? ]+", r"\1[privado]", str(ruta))
            ruta = re.sub(r"(/importar/)(?!preview)[A-Za-z0-9_-]{20,}", r"\1[privado]", ruta)
            ruta = re.sub(r"([?&](?:token|enlace|confirmar)=)[^& ]+", r"\1[privado]", ruta)
            record.args = cliente, metodo, ruta, protocolo, estado
        return True


def proteger_logs():
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, OcultarCredenciales) for f in logger.filters):
        logger.addFilter(OcultarCredenciales())
