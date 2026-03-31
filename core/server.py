"""Serveur FastAPI pour EBJFL-Broadcast - Application tout-en-un offline-first."""

import json
import sys
import os
from contextlib import asynccontextmanager

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Body, UploadFile, File, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from pathlib import Path

from core.obs_bridge import obs_bridge
from core.config import config
from core.auth import (
    authenticate_user, authenticate_by_pin, create_token, get_current_user,
    require_admin, require_operator, require_any, authenticate_ws,
    list_users, create_user, update_user, delete_user, update_last_login,
    get_optional_user,
)
from core.db.models import init_db
from core.db import crud
from core.engines.projection import projection
from core.engines.subtitles import subtitles
from core.engines.virtual_screen import screen_manager
from core.engines.media import media_engine
from core.engines.media_hub import media_hub


# ── WebSocket Manager ──

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        data = json.dumps(message, ensure_ascii=False)
        for ws in list(self.active):
            try:
                await ws.send_text(data)
            except Exception:
                if ws in self.active:
                    self.active.remove(ws)


manager = ConnectionManager()


async def _broadcast_cb(payload: dict):
    """Callback pour les moteurs -> WebSocket."""
    await manager.broadcast(payload)


# ── App ──

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    obs_bridge.connect()
    projection.add_listener(_broadcast_cb)
    subtitles.add_listener(_broadcast_cb)
    screen_manager.add_listener(_broadcast_cb)
    media_engine.add_listener(_broadcast_cb)
    media_hub.add_listener(_broadcast_cb)
    yield
    obs_bridge.disconnect()


app = FastAPI(title="EBJFL-Broadcast", version="0.2.0", lifespan=lifespan)
app.mount("/overlays", StaticFiles(directory="overlays"), name="overlays")
app.mount("/static", StaticFiles(directory="web/static"), name="static")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
os.makedirs("assets/uploads", exist_ok=True)


# ══════════════════════════════════════
#  STATUS
# ══════════════════════════════════════

@app.get("/status")
def get_status():
    return {
        "obs_connected": obs_bridge.connected,
        "obs_version": obs_bridge.get_version() if obs_bridge.connected else None,
        "clients_connected": len(manager.active),
        "projection": projection.get_state(),
        "subtitles": subtitles.get_state(),
        "media": media_engine.get_state(),
    }


@app.post("/obs/connect")
def obs_connect():
    ok = obs_bridge.connect()
    return {"connected": ok, "error": obs_bridge.error}


# ══════════════════════════════════════
#  PROJECTION (VideoPsalm replacement)
# ══════════════════════════════════════

@app.get("/projection/state")
def projection_state():
    return projection.get_state()


class BibleProjection(BaseModel):
    text: str
    reference: str
    version: str = "LSG"
    animation: str = "fade"
    theme_id: int = 0

@app.post("/projection/bible")
async def project_bible(data: BibleProjection):
    await projection.show_bible(data.text, data.reference, data.version, data.animation, data.theme_id)
    return {"ok": True}


class SongProjection(BaseModel):
    song_id: int
    animation: str = "fade"
    theme_id: int = 0

@app.post("/projection/song")
async def project_song(data: SongProjection):
    song = crud.song_get(data.song_id)
    if not song:
        return {"ok": False, "error": "Chant introuvable"}
    await projection.load_song(song["id"], song["title"], song.get("verses", []),
                               data.animation, data.theme_id)
    return {"ok": True, "total_verses": len(song.get("verses", []))}


@app.post("/projection/song/next")
async def project_song_next():
    await projection.song_next()
    return {"ok": True, "index": projection.state.current_verse_index}


@app.post("/projection/song/prev")
async def project_song_prev():
    await projection.song_prev()
    return {"ok": True, "index": projection.state.current_verse_index}


@app.post("/projection/song/goto/{index}")
async def project_song_goto(index: int):
    await projection.song_goto(index)
    return {"ok": True, "index": projection.state.current_verse_index}


class TextProjection(BaseModel):
    title: str
    text: str
    category: str = "text"
    animation: str = "fade"
    theme_id: int = 0

@app.post("/projection/text")
async def project_text(data: TextProjection):
    await projection.show_text(data.title, data.text, data.category, data.animation, data.theme_id)
    return {"ok": True}


@app.post("/projection/blank")
async def project_blank():
    await projection.blank()
    return {"ok": True}


