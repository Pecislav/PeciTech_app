"""
device_view/plugins_panel.py
------------------------------------------------------------------
Prava cast (~20 % sirky, cela vyska okna) obrazovky detailu zarizeni.

Nahore jsou dve zalozky:
  - "Akce"   - BUILTIN_PLUGINS (Navigace, Systém - vzdy dostupne, soucast
               appky samotne) + vsechny SKUTECNE NAINSTALOVANE pluginy
               nactene ze slozky plugins/ (viz plugin_loader.py).
  - "Obchod" - plugin_loader.STORE_CATALOG minus to, co uz je
               nainstalovane. Klik na "Instalovat" stahne .zip z GitHubu
               a rozbali ho do plugins/<id>/ - viz plugin_loader.py pro
               presny mechanismus.

Kategorie se rozbaluji NA MISTE (accordion), presne jako v Elgato appce:
klik na hlavicku kategorie ji rozbali/sbali, beze zmeny stranky.
Konkretni akce uvnitr jsou PRETAHNUTELNE (drag & drop) na tlacitko/
enkoder v obrysu PeciDecku vlevo - viz device_view.py.
"""

import json

from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QScrollArea, QApplication, QMessageBox, QDialog, QLineEdit,
)

from . import plugin_loader
from .device_view import BG, TEXT, TEXT_MUTED, ORANGE, ACTION_MIME_TYPE

# Vestavene kategorie - soucast appky samotne, vzdy dostupne v "Akce"
# (nejsou to stahovatelne pluginy, proto nejsou v plugin_loader.STORE_CATALOG).
BUILTIN_PLUGINS = [
    {
        "id": "navigation", "name": "Navigace", "icon": "\U0001F9ED", "installed": True, "builtin": True,
        "modules": [
            {"id": "next_page", "name": "Další stránka", "icon": "\u25B6", "target": "button"},
            {"id": "prev_page", "name": "Předchozí stránka", "icon": "\u25C0", "target": "button"},
        ],
    },
    {
        "id": "system", "name": "Systém", "icon": "\U0001F5A5", "installed": True, "builtin": True,
        "modules": [
            {"id": "open_website", "name": "Otevřít web", "icon": "\U0001F310", "input_type": "url", "target": "button"},
            {"id": "open_app", "name": "Otevřít aplikaci", "icon": "\U0001F4F1", "input_type": "path", "target": "button"},
            {"id": "type_text", "name": "Napsat text", "icon": "\U0001F4DD", "input_type": "text", "target": "button"},
            {"id": "hotkey", "name": "Klávesová zkratka", "icon": "\u2328", "input_type": "hotkey", "target": "button"},
            {"id": "media_play_pause", "name": "Média: Přehrát/Pauza", "icon": "\u23EF", "target": "button"},
            {"id": "media_next", "name": "Média: Další", "icon": "\u23ED", "target": "both"},
            {"id": "media_prev", "name": "Média: Předchozí", "icon": "\u23EE", "target": "both"},
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

    def __init__(self, plugin: dict, expanded: bool = False, on_open_settings=None):
        super().__init__()
        self.plugin = plugin
        self._expanded = expanded

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(0)

        self.header_btn = QPushButton()
        self.header_btn.setCursor(Qt.PointingHandCursor)
        self.header_btn.clicked.connect(self._toggle)
        header_row.addWidget(self.header_btn, stretch=1)

        if plugin.get("has_settings") and on_open_settings:
            settings_btn = QPushButton("\u2699")
            settings_btn.setCursor(Qt.PointingHandCursor)
            settings_btn.setFixedSize(24, 24)
            settings_btn.setToolTip("Nastavení pluginu")
            settings_btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; border: none; color: {TEXT_MUTED}; font-size: 13px; border-radius: 12px; }}
                QPushButton:hover {{ background-color: rgba(255,255,255,0.08); color: {TEXT}; }}
            """)
            settings_btn.clicked.connect(lambda checked=False, pid=plugin["id"]: on_open_settings(pid))
            header_row.addWidget(settings_btn)

        outer.addLayout(header_row)

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
                "placeholder": module.get("placeholder"),
                "target": module.get("target", "both"),
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


class PluginSettingsDialog(QDialog):
    """
    Male okno na nastaveni pluginu (heslo, port...) - podle SETTINGS
    schematu, ktere plugin sam definuje. Po ulozeni appka rovnou zkusi
    znovu pripojit (test_connection()), pokud ho plugin nabizi.
    """

    def __init__(self, plugin_id: str, module, message: str = None, parent=None):
        super().__init__(parent)
        self.plugin_id = plugin_id
        self.module = module
        self.setWindowTitle("Nastavení pluginu")
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)

        if message:
            info = QLabel(message)
            info.setWordWrap(True)
            info.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            layout.addWidget(info)

        schema = getattr(module, "SETTINGS", [])
        current = module.get_settings() if hasattr(module, "get_settings") else {}

        self._edits = {}
        for field in schema:
            row = QHBoxLayout()
            label = QLabel(field["name"])
            label.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
            row.addWidget(label)
            edit = QLineEdit(str(current.get(field["id"], field.get("default", ""))))
            if field.get("input_type") == "password":
                edit.setEchoMode(QLineEdit.Password)
            edit.setStyleSheet(f"""
                QLineEdit {{
                    background-color: #1c1c1f; border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 6px; padding: 4px 8px; color: {TEXT}; font-size: 12px;
                }}
            """)
            row.addWidget(edit)
            self._edits[field["id"]] = edit
            layout.addLayout(row)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        save_btn = QPushButton("Uložit a připojit")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ORANGE}; color: white; border: none;
                border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #e8650f; }}
        """)
        save_btn.clicked.connect(self._save_and_test)
        buttons_row.addWidget(save_btn)
        layout.addLayout(buttons_row)

        self.setStyleSheet(f"QDialog {{ background-color: {BG}; }}")

    def _save_and_test(self):
        values = {field_id: edit.text() for field_id, edit in self._edits.items()}
        if hasattr(self.module, "save_settings"):
            self.module.save_settings(values)

        if hasattr(self.module, "test_connection"):
            ok, error = self.module.test_connection()
            if ok:
                QMessageBox.information(self, "Připojeno", "Nastavení uloženo, připojení funguje.")
                self.accept()
            else:
                QMessageBox.warning(self, "Stále se nepodařilo připojit", error or "Zkontroluj zadané údaje.")
        else:
            self.accept()


