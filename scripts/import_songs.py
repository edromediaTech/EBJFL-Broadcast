"""Import de chants depuis différents formats (OpenSong, EasyWorship, OpenLP, txt).

Usage:
    python scripts/import_songs.py --format opensong --dir /chemin/dossier --songbook CEF
    python scripts/import_songs.py --format easyworship --file export.db --songbook CEF
    python scripts/import_songs.py --format openLP --file songs.sqlite --songbook CEF
    python scripts/import_songs.py --format txt --dir /chemin/dossier --songbook CEF
    python scripts/import_songs.py --format ccli --dir /chemin/dossier --songbook CEF
"""

import json
import sys
import os
import re
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db.models import init_db, get_db


def parse_opensong(filepath: str) -> dict | None:
    """Parse un fichier OpenSong XML."""
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()

        title = root.findtext("title", "").strip() or Path(filepath).stem
        author = root.findtext("author", "").strip()
        key = root.findtext("key", "").strip()
        tempo = root.findtext("tempo", "").strip()
        lyrics_raw = root.findtext("lyrics", "")

        verses = _parse_opensong_lyrics(lyrics_raw)

        return {
            "title": title,
            "author": author,
            "key_signature": key,
            "tempo": int(tempo) if tempo.isdigit() else 0,
            "verses": verses,
        }
    except Exception as e:
        print(f"  Erreur parsing {filepath}: {e}")
        return None


def _parse_opensong_lyrics(raw: str) -> list[dict]:
    """Parse les paroles au format OpenSong."""
    verses = []
    current_label = ""
    current_type = "verse"
    current_lines = []

    for line in raw.split("\n"):
        line = line.rstrip()

        # Section marker: [V1], [C], [B], etc.
        if line.startswith("["):
            if current_lines:
                verses.append({
                    "type": current_type,
                    "label": current_label,
                    "text": "\n".join(current_lines),
                })
                current_lines = []

            marker = line.strip("[]").strip()
            if marker.upper().startswith("C"):
                current_type = "chorus"
                current_label = "Refrain" + (f" {marker[1:]}" if len(marker) > 1 else "")
            elif marker.upper().startswith("B"):
                current_type = "bridge"
                current_label = "Pont"
            elif marker.upper().startswith("V"):
                current_type = "verse"
                num = marker[1:] if len(marker) > 1 else ""
                current_label = f"Couplet {num}".strip()
            else:
                current_type = "verse"
                current_label = marker

        # Lyrics line (skip chord lines starting with .)
        elif line and not line.startswith("."):
            # Remove leading space (OpenSong format)
            text = line.lstrip(" ")
            if text:
                current_lines.append(text)

    if current_lines:
        verses.append({
            "type": current_type,
            "label": current_label,
            "text": "\n".join(current_lines),
        })

    return verses


def parse_txt_file(filepath: str) -> dict | None:
    """Parse un fichier texte simple.

    Format attendu:
        Titre: Mon Chant
        Auteur: Jean Dupont

        [Couplet 1]
        Première ligne
        ...

        [Refrain]
        ...
    """
    try:
        content = Path(filepath).read_text(encoding="utf-8")
        lines = content.strip().split("\n")

        title = Path(filepath).stem
        author = ""
        lyrics_start = 0

        # Extract metadata from first lines
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.lower().startswith("titre:"):
                title = stripped.split(":", 1)[1].strip()
                lyrics_start = i + 1
            elif stripped.lower().startswith("auteur:") or stripped.lower().startswith("author:"):
                author = stripped.split(":", 1)[1].strip()
                lyrics_start = i + 1
            elif stripped == "":
                lyrics_start = i + 1
            else:
                break

        # Parse title from filename if format "001 - Title.txt"
        stem = Path(filepath).stem
        match = re.match(r"^(\d+)\s*[-–]\s*(.+)$", stem)
        number = None
        if match:
            number = int(match.group(1))
            if title == stem:
                title = match.group(2).strip()

        # Parse verses
        lyrics_text = "\n".join(lines[lyrics_start:])
        verses = _parse_bracket_lyrics(lyrics_text)

        return {
            "number": number,
            "title": title,
            "author": author,
            "verses": verses,
        }
    except Exception as e:
        print(f"  Erreur parsing {filepath}: {e}")
        return None