# ══════════════════════════════════════
#  LOWER THIRDS
# ══════════════════════════════════════

class LowerThirdShow(BaseModel):
    name: str
    title: str = ""
    subtitle: str = ""
    social: str = ""
    animation: str = "slide-left"
    theme_id: int = 0

@app.post("/obs/lower-third")
async def send_lower_third(data: LowerThirdShow):
    await projection.show_lower_third(data.name, data.title, data.subtitle, data.social,
                                      data.animation, data.theme_id)
    return {"ok": True}


@app.post("/obs/lower-third/hide")
async def hide_lower_third():
    await projection.blank()
    return {"ok": True}


@app.get("/lower-thirds")
def list_lower_thirds(category: str = "", search: str = ""):
    return crud.lt_list(category, search)


class LTCreate(BaseModel):
    name: str
    title: str = ""
    subtitle: str = ""
    social: str = ""
    category: str = "general"

@app.post("/lower-thirds")
def create_lower_third(data: LTCreate):
    lt_id = crud.lt_create(data.name, data.title, data.subtitle, data.social, data.category)
    return {"id": lt_id}


@app.delete("/lower-thirds/{lt_id}")
def delete_lower_third(lt_id: int):
    crud.lt_delete(lt_id)
    return {"ok": True}


# ══════════════════════════════════════
#  SUBTITLES (Sous-titrage chants)
# ══════════════════════════════════════

@app.get("/subtitles/state")
def subtitle_state():
    return subtitles.get_state()


class SubtitleLoad(BaseModel):
    song_title: str
    verse_label: str
    text: str
    display_lines: int = 2

@app.post("/subtitles/load")
async def subtitle_load(data: SubtitleLoad):
    subtitles.load_lyrics(data.song_title, data.verse_label, data.text, data.display_lines)
    await subtitles.start()
    return {"ok": True, "total_lines": subtitles.state.total_lines}


@app.post("/subtitles/next")
async def subtitle_next():
    await subtitles.next_lines()
    return {"ok": True, "index": subtitles.state.current_line_index}


@app.post("/subtitles/prev")
async def subtitle_prev():
    await subtitles.prev_lines()
    return {"ok": True, "index": subtitles.state.current_line_index}


@app.post("/subtitles/hide")
async def subtitle_hide():
    await subtitles.hide()
    return {"ok": True}


class ManualSubtitle(BaseModel):
    text: str

@app.post("/subtitles/manual")
async def subtitle_manual(data: ManualSubtitle):
    await subtitles.show_manual(data.text)
    return {"ok": True}


# ══════════════════════════════════════
#  BIBLE
# ══════════════════════════════════════

@app.get("/bible/search")
def bible_search(q: str = "", version: str = "LSG"):
    if not q:
        return {"results": []}
    return {"results": crud.bible_search(q, version)}


@app.get("/bible/passage")
def bible_passage(book: str = "", chapter: int = 1, verse_start: int = 1,
                  verse_end: int = 0, version: str = "LSG"):
    return {"verses": crud.bible_get_passage(book, chapter, verse_start, verse_end, version)}


# ══════════════════════════════════════
#  SONGS / CHANTS
# ══════════════════════════════════════

@app.get("/songs")
def list_songs(songbook: str = "", search: str = ""):
    return crud.songs_list(songbook, search)


@app.get("/songs/{song_id}")
def get_song(song_id: int):
    song = crud.song_get(song_id)
    if not song:
        return {"error": "Chant introuvable"}
    return song


class SongCreate(BaseModel):
    songbook_code: str = "CEF"
    number: int | None = None
    title: str
    author: str = ""
    verses: list[dict] = []

@app.post("/songs")
def create_song(data: SongCreate):
    sid = crud.song_create(data.songbook_code, data.number, data.title, data.author, data.verses)
    return {"id": sid}


@app.delete("/songs/{song_id}")
def delete_song(song_id: int):
    crud.song_delete(song_id)
    return {"ok": True}


# ══════════════════════════════════════
#  SERVICES / PLANNING
# ══════════════════════════════════════

@app.get("/services")
def list_services():
    return crud.service_list()


@app.get("/services/{service_id}")
def get_service(service_id: int):
    svc = crud.service_get(service_id)
    if not svc:
        return {"error": "Service introuvable"}
    return svc


