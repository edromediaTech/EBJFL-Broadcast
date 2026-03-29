"""Pont de connexion vers OBS Studio via obs-websocket v5."""

import threading
import obsws_python as obs

from core.config import config


class OBSBridge:
    """Gère la connexion et les commandes vers OBS Studio."""

    def __init__(self):
        self._client: obs.ReqClient | None = None
        self._lock = threading.Lock()
        self.connected = False
        self.error: str | None = None

    def connect(self) -> bool:
        """Tente une connexion à OBS WebSocket."""
        with self._lock:
            try:
                self._client = obs.ReqClient(
                    host=config.obs.host,
                    port=config.obs.port,
                    password=config.obs.password,
                    timeout=5,
                )
                self.connected = True
                self.error = None
                return True
            except Exception as e:
                self._client = None
                self.connected = False
                self.error = str(e)
                return False

    def disconnect(self):
        """Ferme la connexion OBS."""
        with self._lock:
            if self._client:
                try:
                    self._client.base_client.ws.close()
                except Exception:
                    pass
                self._client = None
            self.connected = False

    def get_version(self) -> str | None:
        """Retourne la version d'OBS si connecté."""
        if not self._client:
            return None
        try:
            resp = self._client.get_version()
            return resp.obs_version
        except Exception:
            self.connected = False
            return None

    def set_text(self, source_name: str, text: str) -> bool:
        """Met a jour le texte d'une source GDI+ dans OBS."""
        if not self._client:
            return False
        try:
            self._client.set_input_settings(
                name=source_name,
                settings={"text": text},
                overlay=True,
            )
            return True
        except Exception:
            return False

    def get_scene_list(self) -> list[str]:
        """Retourne la liste des scenes OBS."""
        if not self._client:
            return []
        try:
            resp = self._client.get_scene_list()
            return [s["sceneName"] for s in resp.scenes]
        except Exception:
            return []


obs_bridge = OBSBridge()
