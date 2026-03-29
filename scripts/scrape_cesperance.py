"""Scrape les Chants d'Espérance depuis cesperance.com.

Usage: python scripts/scrape_cesperance.py

Récupère la liste de tous les chants puis télécharge les paroles de chacun.
Sauvegarde dans data/ce_full_francais.json et data/ce_full_creole.json.
"""

import json
import re
import sys
import ssl
import time
import urllib.request
from pathlib import Path
from html.parser import HTMLParser

sys.path.insert(0, str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

BASE = "https://cesperance.com"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def fetch(url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/json",
                "Accept-Language": "fr-FR,fr;q=0.9",
            })
            resp = urllib.request.urlopen(req, timeout=20, context=ctx)
            return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                print(f"  ERREUR fetch {url}: {e}")
                return ""


def extract_song_links(html: str, book_slug: str) -> list[dict]:
    """Extrait les liens vers les chants depuis la page du recueil."""
    songs = []
    # Pattern: /book/chant-desperance/song/slug avec titre
    pattern = rf'/book/{re.escape(book_slug)}/song/([\w-]+)'

    # Find all song links with their context
    # Look for Next.js data or HTML links
    for match in re.finditer(pattern, html):
        slug = match.group(1)
        if slug not in [s["slug"] for s in songs]:
            songs.append({"slug": slug})

    # Try to extract numbers and titles from HTML context
    # Pattern: number and title near the link
    link_pattern = rf'<a[^>]*href="[^"]*?/book/{re.escape(book_slug)}/song/([\w-]+)"[^>]*>(.*?)</a>'
    for match in re.finditer(link_pattern, html, re.DOTALL):
        slug = match.group(1)
        content = re.sub(r'<[^>]+>', ' ', match.group(2)).strip()
        # Find existing entry
        for s in songs:
            if s["slug"] == slug and "title" not in s:
                # Try to extract number and title
                num_match = re.match(r'(\d+)\s*(.*)', content)
                if num_match:
                    s["number"] = int(num_match.group(1))
                    s["title"] = num_match.group(2).strip()
                else:
                    s["title"] = content

    # Also try extracting from Next.js JSON data
    # Look for patterns like "number":3,"title":"Adorons le Père"
    for match in re.finditer(r'"number"\s*:\s*(\d+)\s*,\s*"title"\s*:\s*"([^"]+)"', html):
        num = int(match.group(1))
        title = match.group(2)
        # Check if we have this song
        found = False
        for s in songs:
            if s.get("number") == num:
                s["title"] = title
                found = True
                break
        if not found:
            songs.append({"number": num, "title": title, "slug": ""})

    # Extract from visible text patterns: "0 Crions à Dieu"
    for match in re.finditer(r'>(\d+)\s*[-–.]?\s*([^<]{3,60})<', html):
        num = int(match.group(1))
        title = match.group(2).strip()
        if num < 1000 and len(title) > 2:
            found = False
            for s in songs:
                if s.get("number") == num:
                    if "title" not in s or not s["title"]:
                        s["title"] = title
                    found = True
                    break

    return songs


def extract_lyrics(html: str) -> tuple[str, list[dict]]:
    """Extrait les paroles d'une page de chant."""
    title = ""
    verses = []

    # Try to get title
    title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
    if title_match:
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

    # Look for verse blocks - they're usually in div/p/section elements
    # Pattern 1: verses separated by sections with headers
    # Pattern 2: numbered paragraphs
    # Pattern 3: raw text blocks

    # Try to find all text blocks that look like lyrics
    # Remove HTML tags but keep structure
    text_blocks = re.findall(r'<(?:p|div|section)[^>]*class="[^"]*(?:verse|lyric|stanza|couplet|refrain|chorus)[^"]*"[^>]*>(.*?)</(?:p|div|section)>', html, re.DOTALL | re.IGNORECASE)

    if not text_blocks:
        # Try simpler approach - find content between verse markers
        text_blocks = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)

    verse_idx = 0
    for block in text_blocks:
        clean = re.sub(r'<br\s*/?>', '\n', block)
        clean = re.sub(r'<[^>]+>', '', clean)
        clean = clean.strip()

        if len(clean) > 10:  # Skip very short blocks
            lower = clean.split('\n')[0].lower()
            if 'refrain' in lower or 'chorus' in lower:
                lines = clean.split('\n')
                text = '\n'.join(lines[1:]).strip() if len(lines) > 1 else clean
                verses.append({"type": "chorus", "label": "Refrain", "text": text})
            else:
                verse_idx += 1
                verses.append({"type": "verse", "label": f"Couplet {verse_idx}", "text": clean})

    return title, verses


