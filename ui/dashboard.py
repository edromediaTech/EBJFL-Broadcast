"""Dashboard PyQt6 - Interface tout-en-un EBJFL-Broadcast.

Regroupe : Projection (VideoPsalm), Lower Thirds, Sous-titrage chants,
Virtual Screen Creator, Planning du service.
100% offline-first.
"""

import sys
import json
import threading

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QLineEdit, QTextEdit, QTabWidget,
    QListWidget, QListWidgetItem, QComboBox, QSpinBox, QSplitter,
    QStatusBar, QToolBar, QMessageBox, QPlainTextEdit,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QAction, QIcon, QPixmap

from core.obs_bridge import obs_bridge
from core.config import config
from pathlib import Path

LOGO_PATH = str(Path(__file__).parent.parent / "assets" / "logo.png")

API = f"http://localhost:{config.server.port}"


def _post(path, **kwargs):
    import requests
    try:
        return requests.post(f"{API}{path}", **kwargs, timeout=3).json()
    except Exception as e:
        return {"error": str(e)}


def _get(path, **params):
    import requests
    try:
        return requests.get(f"{API}{path}", params=params, timeout=3).json()
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════
#  Style global
# ══════════════════════════════════════

DARK_STYLE = """
QMainWindow, QWidget { background: #1e1e2e; color: #cdd6f4; }
QTabWidget::pane { border: 1px solid #45475a; border-radius: 4px; }
QTabBar::tab {
    background: #313244; color: #a6adc8; padding: 8px 20px;
    border: 1px solid #45475a; border-bottom: none; border-radius: 4px 4px 0 0;
    margin-right: 2px;
}
QTabBar::tab:selected { background: #1e1e2e; color: #89b4fa; font-weight: bold; }
QGroupBox {
    color: #89b4fa; font-weight: bold; border: 1px solid #45475a;
    border-radius: 6px; margin-top: 8px; padding-top: 18px;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; }
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox {
    background: #313244; color: #cdd6f4; border: 1px solid #45475a;
    border-radius: 4px; padding: 5px 8px;
}
QListWidget {
    background: #181825; color: #cdd6f4; border: 1px solid #45475a;
    border-radius: 4px; outline: none;
}
QListWidget::item { padding: 6px; border-bottom: 1px solid #313244; }
QListWidget::item:selected { background: #45475a; color: #89b4fa; }
QPushButton {
    background: #89b4fa; color: #1e1e2e; border: none;
    border-radius: 4px; padding: 8px 16px; font-weight: bold;
}
QPushButton:hover { background: #b4d0fb; }
QPushButton:disabled { background: #45475a; color: #6c7086; }
QPushButton[class="danger"] { background: #f38ba8; }
QPushButton[class="success"] { background: #a6e3a1; }
QPushButton[class="warning"] { background: #fab387; }
QPushButton[class="secondary"] { background: #45475a; color: #cdd6f4; }
QStatusBar { background: #181825; color: #a6adc8; border-top: 1px solid #45475a; }
QSplitter::handle { background: #45475a; }
QToolBar { background: #181825; border-bottom: 1px solid #45475a; spacing: 4px; }
"""


# ══════════════════════════════════════
#  Tab: Connexion & Status
# ══════════════════════════════════════

class StatusTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # OBS Config
        obs_group = QGroupBox("Connexion OBS Studio")
        obs_layout = QVBoxLayout()

        row = QHBoxLayout()
        row.addWidget(QLabel("Hôte:"))
        self.obs_host = QLineEdit(config.obs.host)
        row.addWidget(self.obs_host)
        row.addWidget(QLabel("Port:"))
        self.obs_port = QLineEdit(str(config.obs.port))
        self.obs_port.setMaximumWidth(80)
        row.addWidget(self.obs_port)
        row.addWidget(QLabel("Mot de passe:"))
        self.obs_pass = QLineEdit(config.obs.password)
        self.obs_pass.setEchoMode(QLineEdit.EchoMode.Password)
        row.addWidget(self.obs_pass)
        obs_layout.addLayout(row)

        btn_row = QHBoxLayout()
        btn_connect = QPushButton("Connecter")
        btn_connect.clicked.connect(self.connect_obs)
        btn_row.addWidget(btn_connect)
        btn_disconnect = QPushButton("Déconnecter")
        btn_disconnect.setProperty("class", "secondary")
        btn_disconnect.clicked.connect(self.disconnect_obs)
        btn_row.addWidget(btn_disconnect)
        obs_layout.addLayout(btn_row)

        self.obs_label = QLabel("Statut: Non connecté")
        obs_layout.addWidget(self.obs_label)
        obs_group.setLayout(obs_layout)
        layout.addWidget(obs_group)

        # Server info
        srv_group = QGroupBox("Serveur API")
        srv_layout = QVBoxLayout()
        self.srv_label = QLabel(f"En écoute sur http://0.0.0.0:{config.server.port}")
        srv_layout.addWidget(self.srv_label)
        self.clients_label = QLabel("Clients connectés: 0")
        srv_layout.addWidget(self.clients_label)
        srv_layout.addWidget(QLabel(f"\nOverlay OBS: http://localhost:{config.server.port}/overlays/overlay.html"))
        srv_group.setLayout(srv_layout)
        layout.addWidget(srv_group)

        # Log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(200)
        self.log.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log)
        layout.addStretch()

    def connect_obs(self):
        config.obs.host = self.obs_host.text()
        config.obs.port = int(self.obs_port.text() or "4455")
        config.obs.password = self.obs_pass.text()
        ok = obs_bridge.connect()
        if ok:
            v = obs_bridge.get_version() or "?"
            self.obs_label.setText(f"Statut: Connecté (OBS v{v})")
            self.log.append(f"Connecté à OBS v{v}")
        else:
            self.obs_label.setText(f"Statut: Erreur - {obs_bridge.error}")
            self.log.append(f"Erreur: {obs_bridge.error}")

    def disconnect_obs(self):
        obs_bridge.disconnect()
        self.obs_label.setText("Statut: Non connecté")

    def refresh(self):
        status = _get("/status")
        n = status.get("clients_connected", 0)
        self.clients_label.setText(f"Clients connectés: {n}")