class ServiceCreate(BaseModel):
    title: str
    date: str
    theme: str = ""
    notes: str = ""

@app.post("/services")
def create_service(data: ServiceCreate):
    sid = crud.service_create(data.title, data.date, data.theme, data.notes)
    return {"id": sid}


class ServiceUpdate(BaseModel):
    title: str = ""
    date: str = ""
    theme: str = ""
    notes: str = ""

@app.put("/services/{service_id}")
def update_service(service_id: int, data: ServiceUpdate):
    fields = {k: v for k, v in data.model_dump().items() if v}
    ok = crud.service_update(service_id, **fields)
    return {"ok": ok}


@app.delete("/services/{service_id}")
def delete_service(service_id: int):
    crud.service_delete(service_id)
    return {"ok": True}


class ServiceItemAdd(BaseModel):
    item_type: str
    reference_id: int = 0
    custom_text: str = ""
    custom_title: str = ""

@app.post("/services/{service_id}/items")
def add_service_item(service_id: int, data: ServiceItemAdd):
    iid = crud.service_add_item(service_id, data.item_type, data.reference_id,
                                data.custom_text, data.custom_title)
    return {"id": iid}


@app.post("/services/items/{item_id}/status")
def update_item_status(item_id: int, status: str = "done"):
    crud.service_update_item_status(item_id, status)
    return {"ok": True}


class ReorderItems(BaseModel):
    item_ids: list[int]

@app.post("/services/{service_id}/reorder")
def reorder_service_items(service_id: int, data: ReorderItems):
    crud.service_reorder_items(service_id, data.item_ids)
    return {"ok": True}


class ServiceItemUpdate(BaseModel):
    custom_title: str = ""
    custom_text: str = ""

@app.put("/services/items/{item_id}")
def update_service_item(item_id: int, data: ServiceItemUpdate):
    fields = {k: v for k, v in data.model_dump().items() if v}
    crud.service_update_item(item_id, **fields)
    return {"ok": True}


@app.delete("/services/items/{item_id}")
def delete_service_item(item_id: int):
    crud.service_delete_item(item_id)
    return {"ok": True}


# ══════════════════════════════════════
#  CUSTOM TEXTS / ANNONCES
# ══════════════════════════════════════

@app.get("/texts")
def list_texts(category: str = ""):
    return crud.text_list(category)


class TextCreate(BaseModel):
    title: str
    content: str
    category: str = "announcement"

@app.post("/texts")
def create_text(data: TextCreate):
    tid = crud.text_create(data.title, data.content, data.category)
    return {"id": tid}


@app.delete("/texts/{text_id}")
def delete_text(text_id: int):
    crud.text_delete(text_id)
    return {"ok": True}


# ══════════════════════════════════════
#  THEMES
# ══════════════════════════════════════

@app.get("/themes")
def list_themes():
    return crud.theme_list()


@app.get("/themes/{theme_id}")
def get_theme(theme_id: int):
    return crud.theme_get(theme_id) or {"error": "Thème introuvable"}


# ══════════════════════════════════════
#  VIRTUAL SCREENS
# ══════════════════════════════════════

@app.get("/screens")
def list_screens():
    return screen_manager.list_screens()


class ScreenCreate(BaseModel):
    name: str
    width: int = 1920
    height: int = 1080

@app.post("/screens")
def create_screen(data: ScreenCreate):
    scr = screen_manager.create_screen(data.name, data.width, data.height)
    return {"id": scr.id}


@app.get("/screens/{screen_id}")
def get_screen(screen_id: int):
    return screen_manager.get_screen(screen_id) or {"error": "Écran introuvable"}


@app.post("/screens/{screen_id}/activate")
async def activate_screen(screen_id: int):
    await screen_manager.activate(screen_id)
    return {"ok": True}


# ══════════════════════════════════════
#  BACKGROUND (Fonds d'écran)
# ══════════════════════════════════════

class BgColor(BaseModel):
    color: str = "#000000"

@app.post("/background/color")
async def bg_color(data: BgColor):
    await media_engine.set_background_color(data.color)
    return {"ok": True}


class BgImage(BaseModel):
    url: str
    opacity: float = 0.85

@app.post("/background/image")
async def bg_image(data: BgImage):
    await media_engine.set_background_image(data.url, data.opacity)
    return {"ok": True}