def scrape_book(book_slug: str, songbook_code: str):
    """Scrape un recueil complet."""
    print(f"\n{'='*60}")
    print(f"Scraping: {book_slug} -> {songbook_code}")
    print(f"{'='*60}\n")

    # Get song list
    print("Récupération de la liste des chants...")
    html = fetch(f"{BASE}/book/{book_slug}")
    if not html:
        print("Impossible de récupérer la page du recueil.")
        return []

    songs = extract_song_links(html, book_slug)
    print(f"Chants trouvés: {len(songs)}")

    # Fetch each song
    all_songs = []
    for i, song_info in enumerate(songs):
        slug = song_info.get("slug", "")
        if not slug:
            continue

        print(f"  [{i+1}/{len(songs)}] {slug}...", end=" ", flush=True)
        song_html = fetch(f"{BASE}/book/{book_slug}/song/{slug}")

        if song_html:
            title, verses = extract_lyrics(song_html)
            if not title:
                title = song_info.get("title", slug.replace("-", " ").title())

            song_data = {
                "number": song_info.get("number", i),
                "title": title,
                "slug": slug,
                "verses": verses,
            }
            all_songs.append(song_data)
            print(f"{title} ({len(verses)} sections)")
        else:
            print("ERREUR")

        time.sleep(0.5)  # Rate limiting

    # Save
    outfile = DATA_DIR / f"{songbook_code.lower()}_full.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(all_songs, f, ensure_ascii=False, indent=2)
    print(f"\nSauvegardé: {outfile} ({len(all_songs)} chants)")

    return all_songs


def import_to_db(songs: list[dict], songbook_code: str):
    """Importe les chants scrapés dans la BDD."""
    from core.db.models import init_db, get_db

    init_db()
    conn = get_db()

    sb = conn.execute("SELECT id FROM songbooks WHERE code = ?", (songbook_code,)).fetchone()
    if not sb:
        print(f"Recueil {songbook_code} introuvable en BDD.")
        return
    sb_id = sb[0]

    # Remove existing songs from this songbook
    existing = conn.execute("SELECT id FROM songs WHERE songbook_id = ?", (sb_id,)).fetchall()
    for row in existing:
        conn.execute("DELETE FROM song_verses WHERE song_id = ?", (row[0],))
    conn.execute("DELETE FROM songs WHERE songbook_id = ?", (sb_id,))
    conn.commit()

    count = 0
    for song in songs:
        if not song.get("verses"):
            continue

        conn.execute(
            "INSERT INTO songs (songbook_id, number, title, author) VALUES (?, ?, ?, ?)",
            (sb_id, song.get("number"), song["title"], "")
        )
        song_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for i, v in enumerate(song["verses"]):
            conn.execute(
                "INSERT INTO song_verses (song_id, verse_order, verse_type, verse_label, text) VALUES (?, ?, ?, ?, ?)",
                (song_id, i, v["type"], v["label"], v["text"])
            )
        count += 1

    conn.commit()
    conn.close()
    print(f"Importé {count} chants dans {songbook_code}")


def main():
    books = {
        "chant-desperance": "CEF",
        # "echos-des-elus": "CEC",  # Can add more
    }

    if "--import" in sys.argv:
        # Import from existing JSON files
        for book_slug, code in books.items():
            fpath = DATA_DIR / f"{code.lower()}_full.json"
            if fpath.exists():
                with open(fpath, "r", encoding="utf-8") as f:
                    songs = json.load(f)
                import_to_db(songs, code)
            else:
                print(f"Fichier {fpath} introuvable. Lancez d'abord sans --import.")
        return

    for book_slug, code in books.items():
        songs = scrape_book(book_slug, code)
        if songs and "--no-import" not in sys.argv:
            import_to_db(songs, code)


if __name__ == "__main__":
    main()
