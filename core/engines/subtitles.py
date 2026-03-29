"""Moteur de sous-titrage de chants.

Affiche les paroles synchronisées ligne par ligne, couplet par couplet.
Fonctionne 100% offline - pas besoin de STT pour les chants connus.
Le STT live (Phase 3) viendra se greffer sur ce même moteur.
"""

import asyncio
from dataclasses import dataclass, asdict


@dataclass
class SubtitleState:
    active: bool = False
    mode: str = "song"           # song, stt_live, manual
    lines: list[str] = None      # lignes actuellement affichées (2-3 max)
    current_line_index: int = 0
    total_lines: int = 0
    song_title: str = ""
    verse_label: str = ""

    def __post_init__(self):
        if self.lines is None:
            self.lines = []


class SubtitleEngine:
    """Moteur de sous-titrage synchronisé."""

    def __init__(self):
        self.state = SubtitleState()
        self._listeners: list = []
        self._all_lines: list[str] = []
        self._display_count: int = 2  # nb de lignes affichées simultanément

    def add_listener(self, callback):
        self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def _notify(self):
        payload = {"type": "subtitle", **asdict(self.state)}
        for cb in list(self._listeners):
            try:
                await cb(payload)
            except Exception:
                self._listeners.remove(cb)

    def load_lyrics(self, song_title: str, verse_label: str, text: str, display_lines: int = 2):
        """Charge les paroles d'un couplet et prépare le sous-titrage."""
        self._all_lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        self._display_count = display_lines
        self.state = SubtitleState(
            active=True,
            mode="song",
            song_title=song_title,
            verse_label=verse_label,
            current_line_index=0,
            total_lines=len(self._all_lines),
            lines=self._all_lines[:display_lines],
        )

    async def start(self):
        """Affiche les premières lignes."""
        if self._all_lines:
            self.state.lines = self._all_lines[:self._display_count]
            self.state.current_line_index = 0
            self.state.active = True
            await self._notify()

    async def next_lines(self):
        """Avance d'un groupe de lignes."""
        idx = self.state.current_line_index + self._display_count
        if idx >= len(self._all_lines):
            return
        self.state.current_line_index = idx
        self.state.lines = self._all_lines[idx:idx + self._display_count]
        await self._notify()

    async def prev_lines(self):
        """Recule d'un groupe de lignes."""
        idx = max(0, self.state.current_line_index - self._display_count)
        self.state.current_line_index = idx
        self.state.lines = self._all_lines[idx:idx + self._display_count]
        await self._notify()

    async def goto_line(self, index: int):
        """Saute à une ligne spécifique."""
        if 0 <= index < len(self._all_lines):
            self.state.current_line_index = index
            self.state.lines = self._all_lines[index:index + self._display_count]
            await self._notify()

    async def show_manual(self, text: str):
        """Affiche un sous-titre manuel (mode STT ou texte libre)."""
        self.state = SubtitleState(
            active=True,
            mode="manual",
            lines=text.split("\n")[:3],
        )
        await self._notify()

    async def hide(self):
        """Cache les sous-titres."""
        self.state = SubtitleState(active=False)
        await self._notify()

    def get_state(self) -> dict:
        return asdict(self.state)


# Singleton
subtitles = SubtitleEngine()
