"""Virtual Screen Creator - Création et gestion d'écrans virtuels.

Permet de composer des écrans avec des couches (layers) :
texte, images, formes, horloge, ticker défilant.
Chaque écran peut être envoyé comme source OBS.
"""

import json
from dataclasses import dataclass, asdict, field


@dataclass
class Layer:
    id: int = 0
    layer_type: str = "text"    # text, image, shape, ticker, clock
    x: int = 0
    y: int = 0
    width: int = 400
    height: int = 100
    visible: bool = True
    properties: dict = field(default_factory=dict)
    # Properties examples:
    # text: {"content": "...", "font": "Segoe UI", "size": 32, "color": "#fff", "align": "center",
    #        "bold": true, "animation": "fade"}
    # image: {"src": "assets/logo.png", "fit": "contain"}
    # shape: {"shape": "rect", "fill": "#89b4fa", "opacity": 0.8, "radius": 10}
    # ticker: {"text": "Bienvenue...", "speed": 50, "direction": "left"}
    # clock: {"format": "HH:mm", "timezone": "America/New_York"}


@dataclass
class VirtualScreen:
    id: int = 0
    name: str = "Écran 1"
    width: int = 1920
    height: int = 1080
    bg_color: str = "#000000"
    bg_image: str = ""
    theme: str = "default"
    layers: list[Layer] = field(default_factory=list)


class VirtualScreenManager:
    """Gère la composition des écrans virtuels."""

    def __init__(self):
        self.screens: dict[int, VirtualScreen] = {}
        self.active_screen_id: int | None = None
        self._listeners: list = []

    def add_listener(self, callback):
        self._listeners.append(callback)

    async def _notify(self):
        if self.active_screen_id and self.active_screen_id in self.screens:
            screen = self.screens[self.active_screen_id]
            payload = {
                "type": "virtual_screen",
                "screen": asdict(screen),
            }
            for cb in list(self._listeners):
                try:
                    await cb(payload)
                except Exception:
                    self._listeners.remove(cb)

    def create_screen(self, name: str, width: int = 1920, height: int = 1080) -> VirtualScreen:
        sid = max(self.screens.keys(), default=0) + 1
        screen = VirtualScreen(id=sid, name=name, width=width, height=height)
        self.screens[sid] = screen
        return screen

    def add_layer(self, screen_id: int, layer_type: str, x: int = 0, y: int = 0,
                  width: int = 400, height: int = 100, properties: dict | None = None) -> Layer | None:
        screen = self.screens.get(screen_id)
        if not screen:
            return None
        lid = max((l.id for l in screen.layers), default=0) + 1
        layer = Layer(id=lid, layer_type=layer_type, x=x, y=y,
                      width=width, height=height, properties=properties or {})
        screen.layers.append(layer)
        return layer

    def update_layer(self, screen_id: int, layer_id: int, **kwargs) -> bool:
        screen = self.screens.get(screen_id)
        if not screen:
            return False
        for layer in screen.layers:
            if layer.id == layer_id:
                for k, v in kwargs.items():
                    if hasattr(layer, k):
                        setattr(layer, k, v)
                return True
        return False

    def remove_layer(self, screen_id: int, layer_id: int) -> bool:
        screen = self.screens.get(screen_id)
        if not screen:
            return False
        screen.layers = [l for l in screen.layers if l.id != layer_id]
        return True

    async def activate(self, screen_id: int):
        self.active_screen_id = screen_id
        await self._notify()

    def get_screen(self, screen_id: int) -> dict | None:
        screen = self.screens.get(screen_id)
        return asdict(screen) if screen else None

    def list_screens(self) -> list[dict]:
        return [asdict(s) for s in self.screens.values()]


# Singleton
screen_manager = VirtualScreenManager()