class BgVideo(BaseModel):
    url: str
    loop: bool = True
    opacity: float = 0.85

@app.post("/background/video")
async def bg_video(data: BgVideo):
    await media_engine.set_background_video(data.url, data.loop, data.opacity)
    return {"ok": True}


# ══════════════════════════════════════
#  MEDIA (Lecture vidéo/image plein écran)
# ══════════════════════════════════════

class MediaPlay(BaseModel):
    type: str = "video"      # video, image, web
    url: str
    title: str = ""
    loop: bool = False

@app.post("/media/play")
async def media_play(data: MediaPlay):
    await media_engine.play_media(data.type, data.url, data.title, data.loop)
    return {"ok": True}


@app.post("/media/pause")
async def media_pause():
    await media_engine.pause_media()
    return {"ok": True}


@app.post("/media/resume")
async def media_resume():
    await media_engine.resume_media()
    return {"ok": True}


@app.post("/media/stop")
async def media_stop():
    await media_engine.stop_media()
    return {"ok": True}


# ══════════════════════════════════════
#  ALERT (Messages d'annonce superposés)
# ══════════════════════════════════════

class AlertShow(BaseModel):
    text: str
    style: str = "banner"       # banner, fullscreen, ticker
    position: str = "bottom"    # top, bottom, center
    bg_color: str = "#f38ba8"
    text_color: str = "#1e1e2e"
    duration: int = 0           # 0 = permanent

@app.post("/alert/show")
async def alert_show(data: AlertShow):
    await media_engine.show_alert(data.text, data.style, data.position,
                                  data.bg_color, data.text_color, data.duration)
    return {"ok": True}


@app.post("/alert/hide")
async def alert_hide():
    await media_engine.hide_alert()
    return {"ok": True}


# ══════════════════════════════════════
#  CLOCK / COUNTDOWN / STOPWATCH
# ══════════════════════════════════════

class ClockToggle(BaseModel):
    show: bool = True
    format: str = "HH:mm"
    position: str = "top-right"

@app.post("/clock/toggle")
async def clock_toggle(data: ClockToggle):
    await media_engine.toggle_clock(data.show, data.format, data.position)
    return {"ok": True}


class CountdownStart(BaseModel):
    target: str              # "00:05:00" ou ISO datetime
    label: str = ""
    position: str = "top-right"

@app.post("/clock/countdown")
async def clock_countdown(data: CountdownStart):
    await media_engine.start_countdown(data.target, data.label, data.position)
    return {"ok": True}


@app.post("/clock/countdown/stop")
async def clock_countdown_stop():
    await media_engine.stop_countdown()
    return {"ok": True}


class StopwatchToggle(BaseModel):
    running: bool = True
    position: str = "top-right"

@app.post("/clock/stopwatch")
async def clock_stopwatch(data: StopwatchToggle):
    await media_engine.toggle_stopwatch(data.running, data.position)
    return {"ok": True}


@app.post("/clock/stopwatch/hide")
async def clock_stopwatch_hide():
    await media_engine.hide_stopwatch()
    return {"ok": True}


# ══════════════════════════════════════
#  IMPORT (depuis l'interface)
# ══════════════════════════════════════

@app.get("/songbooks")
def list_songbooks():
    from core.db.models import get_db
    conn = get_db()
    rows = conn.execute("SELECT * FROM songbooks ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ══════════════════════════════════════
#  MEDIA HUB (Upload & Projection)
# ══════════════════════════════════════

@app.post("/upload-media")
async def upload_media(file: UploadFile = File(...)):
    content = await file.read()
    try:
        mf = await media_hub.save_upload(file.filename, content)
        return {"ok": True, "file": {"id": mf.id, "filename": mf.original_name,
                "type": mf.file_type, "status": mf.status, "size": mf.size}}
    except ValueError as e:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(e)})


@app.get("/media/files")
def list_media_files(type: str = ""):
    return media_hub.list_files(type)


@app.get("/media/files/{file_id}")
def get_media_file(file_id: str):
    mf = media_hub.get_file(file_id)
    if not mf:
        return {"error": "Fichier introuvable"}
    from dataclasses import asdict
    return asdict(mf)


@app.delete("/media/files/{file_id}")
def delete_media_file(file_id: str):
    ok = media_hub.delete_file(file_id)
    return {"ok": ok}


