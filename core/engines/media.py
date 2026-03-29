"""Moteur de gestion des médias - Images, Vidéos, Fonds d'écran.

Gère les arrière-plans (images/vidéos en boucle derrière les paroles),
les diaporamas, et la lecture de médias autonomes.
"""

import asyncio
from dataclasses import dataclass, asdict, field
from pathlib import Path


@dataclass
class BackgroundState:
    """Fond d'écran actif derrière les projections."""
    type: str = "color"          # color, image, video, slideshow
    color: str = "#000000"
    image_url: str = ""
    video_url: str = ""
    video_loop: bool = True
    slideshow_urls: list[str] = field(default_factory=list)
    slideshow_interval: int = 10  # secondes
    opacity: float = 0.85         # opacité de l'overlay texte


@dataclass
class MediaState:
    """État de lecture média autonome (vidéo plein écran, image)."""
    active: bool = False
    type: str = "none"           # image, video, web, pdf
    url: str = ""
    title: str = ""
    playing: bool = False
    loop: bool = False
    volume: int = 80
    current_time: float = 0
    duration: float = 0


@dataclass
class AlertState:
    """Message d'alerte/annonce superposé."""
    active: bool = False
    text: str = ""
    style: str = "banner"        # banner, fullscreen, ticker
    position: str = "bottom"     # top, bottom, center
    bg_color: str = "#f38ba8"
    text_color: str = "#1e1e2e"
    duration: int = 0            # 0 = permanent jusqu'à masquage


@dataclass
class ClockState:
    """Horloge, compte à rebours, chronomètre."""
    show_clock: bool = False
    clock_format: str = "HH:mm"
    show_countdown: bool = False
    countdown_target: str = ""   # ISO datetime ou durée "00:05:00"
    countdown_label: str = ""
    show_stopwatch: bool = False
    stopwatch_running: bool = False
    position: str = "top-right"  # top-left, top-right, bottom-left, bottom-right


class MediaEngine:
    """Gère fonds, médias, alertes et horloge."""

    def __init__(self):
        self.background = BackgroundState()
        self.media = MediaState()
        self.alert = AlertState()
        self.clock = ClockState()
        self._listeners: list = []

    def add_listener(self, callback):
        self._listeners.append(callback)

    async def _notify(self, msg_type: str, state):
        payload = {"type": msg_type, **asdict(state)}
        for cb in list(self._listeners):
            try:
                await cb(payload)
            except Exception:
                self._listeners.remove(cb)

    # ── Background ──

    async def set_background_color(self, color: str):
        self.background = BackgroundState(type="color", color=color)
        await self._notify("background", self.background)

    async def set_background_image(self, url: str, opacity: float = 0.85):
        self.background = BackgroundState(type="image", image_url=url, opacity=opacity)
        await self._notify("background", self.background)

    async def set_background_video(self, url: str, loop: bool = True, opacity: float = 0.85):
        self.background = BackgroundState(type="video", video_url=url, video_loop=loop, opacity=opacity)
        await self._notify("background", self.background)

    async def set_background_slideshow(self, urls: list[str], interval: int = 10, opacity: float = 0.85):
        self.background = BackgroundState(type="slideshow", slideshow_urls=urls,
                                          slideshow_interval=interval, opacity=opacity)
        await self._notify("background", self.background)

    # ── Media Playback ──

    async def play_media(self, media_type: str, url: str, title: str = "", loop: bool = False):
        self.media = MediaState(active=True, type=media_type, url=url, title=title,
                                playing=True, loop=loop)
        await self._notify("media", self.media)

    async def pause_media(self):
        self.media.playing = False
        await self._notify("media", self.media)

    async def resume_media(self):
        self.media.playing = True
        await self._notify("media", self.media)

    async def stop_media(self):
        self.media = MediaState()
        await self._notify("media", self.media)

    # ── Alert ──

    async def show_alert(self, text: str, style: str = "banner", position: str = "bottom",
                         bg_color: str = "#f38ba8", text_color: str = "#1e1e2e", duration: int = 0):
        self.alert = AlertState(active=True, text=text, style=style, position=position,
                                bg_color=bg_color, text_color=text_color, duration=duration)
        await self._notify("alert", self.alert)

    async def hide_alert(self):
        self.alert = AlertState()
        await self._notify("alert", self.alert)

    # ── Clock / Countdown / Stopwatch ──

    async def toggle_clock(self, show: bool, fmt: str = "HH:mm", position: str = "top-right"):
        self.clock.show_clock = show
        self.clock.clock_format = fmt
        self.clock.position = position
        await self._notify("clock", self.clock)

    async def start_countdown(self, target: str, label: str = "", position: str = "top-right"):
        self.clock.show_countdown = True
        self.clock.countdown_target = target
        self.clock.countdown_label = label
        self.clock.position = position
        await self._notify("clock", self.clock)

    async def stop_countdown(self):
        self.clock.show_countdown = False
        self.clock.countdown_target = ""
        await self._notify("clock", self.clock)

    async def toggle_stopwatch(self, running: bool, position: str = "top-right"):
        self.clock.show_stopwatch = True
        self.clock.stopwatch_running = running
        self.clock.position = position
        await self._notify("clock", self.clock)

    async def hide_stopwatch(self):
        self.clock.show_stopwatch = False
        self.clock.stopwatch_running = False
        await self._notify("clock", self.clock)

    def get_state(self) -> dict:
        return {
            "background": asdict(self.background),
            "media": asdict(self.media),
            "alert": asdict(self.alert),
            "clock": asdict(self.clock),
        }


# Singleton
media_engine = MediaEngine()
