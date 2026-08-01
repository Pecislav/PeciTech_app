"""
device_view/plugins_panel.py
------------------------------------------------------------------
Prava cast (~20 % sirky, cela vyska okna) obrazovky detailu zarizeni.

Nahore jsou dve zalozky:
  - "Akce"   - kategorie/pluginy, ktere uz mas "nainstalovane" (puvodni
               rozbalovaci seznam - klik na hlavicku kategorie ji
               rozbali/sbali na miste, presne jako v Elgato appce).
               Konkretni akce uvnitr jsou PRETAHNUTELNE (drag & drop)
               na tlacitko/enkoder v obrysu PeciDecku vlevo.
  - "Obchod" - pluginy, ktere jeste nemas stazene, s tlacitkem
               "Instalovat" u kazdeho - po instalaci se presune do "Akce".
               (Skutecne stahovani/instalace z internetu je vetsi
               samostatna funkce na priste - tohle je zatim prepinac
               mezi "co uz mam" a "co si jeste muzu stahnout", presne
               jak jsi chtel.)

"Navigace" a "Systém" jsou specialni vestavene kategorie (vzdy dostupne,
"installed": True, "builtin": True) - obsahuji zakladni funkce appky
samotne (stranky, otevirani veci, text/klavesy/media), nejsou to
stahovatelne pluginy.

Vsechny ostatni (OBS, Spotify, Discord, Hlasitost, Twitch) ted START­UJI
jako "installed": False - objevi se nejdriv v zalozce "Obchod", teprve
po kliknuti na "Instalovat" se presunou do "Akce". Tohle je zamerne -
odpovida to realnemu workflow (nejdriv stahnout plugin, pak ho pouzivat),
misto aby byly predem nainstalovane vsechny naraz.

"Hlasitost" ma jen jednu polozku "Nastavit hlasitost" s "has_amount":
True - v konfiguracnim panelu dole (device_view.py) se pak misto dvou
oddelenych "zvysit/snizit" zobrazi jeden posuvnik 0-100.
"""

import json

from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QScrollArea, QApplication, QStackedWidget,
)

from .device_view import BG, TEXT, TEXT_MUTED, ORANGE, ACTION_MIME_TYPE

PLUGINS = [
    {
        "id": "navigation", "name": "Navigace", "icon": "\U0001F9ED", "installed": True, "builtin": True,
        "modules": [
            {"id": "next_page", "name": "Další stránka", "icon": "\u25B6"},
            {"id": "prev_page", "name": "Předchozí stránka", "icon": "\u25C0"},
        ],
    },
    {
        "id": "system", "name": "Systém", "icon": "\U0001F5A5", "installed": True, "builtin": True,
        "modules": [
            {"id": "open_website", "name": "Otevřít web", "icon": "\U0001F310", "input_type": "url"},
            {"id": "open_app", "name": "Otevřít aplikaci", "icon": "\U0001F4F1", "input_type": "path"},
            {"id": "type_text", "name": "Napsat text", "icon": "\U0001F4DD", "input_type": "text"},
            {"id": "hotkey", "name": "Klávesová zkratka", "icon": "\u2328", "input_type": "hotkey"},
            {"id": "media_play_pause", "name": "Média: Přehrát/Pauza", "icon": "\u23EF"},
            {"id": "media_next", "name": "Média: Další", "icon": "\u23ED"},
            {"id": "media_prev", "name": "Média: Předchozí", "icon": "\u23EE"},
        ],
    },
    {
        "id": "obs", "name": "OBS Studio", "icon": "\U0001F3A5", "installed": False,
        "modules": [
            {"id": "start_stream", "name": "Spustit stream", "icon": "\U0001F534"},
            {"id": "stop_stream", "name": "Zastavit stream", "icon": "\u23F9"},
            {"id": "switch_scene", "name": "Přepnout scénu", "icon": "\U0001F3AC"},
            {"id": "mute_mic", "name": "Ztlumit mikrofon", "icon": "\U0001F507"},
        ],
    },
    {
        "id": "spotify", "name": "Spotify", "icon": "\U0001F3B5", "installed": False,
        "modules": [
            {"id": "play_pause", "name": "Play / Pauza", "icon": "\u23EF"},
            {"id": "next_track", "name": "Další skladba", "icon": "\u23ED"},
            {"id": "prev_track", "name": "Předchozí skladba", "icon": "\u23EE"},
        ],
    },
    {
        "id": "discord", "name": "Discord", "icon": "\U0001F4AC", "installed": False,
        "modules": [
            {"id": "toggle_mute", "name": "Mute / Unmute", "icon": "\U0001F3A4"},
            {"id": "toggle_deafen", "name": "Deafen", "icon": "\U0001F3A7"},
        ],
    },
    {
        "id": "volume", "name": "Hlasitost", "icon": "\U0001F50A", "installed": False,
        "modules": [
            {"id": "set_volume", "name": "Nastavit hlasitost", "icon": "\U0001F50A", "has_amount": True},
            {"id": "vol_mute", "name": "Ztlumit", "icon": "\U0001F507"},
        ],
    },
    {
        "id": "twitch", "name": "Twitch", "icon": "\U0001F4FA", "installed": False,
        "modules": [
            {"id": "marker", "name": "Přidat marker", "icon": "\U0001F4CD"},
        ],
    },
    {
        # Priklad pluginu, co jeste NENI nainstalovany - ukazuje se v zalozce "Obchod".
        "id": "philips_hue", "name": "Philips Hue", "icon": "\U0001F4A1", "installed": False,
        "modules": [
            {"id": "toggle_lights", "name": "Zapnout/vypnout světla", "icon": "\U0001F4A1"},
        ],
    },
]


