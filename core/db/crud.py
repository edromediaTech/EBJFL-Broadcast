"""Opérations CRUD pour toutes les tables."""

import json
import sqlite3
from core.db.models import get_db


# ── Helpers ──

def _dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def _dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


# ══════════════════════════════════════
#  BIBLE
# ══════════════════════════════════════

def bible_search(query: str, version_code: str = "LSG", limit: int = 20) -> list[dict]:
    conn = get_db()
    rows = conn.execute("""
        SELECT bv.text, bb.short_name, bv.chapter, bv.verse, ver.code as version
        FROM bible_verses bv
        JOIN bible_books bb ON bv.book_id = bb.id
        JOIN bible_versions ver ON bb.version_id = ver.id
        WHERE ver.code = ? AND bv.text LIKE ?
        LIMIT ?
    """, (version_code, f"%{query}%", limit)).fetchall()
    conn.close()
    return _dicts(rows)


def bible_get_passage(book: str, chapter: int, verse_start: int, verse_end: int = 0, version: str = "LSG") -> list[dict]:
    conn = get_db()
    if verse_end <= 0:
        verse_end = verse_start
    rows = conn.execute("""
        SELECT bv.text, bv.verse
        FROM bible_verses bv
        JOIN bible_books bb ON bv.book_id = bb.id
        JOIN bible_versions ver ON bb.version_id = ver.id
        WHERE ver.code = ? AND (bb.short_name = ? OR bb.name = ?)
              AND bv.chapter = ? AND bv.verse BETWEEN ? AND ?
        ORDER BY bv.verse
    """, (version, book, book, chapter, verse_start, verse_end)).fetchall()
    conn.close()
    return _dicts(rows)


def bible_import_version(code: str, name: str, language: str, books: list[dict]):
    """Import complet d'une version biblique.
    books = [{"name": "Genèse", "short_name": "Gen", "testament": "AT", "book_number": 1,
              "chapters": [{"chapter": 1, "verses": [{"verse": 1, "text": "Au commencement..."}]}]}]
    """
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO bible_versions (code, name, language) VALUES (?, ?, ?)",
                 (code, name, language))
    ver_id = conn.execute("SELECT id FROM bible_versions WHERE code = ?", (code,)).fetchone()["id"]

    for book in books:
        conn.execute(
            "INSERT INTO bible_books (version_id, book_number, name, short_name, testament) VALUES (?, ?, ?, ?, ?)",
            (ver_id, book["book_number"], book["name"], book["short_name"], book["testament"]))
        book_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for ch in book.get("chapters", []):
            for v in ch.get("verses", []):
                conn.execute(
                    "INSERT INTO bible_verses (book_id, chapter, verse, text) VALUES (?, ?, ?, ?)",
                    (book_id, ch["chapter"], v["verse"], v["text"]))
    conn.commit()
    conn.close()


# ══════════════════════════════════════
#  CHANTS / SONGS
# ══════════════════════════════════════

def songs_list(songbook_code: str = "", search: str = "", limit: int = 500) -> list[dict]:
    conn = get_db()
    sql = """
        SELECT s.*, sb.code as songbook_code, sb.name as songbook_name
        FROM songs s JOIN songbooks sb ON s.songbook_id = sb.id
        WHERE 1=1
    """
    params = []
    if songbook_code:
        sql += " AND sb.code = ?"
        params.append(songbook_code)
    if search:
        sql += " AND (s.title LIKE ? OR CAST(s.number AS TEXT) = ?)"
        params.extend([f"%{search}%", search])
    sql += " ORDER BY s.number, s.title LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return _dicts(rows)


def song_get(song_id: int) -> dict | None:
    conn = get_db()
    song = _dict(conn.execute("SELECT * FROM songs WHERE id = ?", (song_id,)).fetchone())
    if song:
        song["verses"] = _dicts(conn.execute(
            "SELECT * FROM song_verses WHERE song_id = ? ORDER BY verse_order", (song_id,)).fetchall())
    conn.close()
    return song


def song_create(songbook_code: str, number: int | None, title: str, author: str = "",
                verses: list[dict] | None = None) -> int:
    conn = get_db()
    sb = conn.execute("SELECT id FROM songbooks WHERE code = ?", (songbook_code,)).fetchone()
    if not sb:
        raise ValueError(f"Songbook '{songbook_code}' introuvable")
    conn.execute("INSERT INTO songs (songbook_id, number, title, author) VALUES (?, ?, ?, ?)",
                 (sb["id"], number, title, author))
    song_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    for i, v in enumerate(verses or []):
        conn.execute(
            "INSERT INTO song_verses (song_id, verse_order, verse_type, verse_label, text) VALUES (?, ?, ?, ?, ?)",
            (song_id, i, v.get("type", "verse"), v.get("label", ""), v["text"]))
    conn.commit()
    conn.close()
    return song_id