class PluginsPanel(QWidget):
    """
    Cisty panel s akcemi pro drag & drop (vestavene kategorie + skutecne
    nainstalovane a POVOLENE pluginy). Zadna zalozka "Obchod" tady uz
    neni - spravu pluginu (instalace/odinstalace/povoleni) resi
    Nastaveni -> Pluginy, viz settings.py (PluginsManagementSection).
    """

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 24, 16, 16)
        outer.setSpacing(10)

        heading = QLabel("Pluginy")
        heading.setStyleSheet(f"color: {TEXT}; font-size: 16px; font-weight: 700;")
        outer.addWidget(heading)

        hint = QLabel("Přetáhni akci na\ntlačítko nebo enkodér.")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        outer.addWidget(hint)

        self.actions_scroll = QScrollArea()
        self.actions_scroll.setWidgetResizable(True)
        self.actions_scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(self.actions_scroll)

        self._rebuild_actions_list()

        self.setStyleSheet(f"background-color: {BG}; border-left: 1px solid rgba(255,255,255,0.06);")

    def open_settings_dialog(self, plugin_id: str, message: str = None):
        module = plugin_loader.get_plugin_module(plugin_id)
        if module is None:
            return
        schema = getattr(module, "SETTINGS", [])
        if not schema:
            QMessageBox.information(self, "Bez nastavení", "Tenhle plugin nemá žádné nastavení k úpravě.")
            return
        dialog = PluginSettingsDialog(plugin_id, module, message, parent=self)
        dialog.exec()

    def _rebuild_actions_list(self):
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignTop)

        for plugin in BUILTIN_PLUGINS:
            layout.addWidget(CategorySection(plugin, on_open_settings=self.open_settings_dialog))
        for plugin in plugin_loader.load_installed_plugins():
            layout.addWidget(CategorySection(plugin, on_open_settings=self.open_settings_dialog))

        layout.addStretch()
        self.actions_scroll.setWidget(inner)