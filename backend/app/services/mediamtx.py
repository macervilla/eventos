import requests
from fastapi import HTTPException

from app.core.config import settings


class MediaMTX:
    def request(self, method, path, *, missing=False):
        try:
            response = requests.request(method, settings.mediamtx_api_url.rstrip("/") + path, timeout=3)
            if response.status_code == 404 and missing:
                return None
            response.raise_for_status()
            return response.json() if response.content else {}
        except (requests.RequestException, ValueError):
            raise HTTPException(503, "El servidor de video no esta disponible. Las fotos siguen funcionando") from None

    def path(self, path):
        return self.request("GET", "/v3/paths/get/" + path, missing=True)

    def sessions(self):
        resultado, page = [], 0
        while True:
            data = self.request("GET", f"/v3/webrtc/sessions/list?page={page}&itemsPerPage=100")
            resultado.extend(data.get("items", []))
            page += 1
            if page >= data.get("pageCount", 1):
                return resultado

    def kick(self, session_id):
        return self.request("POST", "/v3/webrtc/sessions/kick/" + session_id, missing=True)


mediamtx = MediaMTX()