def song_update(song_id: int, **fields) -> bool:
    conn = get_db()
    allowed = {"title", "author", "number", "key_signature", "tempo"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    sql = "UPDATE songs SET " + ", ".join(f"{k}=?" for k in updates) + " WHERE id=?"
    conn.execute(sql, [*updates.values(), song_id])
    conn.commit()
    conn.close()
    return True


def song_delete(song_id: int):
    conn = get_db()
    conn.execute("DELETE FROM song_verses WHERE song_id = ?", (song_id,))
    conn.execute("DELETE FROM songs WHERE id = ?", (song_id,))
    conn.commit()
    conn.close()


# ══════════════════════════════════════
#  LOWER THIRDS
# ══════════════════════════════════════

def lt_list(category: str = "", search: str = "") -> list[dict]:
    conn = get_db()
    sql = "SELECT * FROM lower_thirds WHERE 1=1"
    params = []
    if category:
        sql += " AND category = ?"
        params.append(category)
    if search:
        sql += " AND (name LIKE ? OR title LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    sql += " ORDER BY is_favorite DESC, name"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return _dicts(rows)


def lt_create(name: str, title: str = "", subtitle: str = "", social: str = "",
              category: str = "general") -> int:
    conn = get_db()
    conn.execute(
        "INSERT INTO lower_thirds (name, title, subtitle, social, category) VALUES (?, ?, ?, ?, ?)",
        (name, title, subtitle, social, category))
    lt_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return lt_id


def lt_update(lt_id: int, **fields) -> bool:
    conn = get_db()
    allowed = {"name", "title", "subtitle", "social", "category", "photo_path", "is_favorite"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    sql = "UPDATE lower_thirds SET " + ", ".join(f"{k}=?" for k in updates) + " WHERE id=?"
    conn.execute(sql, [*updates.values(), lt_id])
    conn.commit()
    conn.close()
    return True


def lt_delete(lt_id: int):
    conn = get_db()
    conn.execute("DELETE FROM lower_thirds WHERE id = ?", (lt_id,))
    conn.commit()
    conn.close()


# ══════════════════════════════════════
#  SERVICES / PLANNING
# ══════════════════════════════════════

def service_create(title: str, date: str, theme: str = "", notes: str = "") -> int:
    conn = get_db()
    conn.execute("INSERT INTO services (title, date, theme, notes) VALUES (?, ?, ?, ?)",
                 (title, date, theme, notes))
    sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return sid


def service_update(service_id: int, **fields) -> bool:
    if not fields:
        return False
    allowed = {"title", "date", "theme", "notes"}
    sets = [(k, v) for k, v in fields.items() if k in allowed and v is not None]
    if not sets:
        return False
    conn = get_db()
    sql = "UPDATE services SET " + ", ".join(f"{k} = ?" for k, _ in sets) + " WHERE id = ?"
    conn.execute(sql, [v for _, v in sets] + [service_id])
    conn.commit()
    conn.close()
    return True


def service_delete(service_id: int):
    conn = get_db()
    conn.execute("DELETE FROM service_items WHERE service_id = ?", (service_id,))
    conn.execute("DELETE FROM services WHERE id = ?", (service_id,))
    conn.commit()
    conn.close()


def service_get(service_id: int) -> dict | None:
    conn = get_db()
    svc = _dict(conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone())
    if svc:
        svc["items"] = _dicts(conn.execute(
            "SELECT * FROM service_items WHERE service_id = ? ORDER BY item_order", (service_id,)).fetchall())
    conn.close()
    return svc


def service_list(limit: int = 20) -> list[dict]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM services ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return _dicts(rows)


def service_add_item(service_id: int, item_type: str, reference_id: int = 0,
                     custom_text: str = "", custom_title: str = "", order: int = -1) -> int:
    conn = get_db()
    if order < 0:
        row = conn.execute("SELECT COALESCE(MAX(item_order), -1) + 1 FROM service_items WHERE service_id = ?",
                           (service_id,)).fetchone()
        order = row[0]
    conn.execute(
        "INSERT INTO service_items (service_id, item_order, item_type, reference_id, custom_text, custom_title) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (service_id, order, item_type, reference_id, custom_text, custom_title))
    item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return item_id


def service_update_item(item_id: int, **fields):
    allowed = {"custom_title", "custom_text", "item_type"}
    sets = [(k, v) for k, v in fields.items() if k in allowed and v is not None]
    if not sets:
        return
    conn = get_db()
    sql = "UPDATE service_items SET " + ", ".join(f"{k} = ?" for k, _ in sets) + " WHERE id = ?"
    conn.execute(sql, [v for _, v in sets] + [item_id])
    conn.commit()
    conn.close()


def service_update_item_status(item_id: int, status: str):
    conn = get_db()
    conn.execute("UPDATE service_items SET status = ? WHERE id = ?", (status, item_id))
    conn.commit()
    conn.close()


def service_delete_item(item_id: int):
    conn = get_db()
    conn.execute("DELETE FROM service_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def service_reorder_items(service_id: int, item_ids: list[int]):
    conn = get_db()
    for order, iid in enumerate(item_ids):
        conn.execute("UPDATE service_items SET item_order = ? WHERE id = ? AND service_id = ?",
                     (order, iid, service_id))
    conn.commit()
    conn.close()


# ══════════════════════════════════════
#  VIRTUAL SCREENS
# ══════════════════════════════════════

def screen_list() -> list[dict]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM virtual_screens ORDER BY name").fetchall()
    conn.close()
    return _dicts(rows)


def screen_create(name: str, width: int = 1920, height: int = 1080, theme: str = "default") -> int:
    conn = get_db()
    conn.execute("INSERT INTO virtual_screens (name, width, height, theme) VALUES (?, ?, ?, ?)",
                 (name, width, height, theme))
    sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return sid


def screen_get(screen_id: int) -> dict | None:
    conn = get_db()
    scr = _dict(conn.execute("SELECT * FROM virtual_screens WHERE id = ?", (screen_id,)).fetchone())
    if scr:
        scr["layers"] = _dicts(conn.execute(
            "SELECT * FROM screen_layers WHERE screen_id = ? ORDER BY layer_order", (screen_id,)).fetchall())
        for layer in scr["layers"]:
            layer["properties"] = json.loads(layer["properties"])
    conn.close()
    return scr


def screen_add_layer(screen_id: int, layer_type: str, x: int = 0, y: int = 0,
                     width: int = 400, height: int = 100, properties: dict | None = None) -> int:
    conn = get_db()
    row = conn.execute("SELECT COALESCE(MAX(layer_order), -1) + 1 FROM screen_layers WHERE screen_id = ?",
                       (screen_id,)).fetchone()
    order = row[0]
    conn.execute(
        "INSERT INTO screen_layers (screen_id, layer_order, layer_type, x, y, width, height, properties) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (screen_id, order, layer_type, x, y, width, height, json.dumps(properties or {})))
    lid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return lid


# ══════════════════════════════════════
#  CUSTOM TEXTS / ANNONCES
# ══════════════════════════════════════

def text_list(category: str = "") -> list[dict]:
    conn = get_db()
    if category:
        rows = conn.execute("SELECT * FROM custom_texts WHERE category = ? ORDER BY title",
                            (category,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM custom_texts ORDER BY title").fetchall()
    conn.close()
    return _dicts(rows)


def text_create(title: str, content: str, category: str = "announcement", style: dict | None = None) -> int:
    conn = get_db()
    conn.execute("INSERT INTO custom_texts (title, content, category, style) VALUES (?, ?, ?, ?)",
                 (title, content, category, json.dumps(style or {})))
    tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return tid


def text_update(text_id: int, **fields) -> bool:
    conn = get_db()
    allowed = {"title", "content", "category"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if "style" in fields:
        updates["style"] = json.dumps(fields["style"])
    if not updates:
        return False
    sql = "UPDATE custom_texts SET " + ", ".join(f"{k}=?" for k in updates) + " WHERE id=?"
    conn.execute(sql, [*updates.values(), text_id])
    conn.commit()
    conn.close()
    return True


def text_delete(text_id: int):
    conn = get_db()
    conn.execute("DELETE FROM custom_texts WHERE id = ?", (text_id,))
    conn.commit()
    conn.close()


# ══════════════════════════════════════
#  THEMES
# ══════════════════════════════════════

def theme_list() -> list[dict]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM themes ORDER BY name").fetchall()
    conn.close()
    return _dicts(rows)


def theme_get(theme_id: int) -> dict | None:
    conn = get_db()
    row = _dict(conn.execute("SELECT * FROM themes WHERE id = ?", (theme_id,)).fetchone())
    conn.close()
    return row
