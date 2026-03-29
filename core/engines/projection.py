"""Moteur de projection - Gère l'état de ce qui est affiché à l'écran.

Remplace VideoPsalm : projection Bible, chants, textes libres, annonces.
Tout passe par ce moteur qui broadcast via WebSocket vers les overlays.
"""

import json
import asyncio
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class ProjectionType(str, Enum):
    BIBLE = "bible"
    SONG = "song"
    TEXT = "text"
    LOWER_THIRD = "lower_third"
    ANNOUNCEMENT = "announcement"
    MEDIA = "media"
    BLANK = "blank"


@dataclass
class ProjectionState:
    """État courant de la projection."""
    active: bool = False
    projection_type: str = "blank"
    title: str = ""
    main_text: str = ""
    sub_text: str = ""          # sous-titre, référence biblique, auteur
    footer: str = ""            # numéro de chant, version bible...
    theme_id: int = 0
    animation: str = "fade"     # fade, slide-up, slide-left, typewriter, none
    # Song-specific
    song_id: int = 0
    current_verse_index: int = 0
    total_verses: int = 0
    verse_label: str = ""
    # Bible-specific
    bible_ref: str = ""


class ProjectionEngine:
    """Moteur central de projection. Gère l'état et notifie les clients."""

    def __init__(self):
        self.state = ProjectionState()
        self._listeners: list = []  # WebSocket broadcast callbacks
        self._song_verses: list[dict] = []

    def add_listener(self, callback):
        self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def _notify(self):
        """Broadcast l'état à tous les overlays."""
        payload = {"type": "projection", **asdict(self.state)}
        for cb in list(self._listeners):
            try:
                await cb(payload)
            except Exception:
                self._listeners.remove(cb)

    # ── Projection Bible ──

    async def show_bible(self, text: str, reference: str, version: str = "LSG",
                         animation: str = "fade", theme_id: int = 0):
        self.state = ProjectionState(
            active=True,
            projection_type=ProjectionType.BIBLE,
            title=reference,
            main_text=text,
            sub_text=version,
            bible_ref=reference,
            animation=animation,
            theme_id=theme_id,
        )
        await self._notify()

    # ── Projection Chant ──

    async def load_song(self, song_id: int, title: str, verses: list[dict],
                        animation: str = "fade", theme_id: int = 0):
        """Charge un chant et affiche le premier couplet."""
        self._song_verses = verses
        idx = 0
        v = verses[idx] if verses else {}
        self.state = ProjectionState(
            active=True,
            projection_type=ProjectionType.SONG,
            title=title,
            main_text=v.get("text", ""),
            verse_label=v.get("verse_label", ""),
            song_id=song_id,
            current_verse_index=idx,
            total_verses=len(verses),
            animation=animation,
            theme_id=theme_id,
        )
        await self._notify()

    async def song_next(self):
        """Passe au couplet/refrain suivant."""
        if not self._song_verses:
            return
        idx = min(self.state.current_verse_index + 1, len(self._song_verses) - 1)
        v = self._song_verses[idx]
        self.state.current_verse_index = idx
        self.state.main_text = v.get("text", "")
        self.state.verse_label = v.get("verse_label", "")
        await self._notify()

    async def song_prev(self):
        """Revient au couplet précédent."""
        if not self._song_verses:
            return
        idx = max(self.state.current_verse_index - 1, 0)
        v = self._song_verses[idx]
        self.state.current_verse_index = idx
        self.state.main_text = v.get("text", "")
        self.state.verse_label = v.get("verse_label", "")
        await self._notify()

    async def song_goto(self, index: int):
        """Saute à un couplet spécifique."""
        if not self._song_verses or index < 0 or index >= len(self._song_verses):
            return
        v = self._song_verses[index]
        self.state.current_verse_index = index
        self.state.main_text = v.get("text", "")
        self.state.verse_label = v.get("verse_label", "")
        await self._notify()

    # ── Projection Texte libre / Annonce ──

    async def show_text(self, title: str, text: str, category: str = "text",
                        animation: str = "fade", theme_id: int = 0):
        ptype = ProjectionType.ANNOUNCEMENT if category == "announcement" else ProjectionType.TEXT
        self.state = ProjectionState(
            active=True,
            projection_type=ptype,
            title=title,
            main_text=text,
            animation=animation,
            theme_id=theme_id,
        )
        await self._notify()

    # ── Lower Third ──

    async def show_lower_third(self, name: str, title: str = "", subtitle: str = "",
                               social: str = "", animation: str = "slide-left", theme_id: int = 0):
        self.state = ProjectionState(
            active=True,
            projection_type=ProjectionType.LOWER_THIRD,
            title=name,
            main_text=title,
            sub_text=subtitle,
            footer=social,
            animation=animation,
            theme_id=theme_id,
        )
        await self._notify()

    # ── Contrôle global ──

    async def blank(self):
        """Écran noir."""
        self.state = ProjectionState(active=False, projection_type="blank")
        await self._notify()

    async def freeze(self):
        """Gèle l'affichage (ne broadcast plus)."""
        self.state.active = False

    def get_state(self) -> dict:
        return asdict(self.state)


# Singleton
projection = ProjectionEngine()