def parse_ccli_file(filepath: str) -> dict | None:
    """Parse un fichier CCLI SongSelect (format texte)."""
    try:
        content = Path(filepath).read_text(encoding="utf-8")
        lines = content.strip().split("\n")

        title = ""
        author = ""
        ccli_number = ""
        verses = []
        current_label = ""
        current_type = "verse"
        current_lines = []

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("CCLI Song #"):
                ccli_number = stripped.replace("CCLI Song #", "").strip()
            elif stripped.startswith("Title:"):
                title = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("Author:") or stripped.startswith("Words and Music by"):
                author = stripped.split(":", 1)[-1].strip() if ":" in stripped else stripped.replace("Words and Music by", "").strip()
            elif stripped in ("Verse 1", "Verse 2", "Verse 3", "Verse 4", "Verse 5",
                              "Chorus", "Bridge", "Pre-Chorus", "Tag", "Ending",
                              "Couplet 1", "Couplet 2", "Couplet 3", "Couplet 4",
                              "Refrain", "Pont"):
                if current_lines:
                    verses.append({"type": current_type, "label": current_label,
                                   "text": "\n".join(current_lines)})
                    current_lines = []
                current_label = stripped
                current_type = "chorus" if "chorus" in stripped.lower() or "refrain" in stripped.lower() else "verse"
            elif stripped:
                current_lines.append(stripped)

        if current_lines:
            verses.append({"type": current_type, "label": current_label,
                           "text": "\n".join(current_lines)})

        if not title:
            title = Path(filepath).stem

        return {
            "title": title,
            "author": author,
            "verses": verses,
        }
    except Exception as e:
        print(f"  Erreur parsing {filepath}: {e}")
        return None


def _parse_bracket_lyrics(text: str) -> list[dict]:
    """Parse des paroles avec marqueurs [Couplet 1], [Refrain], etc."""
    verses = []
    current_label = ""
    current_type = "verse"
    current_lines = []

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("[") and "]" in stripped:
            if current_lines:
                verses.append({"type": current_type, "label": current_label,
                               "text": "\n".join(current_lines)})
                current_lines = []
            current_label = stripped.strip("[]")
            lbl_lower = current_label.lower()
            if "refrain" in lbl_lower or "chorus" in lbl_lower:
                current_type = "chorus"
            elif "pont" in lbl_lower or "bridge" in lbl_lower:
                current_type = "bridge"
            else:
                current_type = "verse"
        elif stripped:
            current_lines.append(stripped)

    if current_lines:
        verses.append({"type": current_type, "label": current_label,
                       "text": "\n".join(current_lines)})

    return verses


def import_songs(songs_data: list[dict], songbook_code: str = "CEF", force: bool = False):
    """Insère les chants parsés dans la BDD."""
    init_db()
    conn = get_db()

    sb = conn.execute("SELECT id FROM songbooks WHERE code = ?", (songbook_code,)).fetchone()
    if not sb:
        print(f"Recueil '{songbook_code}' introuvable.")
        conn.close()
        return 0
    sb_id = sb[0]

    total = 0
    for song in songs_data:
        title = song.get("title", "Sans titre")
        number = song.get("number")
        author = song.get("author", "")
        key_sig = song.get("key_signature", "")
        tempo = song.get("tempo", 0)

        conn.execute(
            "INSERT INTO songs (songbook_id, number, title, author, key_signature, tempo) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sb_id, number, title, author, key_sig, tempo)
        )
        song_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for i, v in enumerate(song.get("verses", [])):
            conn.execute(
                "INSERT INTO song_verses (song_id, verse_order, verse_type, verse_label, text) "
                "VALUES (?, ?, ?, ?, ?)",
                (song_id, i, v.get("type", "verse"), v.get("label", ""), v.get("text", ""))
            )
        total += 1

    conn.commit()
    conn.close()
    return total


def main():
    args = sys.argv[1:]

    fmt = "txt"
    source = ""
    songbook = "CEF"
    force = "--force" in args

    if "--format" in args:
        fmt = args[args.index("--format") + 1]
    if "--dir" in args:
        source = args[args.index("--dir") + 1]
    if "--file" in args:
        source = args[args.index("--file") + 1]
    if "--songbook" in args:
        songbook = args[args.index("--songbook") + 1]

    if not source:
        print("Usage:")
        print("  python scripts/import_songs.py --format opensong --dir ./chants/ --songbook CEF")
        print("  python scripts/import_songs.py --format txt --dir ./chants/ --songbook CEF")
        print("  python scripts/import_songs.py --format ccli --dir ./chants/ --songbook CEF")
        print()
        print("Formats supportés: opensong, txt, ccli")
        print("Recueils: CEF, CEC, CARL, MEL_FR, MEL_CR")
        return

    parsers = {
        "opensong": parse_opensong,
        "txt": parse_txt_file,
        "ccli": parse_ccli_file,
    }

    parser = parsers.get(fmt)
    if not parser:
        print(f"Format inconnu: {fmt}. Supportés: {', '.join(parsers.keys())}")
        return

    source_path = Path(source)
    songs = []

    if source_path.is_dir():
        extensions = {"opensong": ["*.xml", "*"], "txt": ["*.txt"], "ccli": ["*.txt", "*.usr"]}
        for ext in extensions.get(fmt, ["*"]):
            for f in sorted(source_path.glob(ext)):
                if f.is_file():
                    print(f"  Parsing: {f.name}")
                    song = parser(str(f))
                    if song and song.get("verses"):
                        songs.append(song)
    elif source_path.is_file():
        song = parser(str(source_path))
        if song:
            songs.append(song)

    if songs:
        total = import_songs(songs, songbook, force)
        print(f"\n{total} chants importés dans {songbook}.")
    else:
        print("Aucun chant trouvé.")


if __name__ == "__main__":
    main()