@app.post("/media/files/{file_id}/project")
async def project_media_file(file_id: str, slide: int = 0):
    await media_hub.project_file(file_id, slide)
    return {"ok": True}


@app.post("/media/slides/next")
async def media_slides_next():
    await media_hub.slide_next()
    return {"ok": True, "slide": media_hub.slideshow.current_slide}


@app.post("/media/slides/prev")
async def media_slides_prev():
    await media_hub.slide_prev()
    return {"ok": True, "slide": media_hub.slideshow.current_slide}


@app.post("/media/slides/goto/{index}")
async def media_slides_goto(index: int):
    await media_hub.slide_goto(index)
    return {"ok": True, "slide": media_hub.slideshow.current_slide}


@app.get("/media/slides/state")
def media_slides_state():
    return media_hub.get_slideshow_state()


@app.post("/media/slides/stop")
async def media_slides_stop():
    await media_hub.stop_slideshow()
    return {"ok": True}


# ══════════════════════════════════════
#  QR CODE
# ══════════════════════════════════════

@app.get("/qrcode")
def get_qr_code():
    """Génère un QR Code PNG pour l'URL d'upload."""
    import socket
    import qrcode
    import io
    from fastapi.responses import StreamingResponse

    ip = socket.gethostbyname(socket.gethostname())
    url = f"http://{ip}:{config.server.port}/static/upload.html"

    qr = qrcode.make(url)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png",
                             headers={"X-Upload-URL": url})


# ══════════════════════════════════════
#  AUTH (Login, Users, Roles)
# ══════════════════════════════════════

class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""
    pin: str = ""

@app.post("/auth/login")
def auth_login(data: LoginRequest):
    """Login par username/password ou par PIN."""
    user = None
    if data.pin:
        user = authenticate_by_pin(data.pin)
    elif data.username and data.password:
        user = authenticate_user(data.username, data.password)

    if not user:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Identifiants incorrects"})

    update_last_login(user["id"])
    token = create_token(user["id"], user["username"], user["role"])
    return {
        "ok": True,
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "role": user["role"],
        }
    }


@app.get("/auth/me")
def auth_me(user: dict = Depends(get_current_user)):
    """Retourne l'utilisateur courant."""
    return user


@app.get("/auth/users")
def auth_list_users(user: dict = Depends(require_admin)):
    """Liste tous les utilisateurs (admin only)."""
    return list_users()


class UserCreate(BaseModel):
    username: str
    display_name: str = ""
    password: str
    pin: str = ""
    role: str = "operator"

@app.post("/auth/users")
def auth_create_user(data: UserCreate, user: dict = Depends(require_admin)):
    """Créer un utilisateur (admin only)."""
    try:
        uid = create_user(data.username, data.display_name, data.password, data.role, data.pin)
        return {"ok": True, "id": uid}
    except Exception as e:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(e)})


class UserUpdate(BaseModel):
    display_name: str = ""
    role: str = ""
    password: str = ""
    pin: str = ""
    is_active: bool | None = None

@app.put("/auth/users/{user_id}")
def auth_update_user(user_id: int, data: UserUpdate, user: dict = Depends(require_admin)):
    """Modifier un utilisateur (admin only)."""
    fields = {k: v for k, v in data.model_dump().items() if v is not None and v != ""}
    ok = update_user(user_id, **fields)
    return {"ok": ok}


@app.delete("/auth/users/{user_id}")
def auth_delete_user(user_id: int, user: dict = Depends(require_admin)):
    """Supprimer un utilisateur (admin only, sauf admin)."""
    ok = delete_user(user_id)
    return {"ok": ok}


# ── Protected endpoints (add Depends to sensitive routes) ──

@app.delete("/songs/{song_id}/protected")
def delete_song_protected(song_id: int, user: dict = Depends(require_operator)):
    crud.song_delete(song_id)
    return {"ok": True}


@app.delete("/lower-thirds/{lt_id}/protected")
def delete_lt_protected(lt_id: int, user: dict = Depends(require_operator)):
    crud.lt_delete(lt_id)
    return {"ok": True}


@app.delete("/texts/{text_id}/protected")
def delete_text_protected(text_id: int, user: dict = Depends(require_operator)):
    crud.text_delete(text_id)
    return {"ok": True}


