"""Import de Bibles françaises depuis scrollmapper/bible_databases (GitHub).

Usage:
    python scripts/import_bible.py                  # Importe Crampon (déjà téléchargé)
    python scripts/import_bible.py --download       # Télécharge + importe toutes les versions

Versions disponibles: FreCrampon, FreBBB, FreBDM1744, FreJND, FreSynodale1921, FrePGR
"""

import json
import sys
import ssl
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db.models import init_db, get_db

# ── Mapping noms anglais -> français + filtrage 66 livres canoniques ──

BOOK_MAP = {
    # AT
    "Genesis":          (1, "Genèse", "Gen", "AT"),
    "Exodus":           (2, "Exode", "Exo", "AT"),
    "Leviticus":        (3, "Lévitique", "Lev", "AT"),
    "Numbers":          (4, "Nombres", "Nom", "AT"),
    "Deuteronomy":      (5, "Deutéronome", "Deu", "AT"),
    "Joshua":           (6, "Josué", "Jos", "AT"),
    "Judges":           (7, "Juges", "Jug", "AT"),
    "Ruth":             (8, "Ruth", "Rut", "AT"),
    "I Samuel":         (9, "1 Samuel", "1Sa", "AT"),
    "II Samuel":        (10, "2 Samuel", "2Sa", "AT"),
    "I Kings":          (11, "1 Rois", "1Ro", "AT"),
    "II Kings":         (12, "2 Rois", "2Ro", "AT"),
    "I Chronicles":     (13, "1 Chroniques", "1Ch", "AT"),
    "II Chronicles":    (14, "2 Chroniques", "2Ch", "AT"),
    "Ezra":             (15, "Esdras", "Esd", "AT"),
    "Nehemiah":         (16, "Néhémie", "Néh", "AT"),
    "Esther":           (17, "Esther", "Est", "AT"),
    "Job":              (18, "Job", "Job", "AT"),
    "Psalms":           (19, "Psaumes", "Psa", "AT"),
    "Proverbs":         (20, "Proverbes", "Pro", "AT"),
    "Ecclesiastes":     (21, "Ecclésiaste", "Ecc", "AT"),
    "Song of Solomon":  (22, "Cantique des Cantiques", "Can", "AT"),
    "Isaiah":           (23, "Ésaïe", "Esa", "AT"),
    "Jeremiah":         (24, "Jérémie", "Jér", "AT"),
    "Lamentations":     (25, "Lamentations", "Lam", "AT"),
    "Ezekiel":          (26, "Ézéchiel", "Ezé", "AT"),
    "Daniel":           (27, "Daniel", "Dan", "AT"),
    "Hosea":            (28, "Osée", "Osé", "AT"),
    "Joel":             (29, "Joël", "Joë", "AT"),
    "Amos":             (30, "Amos", "Amo", "AT"),
    "Obadiah":          (31, "Abdias", "Abd", "AT"),
    "Jonah":            (32, "Jonas", "Jon", "AT"),
    "Micah":            (33, "Michée", "Mic", "AT"),
    "Nahum":            (34, "Nahum", "Nah", "AT"),
    "Habakkuk":         (35, "Habakuk", "Hab", "AT"),
    "Zephaniah":        (36, "Sophonie", "Sop", "AT"),
    "Haggai":           (37, "Aggée", "Agg", "AT"),
    "Zechariah":        (38, "Zacharie", "Zac", "AT"),
    "Malachi":          (39, "Malachie", "Mal", "AT"),
    # NT
    "Matthew":          (40, "Matthieu", "Mat", "NT"),
    "Mark":             (41, "Marc", "Mar", "NT"),
    "Luke":             (42, "Luc", "Luc", "NT"),
    "John":             (43, "Jean", "Jea", "NT"),
    "Acts":             (44, "Actes", "Act", "NT"),
    "Romans":           (45, "Romains", "Rom", "NT"),
    "I Corinthians":    (46, "1 Corinthiens", "1Co", "NT"),
    "II Corinthians":   (47, "2 Corinthiens", "2Co", "NT"),
    "Galatians":        (48, "Galates", "Gal", "NT"),
    "Ephesians":        (49, "Éphésiens", "Éph", "NT"),
    "Philippians":      (50, "Philippiens", "Phi", "NT"),
    "Colossians":       (51, "Colossiens", "Col", "NT"),
    "I Thessalonians":  (52, "1 Thessaloniciens", "1Th", "NT"),
    "II Thessalonians": (53, "2 Thessaloniciens", "2Th", "NT"),
    "I Timothy":        (54, "1 Timothée", "1Ti", "NT"),
    "II Timothy":       (55, "2 Timothée", "2Ti", "NT"),
    "Titus":            (56, "Tite", "Tit", "NT"),
    "Philemon":         (57, "Philémon", "Phm", "NT"),
    "Hebrews":          (58, "Hébreux", "Héb", "NT"),
    "James":            (59, "Jacques", "Jac", "NT"),
    "I Peter":          (60, "1 Pierre", "1Pi", "NT"),
    "II Peter":         (61, "2 Pierre", "2Pi", "NT"),
    "I John":           (62, "1 Jean", "1Jn", "NT"),
    "II John":          (63, "2 Jean", "2Jn", "NT"),
    "III John":         (64, "3 Jean", "3Jn", "NT"),
    "Jude":             (65, "Jude", "Jud", "NT"),
    "Revelation of John": (66, "Apocalypse", "Apo", "NT"),
}

