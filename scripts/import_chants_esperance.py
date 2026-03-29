"""Import des Chants d'Espérance dans la BDD.

Les Chants d'Espérance sont organisés en 14 parties :
  1. Culte et Adoration
  2. La Parole de Dieu
  3. La Trinité - Dieu le Père
  4. Jésus-Christ
  5. Le Saint-Esprit
  6. L'Évangile - Appel et Repentance
  7. La Vie Chrétienne
  8. L'Église
  9. Le Foyer Chrétien
  10. La Jeunesse
  11. Cantiques pour Enfants
  12. Occasions Spéciales
  13. Le Ciel et le Retour de Christ
  14. Cantiques Divers

Usage:
    python scripts/import_chants_esperance.py                    # Import depuis fichier JSON local
    python scripts/import_chants_esperance.py --from-file ce.json  # Import depuis un fichier spécifique
    python scripts/import_chants_esperance.py --template         # Génère un template JSON à remplir

Le format JSON attendu:
[
  {
    "number": 1,
    "title": "Gloire à Dieu",
    "part": 1,
    "part_name": "Culte et Adoration",
    "author": "",
    "verses": [
      {"type": "verse", "label": "Couplet 1", "text": "Première ligne\\nDeuxième ligne"},
      {"type": "chorus", "label": "Refrain", "text": "Refrain ligne 1\\nRefrain ligne 2"}
    ]
  }
]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db.models import init_db, get_db

# ── Les 14 parties des Chants d'Espérance ──

CE_PARTS = {
    1: "Culte et Adoration",
    2: "La Parole de Dieu",
    3: "La Trinité - Dieu le Père",
    4: "Jésus-Christ",
    5: "Le Saint-Esprit",
    6: "L'Évangile - Appel et Repentance",
    7: "La Vie Chrétienne",
    8: "L'Église",
    9: "Le Foyer Chrétien",
    10: "La Jeunesse",
    11: "Cantiques pour Enfants",
    12: "Occasions Spéciales",
    13: "Le Ciel et le Retour de Christ",
    14: "Cantiques Divers",
}

# Plages de numéros approximatives par partie
CE_RANGES = {
    1: (1, 60),
    2: (61, 90),
    3: (91, 130),
    4: (131, 220),
    5: (221, 250),
    6: (251, 310),
    7: (311, 420),
    8: (421, 460),
    9: (461, 490),
    10: (491, 520),
    11: (521, 560),
    12: (561, 620),
    13: (621, 680),
    14: (681, 800),
}


def get_part_for_number(num: int) -> tuple[int, str]:
    """Détermine la partie d'un chant selon son numéro."""
    for part, (start, end) in CE_RANGES.items():
        if start <= num <= end:
            return part, CE_PARTS[part]
    return 14, CE_PARTS[14]


def generate_template():
    """Génère un fichier template JSON pour faciliter la saisie."""
    template = []
    for part_num, part_name in CE_PARTS.items():
        start, end = CE_RANGES[part_num]
        template.append({
            "number": start,
            "title": f"[Titre du chant #{start}]",
            "part": part_num,
            "part_name": part_name,
            "author": "",
            "verses": [
                {"type": "verse", "label": "Couplet 1", "text": "[Paroles couplet 1]"},
                {"type": "chorus", "label": "Refrain", "text": "[Paroles refrain]"},
                {"type": "verse", "label": "Couplet 2", "text": "[Paroles couplet 2]"},
            ]
        })

    out = Path(__file__).parent.parent / "data" / "chants_esperance_template.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
    print(f"Template généré: {out}")
    print(f"Remplissez-le avec les paroles, puis lancez:")
    print(f"  python scripts/import_chants_esperance.py --from-file data/chants_esperance_template.json")


def import_from_file(filepath: str, songbook_code: str = "CEF", force: bool = False):
    """Importe les chants depuis un fichier JSON."""
    init_db()
    conn = get_db()

    path = Path(filepath)
    if not path.exists():
        print(f"Fichier introuvable: {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        songs = json.load(f)

    if not isinstance(songs, list):
        print("Le fichier doit contenir une liste JSON de chants.")
        return

    # Get songbook ID
    sb = conn.execute("SELECT id FROM songbooks WHERE code = ?", (songbook_code,)).fetchone()
    if not sb:
        print(f"Recueil '{songbook_code}' introuvable en BDD.")
        conn.close()
        return
    sb_id = sb[0]

    if force:
        # Delete existing songs from this songbook
        existing_ids = [r[0] for r in conn.execute(
            "SELECT id FROM songs WHERE songbook_id = ?", (sb_id,)).fetchall()]
        for sid in existing_ids:
            conn.execute("DELETE FROM song_verses WHERE song_id = ?", (sid,))
        conn.execute("DELETE FROM songs WHERE songbook_id = ?", (sb_id,))
        conn.commit()
        print(f"Anciens chants supprimés du recueil {songbook_code}.")

    total = 0
    parts_count = {}

    for song_data in songs:
        num = song_data.get("number")
        title = song_data.get("title", "")
        author = song_data.get("author", "")
        part = song_data.get("part", 0)
        part_name = song_data.get("part_name", "")

        if not part and num:
            part, part_name = get_part_for_number(num)

        key_sig = song_data.get("key_signature", "")
        tempo = song_data.get("tempo", 0)

        # Insert song
        conn.execute(
            "INSERT INTO songs (songbook_id, number, title, author, key_signature, tempo) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sb_id, num, title, author, key_sig, tempo)
        )
        song_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert verses
        for i, v in enumerate(song_data.get("verses", [])):
            conn.execute(
                "INSERT INTO song_verses (song_id, verse_order, verse_type, verse_label, text) "
                "VALUES (?, ?, ?, ?, ?)",
                (song_id, i, v.get("type", "verse"), v.get("label", ""), v.get("text", ""))
            )

        total += 1
        parts_count[part] = parts_count.get(part, 0) + 1

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"Import terminé: {total} chants importés dans {songbook_code}")
    print(f"{'='*60}")
    for p in sorted(parts_count.keys()):
        pname = CE_PARTS.get(p, "?")
        print(f"  Partie {p:2d}: {pname:<40s} {parts_count[p]:4d} chants")
    print()


