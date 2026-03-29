"""Modèles de base de données SQLite pour EBJFL-Broadcast."""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "ebjfl.db"


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA encoding='UTF-8'")
    return conn


def init_db():
    """Crée toutes les tables si elles n'existent pas."""
    conn = get_db()
    conn.executescript("""
        -- === BIBLE (VideoPsalm) ===
        CREATE TABLE IF NOT EXISTS bible_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,       -- LSG, KJV, CREOLE
            name TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'fr'
        );

        CREATE TABLE IF NOT EXISTS bible_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL REFERENCES bible_versions(id),
            book_number INTEGER NOT NULL,
            name TEXT NOT NULL,
            short_name TEXT NOT NULL,
            testament TEXT NOT NULL CHECK(testament IN ('AT', 'NT'))
        );

        CREATE TABLE IF NOT EXISTS bible_verses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL REFERENCES bible_books(id),
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            text TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_verses_ref ON bible_verses(book_id, chapter, verse);

        -- === CHANTS (Hymnes + Contemporains) ===
        CREATE TABLE IF NOT EXISTS songbooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,       -- CE_FR, CE_CR, CONTEMP
            name TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'fr'
        );

        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            songbook_id INTEGER NOT NULL REFERENCES songbooks(id),
            number INTEGER,                  -- numéro dans le recueil (ex: CE 145)
            title TEXT NOT NULL,
            author TEXT DEFAULT '',
            key_signature TEXT DEFAULT '',    -- tonalité (Do, Ré...)
            tempo INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS song_verses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL REFERENCES songs(id),
            verse_order INTEGER NOT NULL,    -- ordre d'affichage
            verse_type TEXT NOT NULL DEFAULT 'verse',  -- verse, chorus, bridge, intro
            verse_label TEXT DEFAULT '',      -- "Couplet 1", "Refrain"
            text TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_song_verses ON song_verses(song_id, verse_order);

        -- === LOWER THIRDS ===
        CREATE TABLE IF NOT EXISTS lower_thirds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            title TEXT DEFAULT '',
            subtitle TEXT DEFAULT '',
            social TEXT DEFAULT '',           -- @handle ou lien
            photo_path TEXT DEFAULT '',
            category TEXT DEFAULT 'general',  -- pasteur, diacre, invite, musicien
            is_favorite INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- === PLANNING / SERVICE ===
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            theme TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS service_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
            item_order INTEGER NOT NULL,
            item_type TEXT NOT NULL,          -- song, bible, lower_third, text, media, announcement
            reference_id INTEGER,            -- ID dans la table source (songs.id, lower_thirds.id...)
            custom_text TEXT DEFAULT '',      -- texte libre si pas de référence
            custom_title TEXT DEFAULT '',
            duration_seconds INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'pending'     -- pending, active, done
        );
        CREATE INDEX IF NOT EXISTS idx_service_items ON service_items(service_id, item_order);

        -- === VIRTUAL SCREENS ===
        CREATE TABLE IF NOT EXISTS virtual_screens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            width INTEGER DEFAULT 1920,
            height INTEGER DEFAULT 1080,
            bg_color TEXT DEFAULT '#000000',
            bg_image TEXT DEFAULT '',
            theme TEXT DEFAULT 'default',
            is_active INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS screen_layers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            screen_id INTEGER NOT NULL REFERENCES virtual_screens(id) ON DELETE CASCADE,
            layer_order INTEGER NOT NULL,
            layer_type TEXT NOT NULL,         -- text, image, shape, ticker, clock
            x INTEGER DEFAULT 0,
            y INTEGER DEFAULT 0,
            width INTEGER DEFAULT 400,
            height INTEGER DEFAULT 100,
            properties TEXT DEFAULT '{}',     -- JSON: font, color, animation, etc.
            visible INTEGER DEFAULT 1
        );

        -- === TEXTES LIBRES / ANNONCES ===
        CREATE TABLE IF NOT EXISTS custom_texts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'announcement', -- announcement, prayer, quote
            style TEXT DEFAULT '{}'           -- JSON: font, size, color, animation
        );

        -- === THEMES VISUELS ===
        CREATE TABLE IF NOT EXISTS themes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'culte',    -- culte, mariage, conference, funerailles
            bg_color TEXT DEFAULT '#1e1e2e',
            accent_color TEXT DEFAULT '#89b4fa',
            text_color TEXT DEFAULT '#ffffff',
            font_family TEXT DEFAULT 'Segoe UI',
            font_size_title INTEGER DEFAULT 48,
            font_size_body INTEGER DEFAULT 32,
            overlay_opacity REAL DEFAULT 0.85,
            custom_css TEXT DEFAULT ''
        );
        -- === USERS & AUTH ===
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            pin TEXT DEFAULT '',              -- PIN rapide pour tablettes (hashé)
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'guest' CHECK(role IN ('admin', 'operator', 'presenter', 'guest')),
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );
    """)
    conn.commit()

    # Insert default themes (only if empty)
    if conn.execute("SELECT COUNT(*) FROM themes").fetchone()[0] == 0:
        conn.execute("""
            INSERT INTO themes (name, category, bg_color, accent_color, text_color) VALUES
                ('Culte Dominical', 'culte', '#1a1a2e', '#89b4fa', '#ffffff'),
                ('Mariage', 'mariage', '#1a1a2e', '#f5c6aa', '#ffffff'),
                ('Conférence', 'conference', '#0f0f1a', '#a6e3a1', '#ffffff'),
                ('Funérailles', 'funerailles', '#111111', '#9399b2', '#cdd6f4')
        """)
        conn.commit()

    # Insert default songbooks (only if empty)
    if conn.execute("SELECT COUNT(*) FROM songbooks").fetchone()[0] == 0:
        conn.execute("""
            INSERT INTO songbooks (code, name, language) VALUES
                ('CEF', 'Chants d''Espérance (Français)', 'fr'),
                ('CEC', 'Chants d''Espérance (Créole)', 'ht'),
                ('CARL', 'Chante akk Radio Lumière', 'ht'),
                ('MEL_FR', 'Mélodie (Français)', 'fr'),
                ('MEL_CR', 'Mélodie (Créole)', 'ht')
        """)
        conn.commit()

    # Insert default admin user (only if no users)
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        import hashlib
        users_default = [
            ("sironel", "Sironel", "phigando", "1234", "admin"),
            ("admin", "Administrateur", "admin", "0000", "admin"),
        ]
        for uname, dname, pwd, pin, role in users_default:
            pwd_hash = hashlib.sha256(pwd.encode()).hexdigest()
            pin_hash = hashlib.sha256(pin.encode()).hexdigest()
            conn.execute(
                "INSERT INTO users (username, display_name, password_hash, pin, role) VALUES (?, ?, ?, ?, ?)",
                (uname, dname, pwd_hash, pin_hash, role))
        conn.commit()

    conn.close()