# Versions disponibles sur scrollmapper
VERSIONS = {
    "FreCrampon":      ("LSG", "Bible Crampon 1923 (Français)", "fr"),
    "FreBBB":          ("BBB", "Bible de la Liturgie (Français)", "fr"),
    "FreBDM1744":      ("BDM", "Bible de Martin 1744 (Français)", "fr"),
    "FreJND":          ("JND", "Bible Darby (Français)", "fr"),
    "FreSynodale1921": ("SYN", "Bible Synodale 1921 (Français)", "fr"),
    "FrePGR":          ("PGR", "Bible Perret-Gentil et Rilliet (Français)", "fr"),
}

BASE_URL = "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json"


def download_bible(file_code: str) -> dict | None:
    """Télécharge un fichier Bible JSON depuis GitHub."""
    url = f"{BASE_URL}/{file_code}.json"
    local = Path(__file__).parent.parent / "data" / f"{file_code}.json"

    if local.exists():
        print(f"  Fichier local existant: {local}")
        with open(local, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"  Téléchargement: {url}")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "EBJFL-Broadcast/1.0"})
        data = urllib.request.urlopen(req, timeout=60, context=ctx).read()
        local.parent.mkdir(parents=True, exist_ok=True)
        with open(local, "wb") as f:
            f.write(data)
        print(f"  Sauvegardé: {local} ({len(data)} bytes)")
        return json.loads(data)
    except Exception as e:
        print(f"  Erreur téléchargement: {e}")
        return None


def import_bible(file_code: str, force: bool = False):
    """Importe une version de la Bible dans la BDD."""
    if file_code not in VERSIONS:
        print(f"Version inconnue: {file_code}")
        print(f"Disponibles: {', '.join(VERSIONS.keys())}")
        return

    code, name, lang = VERSIONS[file_code]
    init_db()
    conn = get_db()

    # Check if already imported
    existing = conn.execute("SELECT COUNT(*) FROM bible_verses bv "
                            "JOIN bible_books bb ON bv.book_id = bb.id "
                            "JOIN bible_versions bvr ON bb.version_id = bvr.id "
                            "WHERE bvr.code = ?", (code,)).fetchone()[0]
    if existing > 0 and not force:
        print(f"{name} ({code}) déjà importée: {existing} versets. Utilisez --force pour réimporter.")
        conn.close()
        return

    if existing > 0 and force:
        print(f"Suppression de l'ancienne version {code}...")
        ver_row = conn.execute("SELECT id FROM bible_versions WHERE code = ?", (code,)).fetchone()
        if ver_row:
            vid = ver_row[0]
            conn.execute("DELETE FROM bible_verses WHERE book_id IN (SELECT id FROM bible_books WHERE version_id = ?)", (vid,))
            conn.execute("DELETE FROM bible_books WHERE version_id = ?", (vid,))
            conn.execute("DELETE FROM bible_versions WHERE id = ?", (vid,))
            conn.commit()

    print(f"\n{'='*60}")
    print(f"Import: {name}")
    print(f"{'='*60}\n")

    data = download_bible(file_code)
    if not data:
        return

    # Create version
    conn.execute("INSERT INTO bible_versions (code, name, language) VALUES (?, ?, ?)", (code, name, lang))
    conn.commit()
    ver_id = conn.execute("SELECT id FROM bible_versions WHERE code = ?", (code,)).fetchone()[0]

    books_data = data.get("books", [])
    total_verses = 0
    imported_books = 0

    for book_data in books_data:
        eng_name = book_data["name"]

        # Skip deuterocanonical books
        if eng_name not in BOOK_MAP:
            continue

        book_num, fr_name, short, testament = BOOK_MAP[eng_name]

        conn.execute(
            "INSERT INTO bible_books (version_id, book_number, name, short_name, testament) "
            "VALUES (?, ?, ?, ?, ?)",
            (ver_id, book_num, fr_name, short, testament)
        )
        book_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        book_verses = 0
        for chapter_data in book_data.get("chapters", []):
            ch_num = chapter_data["chapter"]
            for verse_data in chapter_data.get("verses", []):
                text = verse_data["text"].strip()
                if text:
                    conn.execute(
                        "INSERT INTO bible_verses (book_id, chapter, verse, text) VALUES (?, ?, ?, ?)",
                        (book_id, ch_num, verse_data["verse"], text)
                    )
                    book_verses += 1

        total_verses += book_verses
        imported_books += 1
        print(f"  [{book_num:2d}/66] {fr_name:<25s} {len(book_data['chapters']):3d} ch. | {book_verses:5d} versets")

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"TERMINÉ: {imported_books} livres, {total_verses} versets importés")
    print(f"Version: {code} - {name}")
    print(f"{'='*60}\n")


def main():
    args = sys.argv[1:]

    if "--download" in args or "--all" in args:
        # Import all versions
        for file_code in VERSIONS:
            import_bible(file_code, force="--force" in args)
    elif "--version" in args:
        idx = args.index("--version")
        if idx + 1 < len(args):
            import_bible(args[idx + 1], force="--force" in args)
        else:
            print("Usage: --version FreCrampon")
    else:
        # Default: import Crampon (closest to LSG style)
        import_bible("FreCrampon", force="--force" in args)


if __name__ == "__main__":
    main()