def import_from_text_files(directory: str, songbook_code: str = "CEF", force: bool = False):
    """Importe depuis un dossier de fichiers texte.

    Structure attendue:
        directory/
            001 - Gloire à Dieu.txt
            002 - Louange éternelle.txt
            ...

    Format de chaque fichier:
        [Couplet 1]
        Première ligne
        Deuxième ligne

        [Refrain]
        Ligne refrain

        [Couplet 2]
        ...
    """
    init_db()
    conn = get_db()

    dirpath = Path(directory)
    if not dirpath.exists():
        print(f"Dossier introuvable: {dirpath}")
        return

    sb = conn.execute("SELECT id FROM songbooks WHERE code = ?", (songbook_code,)).fetchone()
    if not sb:
        print(f"Recueil '{songbook_code}' introuvable.")
        conn.close()
        return
    sb_id = sb[0]

    if force:
        existing_ids = [r[0] for r in conn.execute(
            "SELECT id FROM songs WHERE songbook_id = ?", (sb_id,)).fetchall()]
        for sid in existing_ids:
            conn.execute("DELETE FROM song_verses WHERE song_id = ?", (sid,))
        conn.execute("DELETE FROM songs WHERE songbook_id = ?", (sb_id,))
        conn.commit()

    files = sorted(dirpath.glob("*.txt"))
    total = 0

    for filepath in files:
        filename = filepath.stem  # "001 - Gloire à Dieu"
        parts = filename.split(" - ", 1)
        try:
            num = int(parts[0].strip())
        except ValueError:
            num = None
        title = parts[1].strip() if len(parts) > 1 else filename

        # Parse verses
        content = filepath.read_text(encoding="utf-8")
        verses = _parse_verses(content)

        part, part_name = get_part_for_number(num) if num else (14, CE_PARTS[14])

        conn.execute(
            "INSERT INTO songs (songbook_id, number, title, author, key_signature, tempo) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sb_id, num, title, "", "", 0)
        )
        song_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for i, v in enumerate(verses):
            conn.execute(
                "INSERT INTO song_verses (song_id, verse_order, verse_type, verse_label, text) "
                "VALUES (?, ?, ?, ?, ?)",
                (song_id, i, v["type"], v["label"], v["text"])
            )

        total += 1
        print(f"  #{num or '?':>3} {title}")

    conn.commit()
    conn.close()
    print(f"\n{total} chants importés.")


def _parse_verses(text: str) -> list[dict]:
    """Parse un texte en couplets/refrains."""
    verses = []
    current_label = ""
    current_type = "verse"
    current_lines = []

    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("[") and "]" in line:
            # Save previous
            if current_lines:
                verses.append({
                    "type": current_type,
                    "label": current_label,
                    "text": "\n".join(current_lines),
                })
                current_lines = []
            current_label = line.strip("[]")
            current_type = "chorus" if "refrain" in current_label.lower() else "verse"
        elif line == "" and current_lines:
            # Empty line = end of section (if no brackets used)
            pass
        elif line:
            current_lines.append(line)

    if current_lines:
        verses.append({
            "type": current_type,
            "label": current_label,
            "text": "\n".join(current_lines),
        })

    return verses


def main():
    args = sys.argv[1:]

    if "--template" in args:
        generate_template()
    elif "--from-file" in args:
        idx = args.index("--from-file")
        filepath = args[idx + 1] if idx + 1 < len(args) else ""
        songbook = "CEF"
        if "--songbook" in args:
            si = args.index("--songbook")
            songbook = args[si + 1]
        import_from_file(filepath, songbook, force="--force" in args)
    elif "--from-dir" in args:
        idx = args.index("--from-dir")
        dirpath = args[idx + 1] if idx + 1 < len(args) else ""
        songbook = "CEF"
        if "--songbook" in args:
            si = args.index("--songbook")
            songbook = args[si + 1]
        import_from_text_files(dirpath, songbook, force="--force" in args)
    else:
        # Default: check for data/chants_esperance.json
        default_file = Path(__file__).parent.parent / "data" / "chants_esperance.json"
        if default_file.exists():
            import_from_file(str(default_file), force="--force" in args)
        else:
            print("Aucun fichier de chants trouvé.")
            print()
            print("Options:")
            print("  --template                        Génère un template JSON à remplir")
            print("  --from-file chemin/fichier.json   Importe depuis un fichier JSON")
            print("  --from-dir chemin/dossier/        Importe depuis des fichiers .txt")
            print("  --songbook CEF|CEC|CARL|MEL_FR|MEL_CR    Recueil cible (défaut: CEF)")
            print("  --force                           Écrase les chants existants")
            print()
            print("Structure des fichiers .txt:")
            print("  Nom: '001 - Gloire à Dieu.txt'")
            print("  Contenu:")
            print("    [Couplet 1]")
            print("    Première ligne")
            print("    Deuxième ligne")
            print("    ")
            print("    [Refrain]")
            print("    Ligne refrain")


if __name__ == "__main__":
    main()