@app.delete("/media/files/{file_id}/protected")
def delete_media_protected(file_id: str, user: dict = Depends(require_operator)):
    ok = media_hub.delete_file(file_id)
    return {"ok": ok}


# ══════════════════════════════════════
#  BIBLE LSG (JSON offline-first)
# ══════════════════════════════════════

_bible_cache: dict[str, list[dict]] = {}   # version -> books
_chants_data: dict | None = None
_range = range  # sauvegarde du builtin pour éviter conflit avec le paramètre 'range'

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_BIBLE_FILES = {
    "lsg": "bible-lsg.json",
    "fr":  "bible-fr.json",
}


def _bible_filename(version: str) -> str:
    return _BIBLE_FILES.get(version.lower(), f"bible-{version.lower()}.json")


def _load_bible(version: str = "lsg") -> list[dict]:
    key = version.lower()
    if key in _bible_cache:
        return _bible_cache[key]
    fp = DATA_DIR / _bible_filename(key)
    if not fp.exists():
        _bible_cache[key] = []
        return _bible_cache[key]
    with open(fp, encoding="utf-8") as f:
        _bible_cache[key] = json.load(f)
    return _bible_cache[key]


def _load_chants():
    global _chants_data
    if _chants_data is not None:
        return _chants_data
    fp = DATA_DIR / "chants-desperance.json"
    if not fp.exists():
        _chants_data = {"Sections": [], "Chants": []}
        return _chants_data
    with open(fp, encoding="utf-8") as f:
        _chants_data = json.load(f)
    return _chants_data


def _serve_json_file(filepath: Path):
    """Sert un fichier JSON local en téléchargement."""
    if not filepath.exists():
        return JSONResponse(status_code=404, content={"error": f"Fichier {filepath.name} introuvable"})
    return FileResponse(filepath, media_type="application/json",
                        filename=filepath.name)


def _bible_find_book(abbrev: str, version: str = "lsg"):
    for book in _load_bible(version):
        if book["abbrev"] == abbrev:
            return book
    return None


@app.get("/api/bible/download")
def api_bible_download(version: str = "lsg"):
    """Sert le fichier Bible JSON pour téléchargement client (offline cache)."""
    return _serve_json_file(DATA_DIR / _bible_filename(version))


@app.get("/api/bible/books")
def api_bible_books(version: str = "lsg"):
    """Liste des livres avec nombre de chapitres."""
    return [
        {"abbrev": b["abbrev"], "name": b["name"], "chapters": len(b["chapters"])}
        for b in _load_bible(version)
    ]


@app.get("/api/bible/chapter/{abbrev}/{chapter}")
def api_bible_chapter(abbrev: str, chapter: int, version: str = "lsg"):
    """Tous les versets d'un chapitre."""
    book = _bible_find_book(abbrev, version)
    if not book:
        return JSONResponse(status_code=404, content={"error": "Livre introuvable"})
    if chapter < 1 or chapter > len(book["chapters"]):
        return JSONResponse(status_code=404, content={"error": "Chapitre introuvable"})
    verses = book["chapters"][chapter - 1]
    return {
        "book": book["name"],
        "abbrev": book["abbrev"],
        "chapter": chapter,
        "totalVerses": len(verses),
        "verses": [{"verse": i + 1, "text": v} for i, v in enumerate(verses)],
    }


@app.get("/api/bible/verse/{abbrev}/{chapter}/{verse}")
def api_bible_verse(abbrev: str, chapter: int, verse: int, version: str = "lsg"):
    """Un seul verset."""
    book = _bible_find_book(abbrev, version)
    if not book:
        return JSONResponse(status_code=404, content={"error": "Livre introuvable"})
    if chapter < 1 or chapter > len(book["chapters"]):
        return JSONResponse(status_code=404, content={"error": "Chapitre introuvable"})
    ch = book["chapters"][chapter - 1]
    if verse < 1 or verse > len(ch):
        return JSONResponse(status_code=404, content={"error": "Verset introuvable"})
    return {
        "book": book["name"],
        "abbrev": book["abbrev"],
        "chapter": chapter,
        "verse": verse,
        "text": ch[verse - 1],
    }