class DraggableModuleItem(QFrame):
    """Jedna konkretni akce uvnitr rozbalene kategorie - da se pretahnout na tlacitko/enkoder."""

    def __init__(self, action: dict):
        super().__init__()
        self.action = action
        self.setCursor(Qt.OpenHandCursor)
        self.setFixedHeight(36)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        label = QLabel(f"{action['icon']}  {action['name']}")
        label.setStyleSheet(f"color: {TEXT}; font-size: 12px; background: transparent; border: none;")
        label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(label)
        self.setStyleSheet("""
            QFrame { background-color: transparent; border-radius: 8px; }
            QFrame:hover { background-color: rgba(255,255,255,0.05); }
        """)
        self._drag_start = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start is None or not (event.buttons() & Qt.LeftButton):
            return
        if (event.position().toPoint() - self._drag_start).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(ACTION_MIME_TYPE, json.dumps(self.action).encode("utf-8"))
        drag.setMimeData(mime)

        # Aby behem tazeni bylo videt, co vlastne "nesu" - bez tohohle
        # QDrag nekdy nic nezobrazi a vypada to, jako by se nic netahalo.
        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.position().toPoint())

        drag.exec(Qt.CopyAction)
        self._drag_start = None


class CategorySection(QWidget):
    """Rozbalovaci kategorie (slozka) - klik na hlavicku ji rozbali/sbali na miste (jako v Elgato appce)."""

    def __init__(self, plugin: dict, expanded: bool = False):
        super().__init__()
        self.plugin = plugin
        self._expanded = expanded

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        self.header_btn = QPushButton()
        self.header_btn.setCursor(Qt.PointingHandCursor)
        self.header_btn.clicked.connect(self._toggle)
        outer.addWidget(self.header_btn)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(20, 2, 4, 8)
        content_layout.setSpacing(2)
        for module in plugin.get("modules", []):
            action = {
                "icon": module["icon"],
                "name": module["name"],
                "plugin_id": plugin["id"],
                "action_id": module["id"],
                "has_amount": module.get("has_amount", False),
                "input_type": module.get("input_type"),
            }
            content_layout.addWidget(DraggableModuleItem(action))
        outer.addWidget(self.content)

        self._refresh()

    def _toggle(self):
        self._expanded = not self._expanded
        self._refresh()

    def _refresh(self):
        self.content.setVisible(self._expanded)
        chevron = "\u25BE" if self._expanded else "\u25B8"
        self.header_btn.setText(f"{chevron}  {self.plugin['icon']}  {self.plugin['name']}")
        self.header_btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left; background-color: transparent; border: none;
                color: {TEXT}; font-size: 13px; font-weight: 700; padding: 8px 4px;
            }}
            QPushButton:hover {{ background-color: rgba(255,255,255,0.05); border-radius: 6px; }}
        """)


class PluginsPanel(QWidget):
    """Zalozky Akce/Obchod nahore + pod tim bud rozbalovaci kategorie, nebo seznam k instalaci."""

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 24, 16, 16)
        outer.setSpacing(10)

        heading = QLabel("Pluginy")
        heading.setStyleSheet(f"color: {TEXT}; font-size: 16px; font-weight: 700;")
        outer.addWidget(heading)

        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(6)
        self.actions_tab_btn = QPushButton("Akce")
        self.store_tab_btn = QPushButton("Obchod")
        self.actions_tab_btn.setCursor(Qt.PointingHandCursor)
        self.store_tab_btn.setCursor(Qt.PointingHandCursor)
        self.actions_tab_btn.clicked.connect(lambda: self._switch_tab(0))
        self.store_tab_btn.clicked.connect(lambda: self._switch_tab(1))
        tabs_row.addWidget(self.actions_tab_btn)
        tabs_row.addWidget(self.store_tab_btn)
        tabs_row.addStretch()
        outer.addLayout(tabs_row)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack)

        # --- stranka 0: "Akce" - nainstalovane kategorie ---
        self.actions_page = QWidget()
        actions_layout = QVBoxLayout(self.actions_page)
        actions_layout.setContentsMargins(0, 4, 0, 0)
        actions_layout.setSpacing(6)
        hint = QLabel("Přetáhni akci na\ntlačítko nebo enkodér.")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        actions_layout.addWidget(hint)
        self.actions_scroll = QScrollArea()
        self.actions_scroll.setWidgetResizable(True)
        self.actions_scroll.setFrameShape(QFrame.NoFrame)
        actions_layout.addWidget(self.actions_scroll)

        # --- stranka 1: "Obchod" - pluginy k instalaci ---
        self.store_page = QWidget()
        store_layout = QVBoxLayout(self.store_page)
        store_layout.setContentsMargins(0, 4, 0, 0)
        store_layout.setSpacing(6)
        store_hint = QLabel("Stáhni si další pluginy.")
        store_hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        store_layout.addWidget(store_hint)
        self.store_scroll = QScrollArea()
        self.store_scroll.setWidgetResizable(True)
        self.store_scroll.setFrameShape(QFrame.NoFrame)
        store_layout.addWidget(self.store_scroll)

        self.stack.addWidget(self.actions_page)
        self.stack.addWidget(self.store_page)

        self._rebuild_actions_list()
        self._rebuild_store_list()
        self._switch_tab(0)

        self.setStyleSheet(f"background-color: {BG}; border-left: 1px solid rgba(255,255,255,0.06);")

    def _switch_tab(self, index: int):
        self.stack.setCurrentIndex(index)
        active_style = f"""
            QPushButton {{
                background-color: {ORANGE}; color: white; border: none;
                border-radius: 8px; padding: 5px 12px; font-size: 12px; font-weight: 700;
            }}
        """
        inactive_style = f"""
            QPushButton {{
                background-color: transparent; color: {TEXT_MUTED}; border: 1px solid rgba(255,255,255,0.12);
                border-radius: 8px; padding: 5px 12px; font-size: 12px; font-weight: 700;
            }}
            QPushButton:hover {{ background-color: rgba(255,255,255,0.05); }}
        """
        self.actions_tab_btn.setStyleSheet(active_style if index == 0 else inactive_style)
        self.store_tab_btn.setStyleSheet(active_style if index == 1 else inactive_style)

    def _rebuild_actions_list(self):
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignTop)
        for plugin in PLUGINS:
            if plugin.get("installed", True):
                layout.addWidget(CategorySection(plugin))
        layout.addStretch()
        self.actions_scroll.setWidget(inner)

    def _rebuild_store_list(self):
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignTop)

        available = [p for p in PLUGINS if not p.get("installed", True)]
        if not available:
            empty = QLabel("Všechny dostupné pluginy\njsou už nainstalované.")
            empty.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            layout.addWidget(empty)
        for plugin in available:
            layout.addWidget(self._build_store_row(plugin))

        layout.addStretch()
        self.store_scroll.setWidget(inner)

    def _build_store_row(self, plugin: dict) -> QFrame:
        row = QFrame()
        row.setStyleSheet("QFrame { background-color: #1c1c1f; border-radius: 8px; }")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 8, 10, 8)
        label = QLabel(f"{plugin['icon']}  {plugin['name']}")
        label.setStyleSheet(f"color: {TEXT}; font-size: 12px; background: transparent; border: none;")
        row_layout.addWidget(label)
        row_layout.addStretch()

        install_btn = QPushButton("Instalovat")
        install_btn.setCursor(Qt.PointingHandCursor)
        install_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ORANGE}; color: white; border: none;
                border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #e8650f; }}
        """)
        install_btn.clicked.connect(lambda checked=False, p=plugin: self._install_plugin(p))
        row_layout.addWidget(install_btn)
        return row

    def _install_plugin(self, plugin: dict):
        plugin["installed"] = True
        self._rebuild_actions_list()
        self._rebuild_store_list()
        self._switch_tab(0)