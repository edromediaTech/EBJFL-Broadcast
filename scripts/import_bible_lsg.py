"""Script d'import de la Bible Louis Segond (LSG) depuis l'API getBible.

Usage: python scripts/import_bible_lsg.py

Télécharge les 66 livres de la Bible LSG et les importe dans la BDD SQLite.
Fonctionne par chapitres pour éviter les timeouts.
"""

import json
import sys
import time
import urllib.request
import ssl
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db.models import init_db, get_db

# ── Livres de la Bible LSG ──
BOOKS = [
    # AT
    (1, "Genèse", "Gen", "AT"),
    (2, "Exode", "Exo", "AT"),
    (3, "Lévitique", "Lev", "AT"),
    (4, "Nombres", "Nom", "AT"),
    (5, "Deutéronome", "Deu", "AT"),
    (6, "Josué", "Jos", "AT"),
    (7, "Juges", "Jug", "AT"),
    (8, "Ruth", "Rut", "AT"),
    (9, "1 Samuel", "1Sa", "AT"),
    (10, "2 Samuel", "2Sa", "AT"),
    (11, "1 Rois", "1Ro", "AT"),
    (12, "2 Rois", "2Ro", "AT"),
    (13, "1 Chroniques", "1Ch", "AT"),
    (14, "2 Chroniques", "2Ch", "AT"),
    (15, "Esdras", "Esd", "AT"),
    (16, "Néhémie", "Néh", "AT"),
    (17, "Esther", "Est", "AT"),
    (18, "Job", "Job", "AT"),
    (19, "Psaumes", "Psa", "AT"),
    (20, "Proverbes", "Pro", "AT"),
    (21, "Ecclésiaste", "Ecc", "AT"),
    (22, "Cantique des Cantiques", "Can", "AT"),
    (23, "Ésaïe", "Esa", "AT"),
    (24, "Jérémie", "Jér", "AT"),
    (25, "Lamentations", "Lam", "AT"),
    (26, "Ézéchiel", "Ezé", "AT"),
    (27, "Daniel", "Dan", "AT"),
    (28, "Osée", "Osé", "AT"),
    (29, "Joël", "Joë", "AT"),
    (30, "Amos", "Amo", "AT"),
    (31, "Abdias", "Abd", "AT"),
    (32, "Jonas", "Jon", "AT"),
    (33, "Michée", "Mic", "AT"),
    (34, "Nahum", "Nah", "AT"),
    (35, "Habakuk", "Hab", "AT"),
    (36, "Sophonie", "Sop", "AT"),
    (37, "Aggée", "Agg", "AT"),
    (38, "Zacharie", "Zac", "AT"),
    (39, "Malachie", "Mal", "AT"),
    # NT
    (40, "Matthieu", "Mat", "NT"),
    (41, "Marc", "Mar", "NT"),
    (42, "Luc", "Luc", "NT"),
    (43, "Jean", "Jea", "NT"),
    (44, "Actes", "Act", "NT"),
    (45, "Romains", "Rom", "NT"),
    (46, "1 Corinthiens", "1Co", "NT"),
    (47, "2 Corinthiens", "2Co", "NT"),
    (48, "Galates", "Gal", "NT"),
    (49, "Éphésiens", "Éph", "NT"),
    (50, "Philippiens", "Phi", "NT"),
    (51, "Colossiens", "Col", "NT"),
    (52, "1 Thessaloniciens", "1Th", "NT"),
    (53, "2 Thessaloniciens", "2Th", "NT"),
    (54, "1 Timothée", "1Ti", "NT"),
    (55, "2 Timothée", "2Ti", "NT"),
    (56, "Tite", "Tit", "NT"),
    (57, "Philémon", "Phm", "NT"),
    (58, "Hébreux", "Héb", "NT"),
    (59, "Jacques", "Jac", "NT"),
    (60, "1 Pierre", "1Pi", "NT"),
    (61, "2 Pierre", "2Pi", "NT"),
    (62, "1 Jean", "1Jn", "NT"),
    (63, "2 Jean", "2Jn", "NT"),
    (64, "3 Jean", "3Jn", "NT"),
    (65, "Jude", "Jud", "NT"),
    (66, "Apocalypse", "Apo", "NT"),
]

# Nombre de chapitres par livre
CHAPTERS = {
    1:50,2:40,3:27,4:36,5:34,6:24,7:21,8:4,9:31,10:24,11:22,12:25,
    13:29,14:36,15:10,16:13,17:10,18:42,19:150,20:31,21:12,22:8,
    23:66,24:52,25:5,26:48,27:12,28:14,29:3,30:9,31:1,32:4,33:7,
    34:3,35:3,36:3,37:2,38:14,39:4,
    40:28,41:16,42:24,43:21,44:28,45:16,46:16,47:13,48:6,49:6,
    50:4,51:4,52:5,53:3,54:6,55:4,56:3,57:1,58:13,59:5,60:5,61:3,
    62:5,63:1,64:1,65:1,66:22,
}