@app.get("/api/bible/passage/{abbrev}/{chapter}/{range}")
def api_bible_passage_range(abbrev: str, chapter: int, range: str, version: str = "lsg"):
    """Passage (ex: jn/3/16-18)."""
    book = _bible_find_book(abbrev, version)
    if not book:
        return JSONResponse(status_code=404, content={"error": "Livre introuvable"})
    if chapter < 1 or chapter > len(book["chapters"]):
        return JSONResponse(status_code=404, content={"error": "Chapitre introuvable"})
    ch = book["chapters"][chapter - 1]
    parts = range.split("-")
    start = int(parts[0])
    end = int(parts[1]) if len(parts) > 1 else start
    start = max(1, start)
    end = min(len(ch), end)
    return {
        "book": book["name"],
        "chapter": chapter,
        "verses": [{"verse": i, "text": ch[i - 1]} for i in _range(start, end + 1)],
    }


@app.post("/api/bible/reload")
def api_bible_reload(version: str = "lsg"):
    """Recharge le fichier Bible depuis le disque."""
    _bible_cache.pop(version.lower(), None)
    books = _load_bible(version)
    return {"ok": True, "version": version, "books": len(books)}


# ══════════════════════════════════════
#  CHANTS D'ESPÉRANCE (JSON offline-first)
# ══════════════════════════════════════

def _chants_section_by_id(sid: int):
    for s in _load_chants().get("Sections", []):
        if s[0] == sid:
            return s
    return None


@app.get("/api/chants/download")
def api_chants_download():
    """Sert le fichier Chants d'Espérance JSON pour téléchargement client (offline cache)."""
    return _serve_json_file(DATA_DIR / "chants-desperance.json")


@app.get("/api/chants/sections")
def api_chants_sections():
    """Liste des sections."""
    return [
        {"id": s[0], "nom": s[1], "total": s[2]}
        for s in _load_chants().get("Sections", [])
    ]


@app.get("/api/chants/list/{section_id}")
def api_chants_list(section_id: int):
    """Liste des chants d'une section."""
    sec = _chants_section_by_id(section_id)
    if not sec:
        return JSONResponse(status_code=404, content={"error": "Section introuvable"})
    chants = [
        {"numero": c[1], "titre": c[2]}
        for c in _load_chants().get("Chants", [])
        if c[0] == section_id
    ]
    return {"section": sec[1], "total": sec[2], "chants": chants}


@app.get("/api/chants/{section_id}/{numero}")
def api_chants_detail(section_id: int, numero: int):
    """Détail d'un chant avec paroles."""
    sec = _chants_section_by_id(section_id)
    if not sec:
        return JSONResponse(status_code=404, content={"error": "Section introuvable"})
    for c in _load_chants().get("Chants", []):
        if c[0] == section_id and c[1] == numero:
            return {
                "sectionId": section_id,
                "section": sec[1],
                "numero": c[1],
                "titre": c[2],
                "paroles": c[3],
            }
    return JSONResponse(status_code=404, content={"error": "Chant introuvable"})


import unicodedata