# ══════════════════════════════════════
#  Tab: Projection (VideoPsalm)
# ══════════════════════════════════════

class ProjectionTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # Bible projection
        bible_group = QGroupBox("Projection Bible")
        bl = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Référence:"))
        self.bible_ref = QLineEdit()
        self.bible_ref.setPlaceholderText("Ex: Jean 3:16 ou Psaume 23:1-6")
        row1.addWidget(self.bible_ref)
        self.bible_version = QComboBox()
        self.bible_version.addItems(["LSG", "KJV", "CREOLE"])
        row1.addWidget(self.bible_version)
        bl.addLayout(row1)

        self.bible_text = QPlainTextEdit()
        self.bible_text.setPlaceholderText("Le texte du verset apparaîtra ici...")
        self.bible_text.setMaximumHeight(100)
        bl.addWidget(self.bible_text)

        row2 = QHBoxLayout()
        btn_search = QPushButton("Chercher")
        btn_search.clicked.connect(self.search_bible)
        row2.addWidget(btn_search)
        btn_project = QPushButton("Projeter")
        btn_project.setProperty("class", "success")
        btn_project.clicked.connect(self.project_bible)
        row2.addWidget(btn_project)
        bl.addLayout(row2)
        bible_group.setLayout(bl)
        layout.addWidget(bible_group)

        # Texte libre
        text_group = QGroupBox("Projection Texte Libre")
        tl = QVBoxLayout()
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Titre:"))
        self.text_title = QLineEdit()
        row3.addWidget(self.text_title)
        tl.addLayout(row3)
        self.text_content = QPlainTextEdit()
        self.text_content.setPlaceholderText("Saisissez le texte à projeter...")
        self.text_content.setMaximumHeight(120)
        tl.addWidget(self.text_content)

        row4 = QHBoxLayout()
        self.text_anim = QComboBox()
        self.text_anim.addItems(["fade", "slide-up", "slide-left", "none"])
        row4.addWidget(QLabel("Animation:"))
        row4.addWidget(self.text_anim)
        btn_proj_text = QPushButton("Projeter Texte")
        btn_proj_text.setProperty("class", "success")
        btn_proj_text.clicked.connect(self.project_text)
        row4.addWidget(btn_proj_text)
        tl.addLayout(row4)
        text_group.setLayout(tl)
        layout.addWidget(text_group)

        # Controls
        ctrl = QHBoxLayout()
        btn_blank = QPushButton("ÉCRAN NOIR")
        btn_blank.setProperty("class", "danger")
        btn_blank.clicked.connect(lambda: _post("/projection/blank"))
        ctrl.addWidget(btn_blank)
        layout.addLayout(ctrl)
        layout.addStretch()

    def search_bible(self):
        q = self.bible_ref.text()
        ver = self.bible_version.currentText()
        res = _get("/bible/search", q=q, version=ver)
        results = res.get("results", [])
        if results:
            text = "\n".join(f"{r['short_name']} {r['chapter']}:{r['verse']} - {r['text']}" for r in results[:5])
            self.bible_text.setPlainText(text)
        else:
            self.bible_text.setPlainText("Aucun résultat. (Importez d'abord une Bible)")

    def project_bible(self):
        _post("/projection/bible", json={
            "text": self.bible_text.toPlainText(),
            "reference": self.bible_ref.text(),
            "version": self.bible_version.currentText(),
        })

    def project_text(self):
        _post("/projection/text", json={
            "title": self.text_title.text(),
            "text": self.text_content.toPlainText(),
            "animation": self.text_anim.currentText(),
        })


# ══════════════════════════════════════
#  Tab: Chants & Sous-titrage
# ══════════════════════════════════════

class SongsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Song list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher un chant (titre ou numéro)...")
        self.search.textChanged.connect(self.load_songs)
        search_row.addWidget(self.search)
        self.songbook = QComboBox()
        self.songbook.addItems(["Tous", "CEF", "CEC", "CARL", "MEL_FR", "MEL_CR"])
        self.songbook.currentIndexChanged.connect(self.load_songs)
        search_row.addWidget(self.songbook)
        ll.addLayout(search_row)

        self.song_list = QListWidget()
        self.song_list.itemClicked.connect(self.select_song)
        ll.addWidget(self.song_list)

        btn_add = QPushButton("+ Ajouter un chant")
        btn_add.clicked.connect(self.add_song_dialog)
        ll.addWidget(btn_add)

        # Right: Song detail + projection
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        self.song_title_label = QLabel("Sélectionnez un chant")
        self.song_title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        rl.addWidget(self.song_title_label)

        self.verse_list = QListWidget()
        self.verse_list.itemClicked.connect(self.select_verse)
        rl.addWidget(self.verse_list)

        self.verse_preview = QPlainTextEdit()
        self.verse_preview.setReadOnly(True)
        self.verse_preview.setMaximumHeight(150)
        rl.addWidget(self.verse_preview)

        # Projection controls
        ctrl = QHBoxLayout()
        btn_proj = QPushButton("Projeter ce chant")
        btn_proj.setProperty("class", "success")
        btn_proj.clicked.connect(self.project_song)
        ctrl.addWidget(btn_proj)

        btn_prev = QPushButton("< Précédent")
        btn_prev.clicked.connect(lambda: _post("/projection/song/prev"))
        ctrl.addWidget(btn_prev)

        btn_next = QPushButton("Suivant >")
        btn_next.clicked.connect(lambda: _post("/projection/song/next"))
        ctrl.addWidget(btn_next)

        btn_blank = QPushButton("Noir")
        btn_blank.setProperty("class", "danger")
        btn_blank.clicked.connect(lambda: _post("/projection/blank"))
        ctrl.addWidget(btn_blank)
        rl.addLayout(ctrl)

        # Subtitle controls
        sub_group = QGroupBox("Sous-titrage")
        sl = QHBoxLayout()
        btn_sub_start = QPushButton("Lancer sous-titres")
        btn_sub_start.clicked.connect(self.start_subtitles)
        sl.addWidget(btn_sub_start)
        btn_sub_next = QPushButton("Lignes suivantes")
        btn_sub_next.clicked.connect(lambda: _post("/subtitles/next"))
        sl.addWidget(btn_sub_next)
        btn_sub_prev = QPushButton("Lignes précédentes")
        btn_sub_prev.clicked.connect(lambda: _post("/subtitles/prev"))
        sl.addWidget(btn_sub_prev)
        btn_sub_hide = QPushButton("Masquer")
        btn_sub_hide.setProperty("class", "secondary")
        btn_sub_hide.clicked.connect(lambda: _post("/subtitles/hide"))
        sl.addWidget(btn_sub_hide)
        sub_group.setLayout(sl)
        rl.addWidget(sub_group)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([400, 600])
        layout.addWidget(splitter)

        self._current_song = None
        self._current_verse_idx = 0

    def load_songs(self):
        sb = self.songbook.currentText()
        if sb == "Tous":
            sb = ""
        songs = _get("/songs", songbook=sb, search=self.search.text())
        self.song_list.clear()
        if isinstance(songs, list):
            for s in songs:
                num = f"#{s['number']} " if s.get('number') else ""
                item = QListWidgetItem(f"{num}{s['title']}")
                item.setData(Qt.ItemDataRole.UserRole, s['id'])
                self.song_list.addItem(item)

    def select_song(self, item):
        song_id = item.data(Qt.ItemDataRole.UserRole)
        song = _get(f"/songs/{song_id}")
        if "error" in song:
            return
        self._current_song = song
        self.song_title_label.setText(f"{song.get('title', '')}")
        self.verse_list.clear()
        for v in song.get("verses", []):
            label = v.get("verse_label", "") or v.get("verse_type", "")
            vi = QListWidgetItem(f"{label}: {v['text'][:60]}...")
            vi.setData(Qt.ItemDataRole.UserRole, v)
            self.verse_list.addItem(vi)

    def select_verse(self, item):
        verse = item.data(Qt.ItemDataRole.UserRole)
        self.verse_preview.setPlainText(verse.get("text", ""))
        self._current_verse_idx = self.verse_list.row(item)

    def project_song(self):
        if self._current_song:
            _post("/projection/song", json={"song_id": self._current_song["id"]})

    def start_subtitles(self):
        if self._current_song and self._current_song.get("verses"):
            v = self._current_song["verses"][self._current_verse_idx]
            _post("/subtitles/load", json={
                "song_title": self._current_song["title"],
                "verse_label": v.get("verse_label", ""),
                "text": v["text"],
            })

    def add_song_dialog(self):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Ajouter un chant")
        dlg.setMinimumWidth(500)
        form = QFormLayout(dlg)

        sb_combo = QComboBox()
        sb_combo.addItems(["CEF", "CEC", "CARL", "MEL_FR", "MEL_CR"])
        form.addRow("Recueil:", sb_combo)

        num_spin = QSpinBox()
        num_spin.setRange(0, 9999)
        form.addRow("Numéro:", num_spin)

        title_input = QLineEdit()
        form.addRow("Titre:", title_input)

        author_input = QLineEdit()
        form.addRow("Auteur:", author_input)

        verses_input = QPlainTextEdit()
        verses_input.setPlaceholderText(
            "Séparez les couplets par une ligne vide.\n"
            "Commencez par [Refrain], [Couplet 1], etc.\n\n"
            "[Couplet 1]\nPremière ligne\nDeuxième ligne\n\n[Refrain]\nRefrain ici..."
        )
        form.addRow("Paroles:", verses_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec():
            # Parse verses
            raw = verses_input.toPlainText().strip()
            verses = []
            for block in raw.split("\n\n"):
                block = block.strip()
                if not block:
                    continue
                lines = block.split("\n")
                label = ""
                text_lines = lines
                if lines[0].startswith("[") and "]" in lines[0]:
                    label = lines[0].strip("[]")
                    text_lines = lines[1:]
                vtype = "chorus" if "refrain" in label.lower() else "verse"
                verses.append({
                    "type": vtype,
                    "label": label,
                    "text": "\n".join(text_lines),
                })

            _post("/songs", json={
                "songbook_code": sb_combo.currentText(),
                "number": num_spin.value() or None,
                "title": title_input.text(),
                "author": author_input.text(),
                "verses": verses,
            })
            self.load_songs()


# ══════════════════════════════════════
#  Tab: Lower Thirds
# ══════════════════════════════════════

class LowerThirdsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher...")
        self.search.returnPressed.connect(self.load_list)
        search_row.addWidget(self.search)
        self.cat_filter = QComboBox()
        self.cat_filter.addItems(["Tous", "pasteur", "diacre", "invite", "musicien", "general"])
        search_row.addWidget(self.cat_filter)
        btn_search = QPushButton("Filtrer")
        btn_search.clicked.connect(self.load_list)
        search_row.addWidget(btn_search)
        ll.addLayout(search_row)

        self.lt_list = QListWidget()
        self.lt_list.itemClicked.connect(self.select_lt)
        ll.addWidget(self.lt_list)

        # Right: form + preview
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        form_group = QGroupBox("Lower Third")
        fl = QVBoxLayout()

        for label, attr, placeholder in [
            ("Nom:", "lt_name", "Prénom NOM"),
            ("Titre:", "lt_title", "Pasteur / Diacre / Invité"),
            ("Sous-titre:", "lt_subtitle", "Église / Organisation"),
            ("Réseaux:", "lt_social", "@handle"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            inp = QLineEdit()
            inp.setPlaceholderText(placeholder)
            setattr(self, attr, inp)
            row.addWidget(inp)
            fl.addLayout(row)

        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("Catégorie:"))
        self.lt_category = QComboBox()
        self.lt_category.addItems(["general", "pasteur", "diacre", "invite", "musicien"])
        cat_row.addWidget(self.lt_category)
        fl.addLayout(cat_row)

        form_group.setLayout(fl)
        rl.addWidget(form_group)

        # Actions
        btn_row = QHBoxLayout()
        btn_save = QPushButton("Sauvegarder")
        btn_save.clicked.connect(self.save_lt)
        btn_row.addWidget(btn_save)

        btn_show = QPushButton("AFFICHER")
        btn_show.setProperty("class", "success")
        btn_show.clicked.connect(self.show_lt)
        btn_row.addWidget(btn_show)

        btn_hide = QPushButton("MASQUER")
        btn_hide.setProperty("class", "danger")
        btn_hide.clicked.connect(lambda: _post("/obs/lower-third/hide"))
        btn_row.addWidget(btn_hide)

        btn_delete = QPushButton("Supprimer")
        btn_delete.setProperty("class", "danger")
        btn_delete.clicked.connect(self.delete_lt)
        btn_row.addWidget(btn_delete)
        rl.addLayout(btn_row)
        rl.addStretch()

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([350, 500])
        layout.addWidget(splitter)

        self._current_id = None
        self.load_list()

    def load_list(self):
        cat = self.cat_filter.currentText()
        if cat == "Tous":
            cat = ""
        lts = _get("/lower-thirds", category=cat, search=self.search.text())
        self.lt_list.clear()
        if isinstance(lts, list):
            for lt in lts:
                item = QListWidgetItem(f"{lt['name']} - {lt['title']}")
                item.setData(Qt.ItemDataRole.UserRole, lt)
                self.lt_list.addItem(item)

    def select_lt(self, item):
        lt = item.data(Qt.ItemDataRole.UserRole)
        self._current_id = lt["id"]
        self.lt_name.setText(lt.get("name", ""))
        self.lt_title.setText(lt.get("title", ""))
        self.lt_subtitle.setText(lt.get("subtitle", ""))
        self.lt_social.setText(lt.get("social", ""))
        idx = self.lt_category.findText(lt.get("category", "general"))
        if idx >= 0:
            self.lt_category.setCurrentIndex(idx)

    def save_lt(self):
        _post("/lower-thirds", json={
            "name": self.lt_name.text(),
            "title": self.lt_title.text(),
            "subtitle": self.lt_subtitle.text(),
            "social": self.lt_social.text(),
            "category": self.lt_category.currentText(),
        })
        self.load_list()

    def show_lt(self):
        _post("/obs/lower-third", json={
            "name": self.lt_name.text(),
            "title": self.lt_title.text(),
            "subtitle": self.lt_subtitle.text(),
            "social": self.lt_social.text(),
        })

    def delete_lt(self):
        if self._current_id:
            _post(f"/lower-thirds/{self._current_id}", json={})
            import requests
            requests.delete(f"{API}/lower-thirds/{self._current_id}", timeout=3)
            self._current_id = None
            self.load_list()


# ══════════════════════════════════════
#  Tab: Planning du Service
# ══════════════════════════════════════

class PlanningTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: services list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        ll.addWidget(QLabel("Services"))
        self.service_list = QListWidget()
        self.service_list.itemClicked.connect(self.select_service)
        ll.addWidget(self.service_list)

        btn_new = QPushButton("+ Nouveau service")
        btn_new.clicked.connect(self.new_service)
        ll.addWidget(btn_new)

        # Right: service items
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        self.service_title = QLabel("Programme du service")
        self.service_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        rl.addWidget(self.service_title)

        self.item_list = QListWidget()
        rl.addWidget(self.item_list)

        ctrl = QHBoxLayout()

        self.item_type = QComboBox()
        self.item_type.addItems(["song", "bible", "lower_third", "text", "announcement"])
        ctrl.addWidget(self.item_type)

        self.item_text = QLineEdit()
        self.item_text.setPlaceholderText("Titre ou référence...")
        ctrl.addWidget(self.item_text)

        btn_add = QPushButton("Ajouter")
        btn_add.clicked.connect(self.add_item)
        ctrl.addWidget(btn_add)
        rl.addLayout(ctrl)

        # Live controls
        live_row = QHBoxLayout()
        btn_go = QPushButton("GO LIVE - Élément suivant")
        btn_go.setProperty("class", "success")
        btn_go.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        btn_go.clicked.connect(self.go_next_item)
        live_row.addWidget(btn_go)
        rl.addLayout(live_row)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([300, 600])
        layout.addWidget(splitter)

        self._current_service_id = None
        self._current_item_idx = -1
        self.load_services()

    def load_services(self):
        services = _get("/services")
        self.service_list.clear()
        if isinstance(services, list):
            for s in services:
                item = QListWidgetItem(f"{s['date']} - {s['title']}")
                item.setData(Qt.ItemDataRole.UserRole, s['id'])
                self.service_list.addItem(item)

    def select_service(self, item):
        sid = item.data(Qt.ItemDataRole.UserRole)
        self._current_service_id = sid
        self._current_item_idx = -1
        svc = _get(f"/services/{sid}")
        if "error" in svc:
            return
        self.service_title.setText(f"{svc['title']} - {svc['date']}")
        self.item_list.clear()
        for it in svc.get("items", []):
            icon = {"song": "\u266b", "bible": "\u271d", "lower_third": "\u263a",
                    "text": "\u270e", "announcement": "\u2709"}.get(it["item_type"], "\u25cf")
            label = it.get("custom_title", "") or it.get("custom_text", "")[:50] or f"[{it['item_type']}]"
            status_icon = "\u2705" if it["status"] == "done" else "\u25cb"
            li = QListWidgetItem(f"{status_icon} {icon} {label}")
            li.setData(Qt.ItemDataRole.UserRole, it)
            self.item_list.addItem(li)

    def new_service(self):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Nouveau service")
        form = QFormLayout(dlg)
        title_input = QLineEdit()
        title_input.setText("Culte Dominical")
        form.addRow("Titre:", title_input)
        date_input = QLineEdit()
        date_input.setPlaceholderText("YYYY-MM-DD")
        form.addRow("Date:", date_input)
        theme_input = QLineEdit()
        form.addRow("Thème:", theme_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec():
            _post("/services", json={
                "title": title_input.text(),
                "date": date_input.text(),
                "theme": theme_input.text(),
            })
            self.load_services()

    def add_item(self):
        if not self._current_service_id:
            return
        _post(f"/services/{self._current_service_id}/items", json={
            "item_type": self.item_type.currentText(),
            "custom_title": self.item_text.text(),
        })
        self.item_text.clear()
        # Reload
        for i in range(self.service_list.count()):
            item = self.service_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self._current_service_id:
                self.select_service(item)
                break

    def go_next_item(self):
        if self.item_list.count() == 0:
            return
        self._current_item_idx = min(self._current_item_idx + 1, self.item_list.count() - 1)
        self.item_list.setCurrentRow(self._current_item_idx)
        item = self.item_list.item(self._current_item_idx)
        data = item.data(Qt.ItemDataRole.UserRole)
        # Mark as done
        if data.get("id"):
            _post(f"/services/items/{data['id']}/status", params={"status": "done"})


# ══════════════════════════════════════
#  Tab: Import & Gestion
# ══════════════════════════════════════

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

BIBLE_VERSIONS = {
    "FreCrampon": ("LSG", "Bible Crampon 1923"),
    "FreBBB": ("BBB", "Bible de la Liturgie"),
    "FreBDM1744": ("BDM", "Bible de Martin 1744"),
    "FreJND": ("JND", "Bible Darby"),
    "FreSynodale1921": ("SYN", "Bible Synodale 1921"),
    "FrePGR": ("PGR", "Bible Perret-Gentil"),
}


class ImportWorker(QObject):
    """Worker pour exécuter les imports en arrière-plan."""
    finished = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, task, *args):
        super().__init__()
        self._task = task
        self._args = args

    def run(self):
        try:
            self._task(*self._args, progress_cb=self.progress.emit)
            self.finished.emit("OK")
        except Exception as e:
            self.finished.emit(f"ERREUR: {e}")


class ImportTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # ── Bible Import ──
        bible_group = QGroupBox("Import de Bible")
        bl = QVBoxLayout()

        bl.addWidget(QLabel("Sélectionnez une version à télécharger et importer :"))

        self.bible_combo = QComboBox()
        for code, (short, name) in BIBLE_VERSIONS.items():
            self.bible_combo.addItem(f"{short} - {name}", code)
        bl.addWidget(self.bible_combo)

        bible_btns = QHBoxLayout()
        btn_import_bible = QPushButton("Télécharger et Importer")
        btn_import_bible.clicked.connect(self.import_bible)
        bible_btns.addWidget(btn_import_bible)

        btn_bible_file = QPushButton("Importer depuis fichier JSON...")
        btn_bible_file.clicked.connect(self.import_bible_file)
        bible_btns.addWidget(btn_bible_file)
        bl.addLayout(bible_btns)

        self.bible_status = QLabel("")
        bl.addWidget(self.bible_status)

        bible_group.setLayout(bl)
        layout.addWidget(bible_group)

        # ── Chants d'Espérance Import ──
        ce_group = QGroupBox("Import des Chants d'Espérance (14 parties)")
        cl = QVBoxLayout()

        # Parts display
        parts_text = ""
        for num, name in CE_PARTS.items():
            parts_text += f"  {num:2d}. {name}\n"
        parts_label = QLabel(parts_text.strip())
        parts_label.setFont(QFont("Consolas", 9))
        parts_label.setStyleSheet("color: #a6adc8; padding: 8px;")
        cl.addWidget(parts_label)

        self.ce_songbook = QComboBox()
        self.ce_songbook.addItems(["CEF - Chants d'Espérance Français", "CEC - Chants d'Espérance Créole", "CARL - Chante akk Radio Lumière", "MEL_FR - Mélodie Français", "MEL_CR - Mélodie Créole"])
        cl.addWidget(self.ce_songbook)

        ce_btns = QHBoxLayout()

        btn_ce_json = QPushButton("Importer depuis fichier JSON...")
        btn_ce_json.clicked.connect(self.import_ce_json)
        ce_btns.addWidget(btn_ce_json)

        btn_ce_dir = QPushButton("Importer depuis dossier .txt...")
        btn_ce_dir.clicked.connect(self.import_ce_dir)
        ce_btns.addWidget(btn_ce_dir)

        btn_ce_template = QPushButton("Générer template JSON")
        btn_ce_template.setProperty("class", "secondary")
        btn_ce_template.clicked.connect(self.generate_ce_template)
        ce_btns.addWidget(btn_ce_template)
        cl.addLayout(ce_btns)

        self.ce_status = QLabel("")
        cl.addWidget(self.ce_status)

        ce_group.setLayout(cl)
        layout.addWidget(ce_group)

        # ── Création / Édition de chant ──
        edit_group = QGroupBox("Créer / Éditer un chant")
        el = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Recueil:"))
        self.edit_songbook = QComboBox()
        self.edit_songbook.addItems(["CEF", "CEC", "CARL", "MEL_FR", "MEL_CR"])
        row1.addWidget(self.edit_songbook)

        row1.addWidget(QLabel("N°:"))
        self.edit_number = QSpinBox()
        self.edit_number.setRange(0, 9999)
        row1.addWidget(self.edit_number)

        row1.addWidget(QLabel("Partie:"))
        self.edit_part = QComboBox()
        self.edit_part.addItem("Auto (par numéro)", 0)
        for num, name in CE_PARTS.items():
            self.edit_part.addItem(f"{num}. {name}", num)
        row1.addWidget(self.edit_part)
        el.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Titre:"))
        self.edit_title = QLineEdit()
        self.edit_title.setPlaceholderText("Titre du chant")
        row2.addWidget(self.edit_title)
        row2.addWidget(QLabel("Auteur:"))
        self.edit_author = QLineEdit()
        row2.addWidget(self.edit_author)
        el.addLayout(row2)

        el.addWidget(QLabel("Paroles (séparez couplets par ligne vide, utilisez [Couplet 1], [Refrain]...) :"))
        self.edit_lyrics = QPlainTextEdit()
        self.edit_lyrics.setPlaceholderText(
            "[Couplet 1]\nGloire à Dieu dans les lieux très hauts\n"
            "Et paix sur la terre aux hommes\n\n"
            "[Refrain]\nGloire, gloire, alléluia!\n\n"
            "[Couplet 2]\nQue son nom soit béni à jamais\nDans toutes les nations"
        )
        self.edit_lyrics.setMinimumHeight(180)
        el.addWidget(self.edit_lyrics)

        edit_btns = QHBoxLayout()

        btn_save_new = QPushButton("Enregistrer comme nouveau chant")
        btn_save_new.setProperty("class", "success")
        btn_save_new.clicked.connect(self.save_new_song)
        edit_btns.addWidget(btn_save_new)

        btn_load_edit = QPushButton("Charger un chant existant...")
        btn_load_edit.clicked.connect(self.load_song_for_edit)
        edit_btns.addWidget(btn_load_edit)

        btn_update = QPushButton("Mettre à jour le chant chargé")
        btn_update.setProperty("class", "warning")
        btn_update.clicked.connect(self.update_song)
        edit_btns.addWidget(btn_update)

        btn_delete = QPushButton("Supprimer")
        btn_delete.setProperty("class", "danger")
        btn_delete.clicked.connect(self.delete_song)
        edit_btns.addWidget(btn_delete)
        el.addLayout(edit_btns)

        self.edit_status = QLabel("")
        el.addWidget(self.edit_status)

        edit_group.setLayout(el)
        layout.addWidget(edit_group)

        # Log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.log.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log)

        self._editing_song_id = None

    def _log(self, msg: str):
        self.log.append(msg)

    # ── Bible Import ──

    def import_bible(self):
        file_code = self.bible_combo.currentData()
        code, name = BIBLE_VERSIONS[file_code]
        self.bible_status.setText(f"Import en cours: {name}...")
        self._log(f"Lancement import {name}...")

        def do_import():
            import subprocess, sys
            result = subprocess.run(
                [sys.executable, "scripts/import_bible.py", "--version", file_code, "--force"],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            return result.stdout + result.stderr

        import concurrent.futures
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = self._executor.submit(do_import)
        future.add_done_callback(lambda f: self._on_bible_done(f))

    def _on_bible_done(self, future):
        try:
            output = future.result()
            self._log(output)
            self.bible_status.setText("Import Bible terminé!")
        except Exception as e:
            self._log(f"Erreur: {e}")
            self.bible_status.setText(f"Erreur: {e}")

    def import_bible_file(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Fichier Bible JSON", "", "JSON (*.json)")
        if not path:
            return
        self._log(f"Import depuis: {path}")
        self.bible_status.setText("Import en cours...")

        def do_import():
            import subprocess, sys
            # Copy to data/ then run import
            import shutil
            dest = Path("data") / Path(path).name
            shutil.copy2(path, dest)
            result = subprocess.run(
                [sys.executable, "scripts/import_bible.py", "--force"],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            return result.stdout + result.stderr

        import concurrent.futures
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = self._executor.submit(do_import)
        future.add_done_callback(lambda f: self._on_bible_done(f))

    # ── Chants d'Espérance Import ──

    def _get_ce_songbook_code(self) -> str:
        return self.ce_songbook.currentText().split(" - ")[0]

    def import_ce_json(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Fichier Chants d'Espérance JSON", "", "JSON (*.json)")
        if not path:
            return
        songbook = self._get_ce_songbook_code()
        self.ce_status.setText("Import en cours...")
        self._log(f"Import CE depuis: {path} -> {songbook}")

        def do_import():
            import subprocess, sys
            result = subprocess.run(
                [sys.executable, "scripts/import_chants_esperance.py",
                 "--from-file", path, "--songbook", songbook, "--force"],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            return result.stdout + result.stderr

        import concurrent.futures
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = self._executor.submit(do_import)
        future.add_done_callback(lambda f: self._on_ce_done(f))

    def import_ce_dir(self):
        from PyQt6.QtWidgets import QFileDialog
        dirpath = QFileDialog.getExistingDirectory(self, "Dossier de fichiers .txt des chants")
        if not dirpath:
            return
        songbook = self._get_ce_songbook_code()
        self.ce_status.setText("Import en cours...")
        self._log(f"Import CE depuis dossier: {dirpath} -> {songbook}")

        def do_import():
            import subprocess, sys
            result = subprocess.run(
                [sys.executable, "scripts/import_chants_esperance.py",
                 "--from-dir", dirpath, "--songbook", songbook, "--force"],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            return result.stdout + result.stderr

        import concurrent.futures
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = self._executor.submit(do_import)
        future.add_done_callback(lambda f: self._on_ce_done(f))

    def _on_ce_done(self, future):
        try:
            output = future.result()
            self._log(output)
            self.ce_status.setText("Import Chants d'Espérance terminé!")
        except Exception as e:
            self._log(f"Erreur: {e}")
            self.ce_status.setText(f"Erreur: {e}")

    def generate_ce_template(self):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "scripts/import_chants_esperance.py", "--template"],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        self._log(result.stdout)
        self.ce_status.setText("Template généré dans data/chants_esperance_template.json")

    # ── Création / Édition de chant ──

    def _parse_lyrics(self) -> list[dict]:
        """Parse le texte des paroles en couplets structurés."""
        raw = self.edit_lyrics.toPlainText().strip()
        verses = []
        current_label = ""
        current_type = "verse"
        current_lines = []

        for line in raw.split("\n"):
            stripped = line.strip()
            if stripped.startswith("[") and "]" in stripped:
                if current_lines:
                    verses.append({
                        "type": current_type,
                        "label": current_label,
                        "text": "\n".join(current_lines),
                    })
                    current_lines = []
                current_label = stripped.strip("[]")
                current_type = "chorus" if "refrain" in current_label.lower() else "verse"
            elif stripped == "" and current_lines:
                # Ligne vide = fin de section si pas de brackets
                pass
            elif stripped:
                current_lines.append(stripped)

        if current_lines:
            verses.append({
                "type": current_type,
                "label": current_label,
                "text": "\n".join(current_lines),
            })
        return verses

    def save_new_song(self):
        verses = self._parse_lyrics()
        if not self.edit_title.text():
            self.edit_status.setText("Veuillez saisir un titre.")
            return

        result = _post("/songs", json={
            "songbook_code": self.edit_songbook.currentText(),
            "number": self.edit_number.value() or None,
            "title": self.edit_title.text(),
            "author": self.edit_author.text(),
            "verses": verses,
        })
        if "id" in result:
            self._editing_song_id = result["id"]
            self.edit_status.setText(f"Chant créé (ID: {result['id']})")
            self._log(f"Nouveau chant: #{self.edit_number.value()} {self.edit_title.text()} ({len(verses)} sections)")
        else:
            self.edit_status.setText(f"Erreur: {result}")

    def load_song_for_edit(self):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox

        dlg = QDialog(self)
        dlg.setWindowTitle("Charger un chant")
        dlg.setMinimumWidth(400)
        form = QVBoxLayout(dlg)

        search_row = QHBoxLayout()
        search_input = QLineEdit()
        search_input.setPlaceholderText("Rechercher par titre ou numéro...")
        search_row.addWidget(search_input)
        btn_search = QPushButton("Chercher")
        search_row.addWidget(btn_search)
        form.addLayout(search_row)

        result_list = QListWidget()
        form.addWidget(result_list)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addWidget(buttons)

        def do_search():
            songs = _get("/songs", search=search_input.text())
            result_list.clear()
            if isinstance(songs, list):
                for s in songs:
                    num = f"#{s['number']} " if s.get('number') else ""
                    item = QListWidgetItem(f"{num}{s['title']}")
                    item.setData(Qt.ItemDataRole.UserRole, s['id'])
                    result_list.addItem(item)

        btn_search.clicked.connect(do_search)
        search_input.returnPressed.connect(do_search)
        do_search()

        if dlg.exec():
            sel = result_list.currentItem()
            if sel:
                song_id = sel.data(Qt.ItemDataRole.UserRole)
                song = _get(f"/songs/{song_id}")
                if "error" not in song:
                    self._editing_song_id = song["id"]
                    self.edit_title.setText(song.get("title", ""))
                    self.edit_author.setText(song.get("author", ""))
                    self.edit_number.setValue(song.get("number", 0) or 0)

                    # Rebuild lyrics text
                    lyrics_text = ""
                    for v in song.get("verses", []):
                        if v.get("verse_label"):
                            lyrics_text += f"[{v['verse_label']}]\n"
                        lyrics_text += v.get("text", "") + "\n\n"
                    self.edit_lyrics.setPlainText(lyrics_text.strip())
                    self.edit_status.setText(f"Chant chargé: ID {song_id}")

    def update_song(self):
        if not self._editing_song_id:
            self.edit_status.setText("Aucun chant chargé. Utilisez 'Charger un chant existant'.")
            return

        verses = self._parse_lyrics()

        # Delete old song and recreate (simpler than partial update)
        import requests
        requests.delete(f"{API}/songs/{self._editing_song_id}", timeout=3)

        result = _post("/songs", json={
            "songbook_code": self.edit_songbook.currentText(),
            "number": self.edit_number.value() or None,
            "title": self.edit_title.text(),
            "author": self.edit_author.text(),
            "verses": verses,
        })
        if "id" in result:
            self._editing_song_id = result["id"]
            self.edit_status.setText(f"Chant mis à jour (ID: {result['id']})")
            self._log(f"Chant mis à jour: #{self.edit_number.value()} {self.edit_title.text()}")
        else:
            self.edit_status.setText(f"Erreur: {result}")

    def delete_song(self):
        if not self._editing_song_id:
            self.edit_status.setText("Aucun chant chargé.")
            return
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "Confirmer", "Supprimer ce chant définitivement?")
        if reply == QMessageBox.StandardButton.Yes:
            import requests
            requests.delete(f"{API}/songs/{self._editing_song_id}", timeout=3)
            self._log(f"Chant supprimé: ID {self._editing_song_id}")
            self._editing_song_id = None
            self.edit_title.clear()
            self.edit_author.clear()
            self.edit_lyrics.clear()
            self.edit_number.setValue(0)
            self.edit_status.setText("Chant supprimé.")


# ══════════════════════════════════════
#  Tab: Utilisateurs
# ══════════════════════════════════════

class UsersTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: user list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("Utilisateurs"))

        self.user_list = QListWidget()
        self.user_list.itemClicked.connect(self.select_user)
        ll.addWidget(self.user_list)

        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setProperty("class", "secondary")
        btn_refresh.clicked.connect(self.load_users)
        ll.addWidget(btn_refresh)

        # Right: user form
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        form_group = QGroupBox("Créer / Modifier un utilisateur")
        fl = QVBoxLayout()

        for label, attr, placeholder in [
            ("Nom d'utilisateur:", "user_username", "ex: operateur1"),
            ("Nom affiché:", "user_display", "ex: Jean Dupont"),
            ("Mot de passe:", "user_password", "Min 4 caractères"),
            ("PIN (4-6 chiffres):", "user_pin", "ex: 1234"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            inp = QLineEdit()
            inp.setPlaceholderText(placeholder)
            if "passe" in label.lower():
                inp.setEchoMode(QLineEdit.EchoMode.Password)
            setattr(self, attr, inp)
            row.addWidget(inp)
            fl.addLayout(row)

        role_row = QHBoxLayout()
        role_row.addWidget(QLabel("Rôle:"))
        self.user_role = QComboBox()
        self.user_role.addItems(["operator", "admin", "presenter", "guest"])
        role_row.addWidget(self.user_role)
        fl.addLayout(role_row)

        fl.addWidget(QLabel("Permissions par rôle:"))
        perms = QLabel(
            "  admin: Accès complet (config, users, import, suppression)\n"
            "  operator: Projection, chants, LT, planning, médias\n"
            "  presenter: Navigation slides, upload, projection\n"
            "  guest: Upload de fichiers uniquement"
        )
        perms.setFont(QFont("Consolas", 9))
        perms.setStyleSheet("color: #a6adc8; padding: 4px;")
        fl.addWidget(perms)

        form_group.setLayout(fl)
        rl.addWidget(form_group)

        btn_row = QHBoxLayout()
        btn_create = QPushButton("Créer")
        btn_create.setProperty("class", "success")
        btn_create.clicked.connect(self.create_user)
        btn_row.addWidget(btn_create)

        btn_update = QPushButton("Modifier")
        btn_update.setProperty("class", "warning")
        btn_update.clicked.connect(self.update_user)
        btn_row.addWidget(btn_update)

        btn_delete = QPushButton("Supprimer")
        btn_delete.setProperty("class", "danger")
        btn_delete.clicked.connect(self.delete_user)
        btn_row.addWidget(btn_delete)
        rl.addLayout(btn_row)

        self.user_status = QLabel("")
        rl.addWidget(self.user_status)

        # Default credentials info
        info = QGroupBox("Identifiants par défaut")
        il = QVBoxLayout()
        il.addWidget(QLabel("Admin: admin / admin (PIN: 1234)"))
        il.addWidget(QLabel("Changez le mot de passe admin dès que possible!"))
        info.setLayout(il)
        rl.addWidget(info)

        rl.addStretch()

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([300, 500])
        layout.addWidget(splitter)

        self._current_user_id = None
        self.load_users()

    def load_users(self):
        users = _get("/auth/users")
        self.user_list.clear()
        if isinstance(users, list):
            for u in users:
                role_icon = {"admin": "\u2b50", "operator": "\u2699", "guest": "\ud83d\udc64"}.get(u["role"], "")
                active = "" if u.get("is_active", 1) else " [INACTIF]"
                item = QListWidgetItem(f"{role_icon} {u['username']} ({u['role']}){active}")
                item.setData(Qt.ItemDataRole.UserRole, u)
                self.user_list.addItem(item)

    def select_user(self, item):
        u = item.data(Qt.ItemDataRole.UserRole)
        self._current_user_id = u["id"]
        self.user_username.setText(u.get("username", ""))
        self.user_display.setText(u.get("display_name", ""))
        self.user_password.clear()
        self.user_pin.clear()
        idx = self.user_role.findText(u.get("role", "operator"))
        if idx >= 0:
            self.user_role.setCurrentIndex(idx)
        self.user_status.setText(f"Utilisateur chargé: {u['username']}")

    def create_user(self):
        if not self.user_username.text() or not self.user_password.text():
            self.user_status.setText("Nom d'utilisateur et mot de passe requis.")
            return
        result = _post("/auth/users", json={
            "username": self.user_username.text(),
            "display_name": self.user_display.text(),
            "password": self.user_password.text(),
            "pin": self.user_pin.text(),
            "role": self.user_role.currentText(),
        })
        if result.get("ok"):
            self.user_status.setText(f"Utilisateur créé (ID: {result['id']})")
            self.load_users()
        else:
            self.user_status.setText(f"Erreur: {result.get('error', result)}")

    def update_user(self):
        if not self._current_user_id:
            self.user_status.setText("Sélectionnez un utilisateur d'abord.")
            return
        import requests
        data = {"display_name": self.user_display.text(), "role": self.user_role.currentText()}
        if self.user_password.text():
            data["password"] = self.user_password.text()
        if self.user_pin.text():
            data["pin"] = self.user_pin.text()
        r = requests.put(f"{API}/auth/users/{self._current_user_id}", json=data, timeout=3)
        if r.json().get("ok"):
            self.user_status.setText("Utilisateur modifié.")
            self.load_users()
        else:
            self.user_status.setText(f"Erreur: {r.text}")

    def delete_user(self):
        if not self._current_user_id:
            return
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "Confirmer", "Supprimer cet utilisateur?")
        if reply == QMessageBox.StandardButton.Yes:
            import requests
            requests.delete(f"{API}/auth/users/{self._current_user_id}", timeout=3)
            self._current_user_id = None
            self.user_status.setText("Utilisateur supprimé.")
            self.load_users()


# ══════════════════════════════════════
#  Server Thread
# ══════════════════════════════════════

class ServerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)

    def run(self):
        import uvicorn
        from core.server import app
        uvicorn.run(app, host=config.server.host, port=config.server.port, log_level="warning")


# ══════════════════════════════════════
#  Main Window
# ══════════════════════════════════════

class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EBJFL-Broadcast - Régie Live Tout-en-Un")
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(DARK_STYLE)
        self.setWindowIcon(QIcon(LOGO_PATH))

        # Central layout with logo header
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header with logo
        header = QWidget()
        header.setStyleSheet("background: #181825; border-bottom: 2px solid #89b4fa;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)

        logo_label = QLabel()
        logo_pixmap = QPixmap(LOGO_PATH).scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation)
        logo_label.setPixmap(logo_pixmap)
        header_layout.addWidget(logo_label)

        title_label = QLabel("EBJFL-Broadcast")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #89b4fa;")
        header_layout.addWidget(title_label)

        subtitle_label = QLabel("Eglise Baptiste Jérusalem de Fort-Liberté")
        subtitle_label.setFont(QFont("Segoe UI", 10))
        subtitle_label.setStyleSheet("color: #a6adc8;")
        header_layout.addWidget(subtitle_label)

        header_layout.addStretch()
        main_layout.addWidget(header)

        # Tabs
        tabs = QTabWidget()
        self.status_tab = StatusTab()
        self.projection_tab = ProjectionTab()
        self.songs_tab = SongsTab()
        self.lt_tab = LowerThirdsTab()
        self.planning_tab = PlanningTab()
        self.import_tab = ImportTab()
        self.users_tab = UsersTab()

        tabs.addTab(self.status_tab, "Connexion")
        tabs.addTab(self.projection_tab, "Projection")
        tabs.addTab(self.songs_tab, "Chants")
        tabs.addTab(self.lt_tab, "Lower Thirds")
        tabs.addTab(self.planning_tab, "Planning")
        tabs.addTab(self.import_tab, "Import / Gestion")
        tabs.addTab(self.users_tab, "Utilisateurs")

        main_layout.addWidget(tabs)
        self.setCentralWidget(central)

        # Status bar
        self.statusBar().showMessage("EBJFL-Broadcast v0.2 | Offline-First | Tout-en-Un")

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(5000)

        # Start server
        self.server_thread = ServerThread()
        self.server_thread.start()
        self.status_tab.log.append(f"Serveur démarré sur le port {config.server.port}")

        # Try OBS
        self.status_tab.connect_obs()

    def refresh(self):
        self.status_tab.refresh()