def fetch_chapter(book_num: int, chapter: int, retries: int = 3) -> dict | None:
    """Télécharge un chapitre depuis l'API."""
    url = f"https://bible-api.com/{book_num}.{chapter}?translation=lsg"
    # Alternative: use a direct JSON source
    for attempt in range(retries):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers={"User-Agent": "EBJFL-Broadcast/1.0"})
            data = urllib.request.urlopen(req, timeout=15, context=ctx).read()
            return json.loads(data)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                return None


def import_from_embedded():
    """Import la Bible à partir des données embarquées dans pythonbible (KJV/ASV)
    puis génère la LSG depuis une source en ligne, ou charge un fichier local."""

    init_db()
    conn = get_db()

    # Vérifier si déjà importé
    count = conn.execute("SELECT COUNT(*) FROM bible_verses").fetchone()[0]
    if count > 0:
        print(f"Bible déjà importée ({count} versets). Suppression et réimport...")
        conn.execute("DELETE FROM bible_verses")
        conn.execute("DELETE FROM bible_books")
        conn.execute("DELETE FROM bible_versions WHERE code = 'LSG'")
        conn.commit()

    # Créer la version
    conn.execute("INSERT OR IGNORE INTO bible_versions (code, name, language) VALUES ('LSG', 'Louis Segond 1910', 'fr')")
    conn.commit()
    ver_id = conn.execute("SELECT id FROM bible_versions WHERE code = 'LSG'").fetchone()[0]

    # Vérifier si un fichier local existe
    local_file = Path(__file__).parent.parent / "data" / "lsg.json"
    if local_file.exists():
        print(f"Fichier local trouvé: {local_file}")
        with open(local_file, "r", encoding="utf-8") as f:
            bible_data = json.load(f)
        _import_json_data(conn, ver_id, bible_data)
        conn.close()
        return

    # Sinon, télécharger depuis les APIs
    print("Téléchargement de la Bible LSG depuis les APIs...")
    print("Cela peut prendre quelques minutes...\n")

    total_verses = 0

    for book_num, name, short, testament in BOOKS:
        num_chapters = CHAPTERS[book_num]
        conn.execute(
            "INSERT INTO bible_books (version_id, book_number, name, short_name, testament) VALUES (?, ?, ?, ?, ?)",
            (ver_id, book_num, name, short, testament)
        )
        book_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        book_verses = 0
        for ch in range(1, num_chapters + 1):
            result = fetch_chapter(book_num, ch)
            if result and "verses" in result:
                for v in result["verses"]:
                    conn.execute(
                        "INSERT INTO bible_verses (book_id, chapter, verse, text) VALUES (?, ?, ?, ?)",
                        (book_id, ch, v["verse"], v["text"].strip())
                    )
                    book_verses += 1
            elif result and "text" in result:
                # Format simple: un seul texte
                conn.execute(
                    "INSERT INTO bible_verses (book_id, chapter, verse, text) VALUES (?, ?, ?, ?)",
                    (book_id, ch, 1, result["text"].strip())
                )
                book_verses += 1

            time.sleep(0.3)  # Rate limiting

        conn.commit()
        total_verses += book_verses
        print(f"  [{book_num:2d}/66] {name:<25s} {num_chapters:3d} ch. | {book_verses} versets")

    conn.close()
    print(f"\nImport terminé! {total_verses} versets importés.")


def _import_json_data(conn, ver_id, data):
    """Importe depuis un fichier JSON local structuré."""
    total = 0
    if isinstance(data, list):
        # Format: [{book, chapter, verse, text}, ...]
        current_book = None
        book_id = None
        for entry in data:
            bnum = entry.get("book", entry.get("book_number", 0))
            if bnum != current_book:
                current_book = bnum
                info = next((b for b in BOOKS if b[0] == bnum), None)
                if info:
                    conn.execute(
                        "INSERT INTO bible_books (version_id, book_number, name, short_name, testament) VALUES (?, ?, ?, ?, ?)",
                        (ver_id, info[0], info[1], info[2], info[3])
                    )
                    book_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            if book_id:
                conn.execute(
                    "INSERT INTO bible_verses (book_id, chapter, verse, text) VALUES (?, ?, ?, ?)",
                    (book_id, entry["chapter"], entry["verse"], entry["text"])
                )
                total += 1
    elif isinstance(data, dict):
        # Format: {"books": [{"name": ..., "chapters": [{"verses": [...]}]}]}
        books = data.get("books", data.get("resultset", {}).get("row", []))
        for bk in books:
            bnum = bk.get("book_number", bk.get("nr", 0))
            info = next((b for b in BOOKS if b[0] == bnum), None)
            if not info:
                continue
            conn.execute(
                "INSERT INTO bible_books (version_id, book_number, name, short_name, testament) VALUES (?, ?, ?, ?, ?)",
                (ver_id, info[0], info[1], info[2], info[3])
            )
            book_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            for ch in bk.get("chapters", []):
                ch_num = ch.get("chapter", ch.get("nr", 0))
                for v in ch.get("verses", []):
                    conn.execute(
                        "INSERT INTO bible_verses (book_id, chapter, verse, text) VALUES (?, ?, ?, ?)",
                        (book_id, ch_num, v.get("verse", v.get("nr", 0)), v.get("text", ""))
                    )
                    total += 1

    conn.commit()
    print(f"Import terminé! {total} versets importés depuis le fichier local.")


if __name__ == "__main__":
    import_from_embedded()