def _normalize(text: str) -> str:
    """Supprime les accents et met en minuscule pour la recherche."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


@app.get("/api/chants/search")
def api_chants_search(q: str = "", section_id: int = 0, limit: int = 50):
    """Recherche par numéro, titre ou paroles (insensible aux accents)."""
    if not q:
        return []
    q_norm = _normalize(q.strip())
    q_is_num = q.strip().lstrip("#").isdigit()
    q_num = int(q.strip().lstrip("#")) if q_is_num else 0

    sections = {s[0]: s[1] for s in _load_chants().get("Sections", [])}
    exact = []
    title_match = []
    first_line_match = []
    paroles_match = []

    for c in _load_chants().get("Chants", []):
        if section_id and c[0] != section_id:
            continue

        entry = {
            "sectionId": c[0],
            "section": sections.get(c[0], ""),
            "numero": c[1],
            "titre": c[2],
            "paroles": c[3],
            "firstLine": c[3].split("\n")[0].strip() if c[3] else "",
        }

        # 1. Exact number match
        if q_is_num and c[1] == q_num:
            exact.append(entry)
        # 2. Title match
        elif q_norm in _normalize(c[2]):
            title_match.append(entry)
        # 3. First line match
        elif c[3] and q_norm in _normalize(c[3].split("\n")[0]):
            first_line_match.append(entry)
        # 4. Paroles match
        elif q_norm in _normalize(c[3]):
            paroles_match.append(entry)

    # Tri: exact > titre > première ligne > paroles
    results = exact + title_match + first_line_match + paroles_match
    return results[:limit]


@app.post("/api/chants/reload")
def api_chants_reload():
    """Recharge le fichier chants-desperance.json (sync manuelle)."""
    global _chants_data
    _chants_data = None
    _load_chants()
    return {"ok": True, "sections": len(_chants_data.get("Sections", [])),
            "chants": len(_chants_data.get("Chants", []))}


def _save_chants():
    """Sauvegarde les chants en JSON."""
    fp = DATA_DIR / "chants-desperance.json"
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(_chants_data, f, ensure_ascii=False)


# ── CRUD Sections ──

class SectionCreate(BaseModel):
    nom: str

@app.post("/api/chants/sections")
def api_chants_section_create(data: SectionCreate):
    """Créer une nouvelle section/recueil."""
    d = _load_chants()
    new_id = max((s[0] for s in d["Sections"]), default=0) + 1
    d["Sections"].append([new_id, data.nom, 0])
    _save_chants()
    return {"ok": True, "id": new_id}


class SectionUpdate(BaseModel):
    nom: str

@app.put("/api/chants/sections/{section_id}")
def api_chants_section_update(section_id: int, data: SectionUpdate):
    """Renommer une section."""
    d = _load_chants()
    for s in d["Sections"]:
        if s[0] == section_id:
            s[1] = data.nom
            _save_chants()
            return {"ok": True}
    return JSONResponse(status_code=404, content={"error": "Section introuvable"})


@app.delete("/api/chants/sections/{section_id}")
def api_chants_section_delete(section_id: int):
    """Supprimer une section et tous ses chants."""
    d = _load_chants()
    d["Sections"] = [s for s in d["Sections"] if s[0] != section_id]
    d["Chants"] = [c for c in d["Chants"] if c[0] != section_id]
    _save_chants()
    return {"ok": True}


# ── CRUD Chants ──

class ChantCreate(BaseModel):
    section_id: int
    numero: int = 0
    titre: str
    paroles: str = ""

@app.post("/api/chants")
def api_chants_create(data: ChantCreate):
    """Créer un nouveau chant."""
    d = _load_chants()
    # Auto-numero si 0
    numero = data.numero
    if numero == 0:
        existing = [c[1] for c in d["Chants"] if c[0] == data.section_id]
        numero = max(existing, default=0) + 1
    d["Chants"].append([data.section_id, numero, data.titre, data.paroles])
    # Update section total
    for s in d["Sections"]:
        if s[0] == data.section_id:
            s[2] = len([c for c in d["Chants"] if c[0] == data.section_id])
    _save_chants()
    return {"ok": True, "numero": numero}


class ChantUpdate(BaseModel):
    titre: str = ""
    paroles: str = ""

@app.put("/api/chants/{section_id}/{numero}")
def api_chants_update(section_id: int, numero: int, data: ChantUpdate):
    """Modifier un chant."""
    d = _load_chants()
    for c in d["Chants"]:
        if c[0] == section_id and c[1] == numero:
            if data.titre:
                c[2] = data.titre
            if data.paroles:
                c[3] = data.paroles
            _save_chants()
            return {"ok": True}
    return JSONResponse(status_code=404, content={"error": "Chant introuvable"})


@app.delete("/api/chants/{section_id}/{numero}")
def api_chants_delete(section_id: int, numero: int):
    """Supprimer un chant."""
    d = _load_chants()
    d["Chants"] = [c for c in d["Chants"] if not (c[0] == section_id and c[1] == numero)]
    for s in d["Sections"]:
        if s[0] == section_id:
            s[2] = len([c for c in d["Chants"] if c[0] == section_id])
    _save_chants()
    return {"ok": True}


# ══════════════════════════════════════
#  WEBSOCKET
# ══════════════════════════════════════

@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    await manager.connect(websocket)
    ws_user = await authenticate_ws(websocket)
    try:
        await websocket.send_text(json.dumps({
            "type": "init",
            "projection": projection.get_state(),
            "subtitles": subtitles.get_state(),
            "media": media_engine.get_state(),
            "slideshow": media_hub.get_slideshow_state(),
            "user": ws_user,
        }, ensure_ascii=False))
    except Exception:
        pass
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            await manager.broadcast(message)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
