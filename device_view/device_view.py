"""
device_view/device_view.py
------------------------------------------------------------------
Detail zarizeni PeciDeck - otevre se kliknutim na pripojenou dlazdici
na hlavni obrazovce (viz main_window.py). Vlevo (~80% sirky) je lehky
obrys desky - tlacitka jako obrys keycapu (4x2), pod tim displej, pod
tim 3 enkodery, hned pod tim navigace stranek a konfiguracni panel.
Vpravo (~20% sirky, cela vyska okna) je panel s kategoriemi/pluginy
(plugins_panel.py).

Prirazeni (podle Elgato appky): akci PRETAHNES levym tlacitkem z praveho
panelu na tlacitko/enkoder - cil se behem pretazeni zesvetli. Po pusteni
se akce priradi.

Klik na tlacitko/enkoder (bez pretahovani) ho VYBERE (modry okraj) a
dole (jen pod levym sloupcem, ne pod celym oknem) se zobrazi
konfiguracni panel pro tu konkretni akci - vcetne vlastniho NAZVU, ktery
se ulozi a zobrazi pod ikonkou primo na tlacitku/enkoderu.

Odebrani prirazeni: pravy klik na tlacitko/enkoder -> "Odebrat" -> jeste
potvrzovaci dialog, jestli to fakt chces.

Testovani akci bez hardwaru: nektere akce (otevrit web/aplikaci, napsat
text, klavesova zkratka, media tlacitka) jdou rovnou "Otestovat" primo
z konfiguracniho panelu - spusti se doopravdy. Text/hotkey/media pouzivaji
knihovnu `pynput` (pip install pynput) pro simulaci klaves.

Pod mrizkou tlacitek je navigacni panel stranek (<, cisla, +, >) - jako
v Elgato appce, max. MAX_PAGES stranek. Kazda stranka ma vlastni sadu
prirazeni tlacitek; nove stranky zacinaji prazdne. Enkodery zatim
stranky nemaji.
"""

import json
import os
import sys
import subprocess
import webbrowser

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QFrame,
    QMenu, QLineEdit, QSlider, QFileDialog, QMessageBox,
)

try:
    from pynput.keyboard import Controller as _KeyboardController, Key as _Key
    _keyboard = _KeyboardController()
except ImportError:
    _keyboard = None
    _Key = None

BG = "#111113"
TEXT = "#f2f2f0"
TEXT_MUTED = "#9a9aa0"
ORANGE = "#ff7a29"
BLUE_SELECTED = "#4da6ff"
OUTLINE = "rgba(255,255,255,0.25)"
ACTION_MIME_TYPE = "application/x-pecitech-action"
MAX_PAGES = 20

TESTABLE_ACTION_IDS = {
    "open_website", "open_app", "type_text", "hotkey",
    "media_play_pause", "media_next", "media_prev",
}

HOTKEY_NAME_MAP = {
    "ctrl": "ctrl", "control": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "cmd": "cmd", "win": "cmd", "super": "cmd",
}

from .plugins_panel import PluginsPanel  # noqa: E402 (musi byt az po definici konstant vyse)


class Keycap(QFrame):
    """Jedno tlacitko PeciDecku - obrys keycapu. Cil pro pretazeni akce, klik = vyber."""

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.assigned = None
        self.selected = False
        self.on_click = None     # nastavi DeviceDetailPage
        self.on_remove = None    # nastavi DeviceDetailPage
        self.on_dropped = None   # nastavi DeviceDetailPage - zavola se po uspesnem pretazeni
        self._drag_hover = False
        self.setFixedSize(80, 80)
        self.setCursor(Qt.PointingHandCursor)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel(str(index + 1))
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.title_label = QLabel("")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.title_label.setVisible(False)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)

        self._apply_style()

    def assign(self, action: dict):
        self.assigned = action
        self._apply_style()
        self.setToolTip(action.get("title") or action["name"])

    def clear(self):
        self.assigned = None
        self._apply_style()
        self.setToolTip("")

    def set_selected(self, selected: bool):
        self.selected = selected
        self._apply_style()

    def _show_context_menu(self, pos):
        if self.assigned is None:
            return
        menu = QMenu(self)
        remove_action = menu.addAction("Odebrat")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == remove_action:
            self._confirm_and_remove()

    def _confirm_and_remove(self):
        answer = QMessageBox.question(
            self, "Odebrat akci",
            f"Opravdu chceš odebrat přiřazenou akci z tlačítka {self.index + 1}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.clear()
            if self.on_remove:
                self.on_remove()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(ACTION_MIME_TYPE):
            event.acceptProposedAction()
            self._drag_hover = True
            self._apply_style()

    def dragLeaveEvent(self, event):
        self._drag_hover = False
        self._apply_style()

    def dropEvent(self, event):
        if event.mimeData().hasFormat(ACTION_MIME_TYPE):
            raw = bytes(event.mimeData().data(ACTION_MIME_TYPE)).decode("utf-8")
            self.assign(json.loads(raw))
            event.acceptProposedAction()
            if self.on_dropped:
                self.on_dropped()
        self._drag_hover = False
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.on_click:
            self.on_click(self)
        super().mousePressEvent(event)

    def _apply_style(self):
        if self.selected:
            border = BLUE_SELECTED
        elif self.assigned:
            border = ORANGE
        else:
            border = OUTLINE
        bg = "rgba(255,255,255,0.10)" if self._drag_hover else "transparent"
        text_color = TEXT if self.assigned else TEXT_MUTED

        if self.assigned:
            self.icon_label.setText(self.assigned["icon"])
            title = (self.assigned.get("title") or "").strip()
            self.title_label.setText(title)
            self.title_label.setVisible(bool(title))
        else:
            self.icon_label.setText(str(self.index + 1))
            self.title_label.setText("")
            self.title_label.setVisible(False)

        self.icon_label.setStyleSheet(f"color: {text_color}; font-size: 20px; background: transparent; border: none;")
        self.title_label.setStyleSheet(f"color: {text_color}; font-size: 9px; background: transparent; border: none;")

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1.5px solid {border};
                border-radius: 12px;
            }}
        """)


class EncoderDial(QFrame):
    """Jeden enkoder - kolecko. Stejny princip jako Keycap (pretazeni = prirazeni, klik = vyber)."""

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.assigned = None
        self.selected = False
        self.on_click = None    # nastavi DeviceDetailPage
        self.on_remove = None
        self.on_dropped = None
        self._drag_hover = False
        self.setFixedSize(70, 70)
        self.setCursor(Qt.PointingHandCursor)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.title_label = QLabel("")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.title_label.setVisible(False)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)

        self._apply_style()

    def assign(self, action: dict):
        self.assigned = action
        self._apply_style()
        self.setToolTip(action.get("title") or action["name"])

    def clear(self):
        self.assigned = None
        self._apply_style()
        self.setToolTip("")

    def set_selected(self, selected: bool):
        self.selected = selected
        self._apply_style()

    def _show_context_menu(self, pos):
        if self.assigned is None:
            return
        menu = QMenu(self)
        remove_action = menu.addAction("Odebrat")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == remove_action:
            self._confirm_and_remove()

    def _confirm_and_remove(self):
        answer = QMessageBox.question(
            self, "Odebrat akci",
            f"Opravdu chceš odebrat přiřazenou akci z enkodéru {self.index + 1}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.clear()
            if self.on_remove:
                self.on_remove()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(ACTION_MIME_TYPE):
            event.acceptProposedAction()
            self._drag_hover = True
            self._apply_style()

    def dragLeaveEvent(self, event):
        self._drag_hover = False
        self._apply_style()

    def dropEvent(self, event):
        if event.mimeData().hasFormat(ACTION_MIME_TYPE):
            raw = bytes(event.mimeData().data(ACTION_MIME_TYPE)).decode("utf-8")
            self.assign(json.loads(raw))
            event.acceptProposedAction()
            if self.on_dropped:
                self.on_dropped()
        self._drag_hover = False
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.on_click:
            self.on_click(self)
        super().mousePressEvent(event)

    def _apply_style(self):
        if self.selected:
            border = BLUE_SELECTED
        elif self.assigned:
            border = ORANGE
        else:
            border = OUTLINE
        bg = "rgba(255,255,255,0.10)" if self._drag_hover else "transparent"
        text_color = TEXT if self.assigned else TEXT_MUTED

        if self.assigned:
            self.icon_label.setText(self.assigned["icon"])
            title = (self.assigned.get("title") or "").strip()
            self.title_label.setText(title)
            self.title_label.setVisible(bool(title))
        else:
            self.icon_label.setText(f"E{self.index + 1}")
            self.title_label.setText("")
            self.title_label.setVisible(False)

        self.icon_label.setStyleSheet(f"color: {text_color}; font-size: 15px; border: none; background: transparent;")
        self.title_label.setStyleSheet(f"color: {text_color}; font-size: 8px; border: none; background: transparent;")
        self.setStyleSheet(f"""
            QFrame {{ background-color: {bg}; border: 1.5px solid {border}; border-radius: 35px; }}
        """)


class DeviceOutline(QWidget):
    """
    Obrys PeciDecku: 4x2 tlacitka, displej, 3 enkodery. Prirozena vyska
    podle obsahu (zadny vlastni "stretch"), aby navigace stranek hned
    pod tim navazovala bez velke mezery.
    """

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(28)

        grid_wrap = QFrame()
        grid_wrap.setStyleSheet(f"QFrame {{ border: 1.5px solid {OUTLINE}; border-radius: 20px; }}")
        grid_layout = QGridLayout(grid_wrap)
        grid_layout.setSpacing(14)
        grid_layout.setContentsMargins(24, 24, 24, 24)

        self.keycaps = []
        for i in range(8):
            row, col = divmod(i, 4)  # 2 rady x 4 sloupce = 4x2 podle zadani
            key = Keycap(i)
            self.keycaps.append(key)
            grid_layout.addWidget(key, row, col)

        display = QFrame()
        display.setFixedSize(300, 60)
        display.setStyleSheet(f"QFrame {{ border: 1.5px solid {OUTLINE}; border-radius: 10px; }}")
        display_layout = QVBoxLayout(display)
        display_label = QLabel("Displej")
        display_label.setAlignment(Qt.AlignCenter)
        display_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; border: none; background: transparent;")
        display_layout.addWidget(display_label)

        encoders_row = QHBoxLayout()
        encoders_row.setSpacing(20)
        encoders_row.addStretch()
        self.encoders = [EncoderDial(i) for i in range(3)]
        for enc in self.encoders:
            encoders_row.addWidget(enc)
        encoders_row.addStretch()

        layout.addWidget(grid_wrap, alignment=Qt.AlignCenter)
        layout.addWidget(display, alignment=Qt.AlignCenter)
        layout.addLayout(encoders_row)


class PageNavBar(QWidget):
    """
    Navigacni panel pod mrizkou tlacitek: <, cisla stranek (1,2,3...), +, >.
    "+" se deaktivuje po dosazeni MAX_PAGES stranek.
    """

    def __init__(self, on_page_selected, on_add_page):
        super().__init__()
        self._on_page_selected = on_page_selected
        self._on_add_page = on_add_page
        self._page_buttons = []
        self._current_index = 0

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 16, 0, 8)
        root.setAlignment(Qt.AlignCenter)
        root.setSpacing(8)

        self.prev_btn = QPushButton("\u2039")
        self.next_btn = QPushButton("\u203A")
        for arrow_btn in (self.prev_btn, self.next_btn):
            arrow_btn.setCursor(Qt.PointingHandCursor)
            arrow_btn.setFixedSize(28, 28)
            arrow_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: 1px solid rgba(255,255,255,0.2);
                    border-radius: 14px; color: {TEXT_MUTED}; font-size: 15px; font-weight: 700;
                }}
                QPushButton:hover {{ background-color: rgba(255,255,255,0.06); }}
                QPushButton:disabled {{ color: rgba(255,255,255,0.15); border-color: rgba(255,255,255,0.08); }}
            """)
        self.prev_btn.clicked.connect(lambda: self._on_page_selected(self._current_index - 1))
        self.next_btn.clicked.connect(lambda: self._on_page_selected(self._current_index + 1))

        self.add_btn = QPushButton("+")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setFixedSize(28, 28)
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid rgba(255,255,255,0.2);
                border-radius: 14px; color: {TEXT_MUTED}; font-size: 14px;
            }}
            QPushButton:hover {{ background-color: rgba(255,255,255,0.06); }}
            QPushButton:disabled {{ color: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.06); }}
        """)
        self.add_btn.clicked.connect(self._on_add_page)

        self._pills_layout = QHBoxLayout()
        self._pills_layout.setSpacing(8)

        root.addWidget(self.prev_btn)
        root.addLayout(self._pills_layout)
        root.addWidget(self.add_btn)
        root.addWidget(self.next_btn)

        self.set_page_count(1)

    def set_page_count(self, count: int):
        for btn in self._page_buttons:
            self._pills_layout.removeWidget(btn)
            btn.deleteLater()
        self._page_buttons = []

        for i in range(count):
            btn = QPushButton(str(i + 1))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedSize(28, 28)
            btn.clicked.connect(lambda checked=False, idx=i: self._on_page_selected(idx))
            self._page_buttons.append(btn)
            self._pills_layout.addWidget(btn)

        self.add_btn.setEnabled(count < MAX_PAGES)
        self.set_active(min(self._current_index, count - 1))

    def set_active(self, index: int):
        self._current_index = index
        for i, btn in enumerate(self._page_buttons):
            active = i == index
            bg = ORANGE if active else "transparent"
            color = "white" if active else TEXT_MUTED
            border = ORANGE if active else "rgba(255,255,255,0.2)"
            hover = "#e8650f" if active else "rgba(255,255,255,0.06)"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg}; border: 1px solid {border};
                    border-radius: 14px; color: {color}; font-size: 12px; font-weight: 600;
                }}
                QPushButton:hover {{ background-color: {hover}; }}
            """)
        self.prev_btn.setEnabled(index > 0)
        self.next_btn.setEnabled(index < len(self._page_buttons) - 1)


class ConfigPanel(QWidget):
    """
    Panel s nastavenim vybrane akce - jen pod levym sloupcem. Umoznuje
    zadat vlastni Nazev (uklada se a zobrazuje pod ikonkou primo na
    tlacitku/enkoderu), pripadne dalsi pole podle typu akce (URL, cesta
    k aplikaci, text, klavesova zkratka...), a tlacitko Otestovat pro
    akce, ktere jdou spustit primo ze softwaru (bez hardwaru).
    """

    def __init__(self):
        super().__init__()
        self._current_target = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 14, 24, 14)
        root.setSpacing(10)

        self.header_label = QLabel("Vyber tlačítko nebo enkodér")
        self.header_label.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 700;")
        root.addWidget(self.header_label)

        self.fields_layout = QVBoxLayout()
        self.fields_layout.setSpacing(8)
        root.addLayout(self.fields_layout)

        self.setStyleSheet(f"background-color: {BG}; border-top: 1px solid rgba(255,255,255,0.08);")
        self.setMinimumHeight(80)

    def show_for(self, target):
        """target = Keycap nebo EncoderDial (ma atribut .assigned)."""
        self._current_target = target
        self._clear_fields()

        if target is None or target.assigned is None:
            self.header_label.setText("Prázdné – přetáhni sem akci z pravého panelu")
            return

        action = target.assigned
        self.header_label.setText(action.get("title") or action["name"])

        title_row = QHBoxLayout()
        title_row.addWidget(self._muted_label("Název:"))
        title_edit = self._styled_line_edit(action.get("title", ""), action["name"])
        title_edit.editingFinished.connect(lambda a=action, e=title_edit, t=target: self._save_title(a, e, t))
        title_row.addWidget(title_edit)
        self.fields_layout.addLayout(title_row)

        input_type = action.get("input_type")

        if input_type == "url":
            row = QHBoxLayout()
            row.addWidget(self._muted_label("URL:"))
            url_edit = self._styled_line_edit(action.get("value", ""), "https://…")
            url_edit.editingFinished.connect(lambda a=action, e=url_edit: a.update({"value": e.text()}))
            row.addWidget(url_edit)
            self.fields_layout.addLayout(row)

        elif input_type == "path":
            row = QHBoxLayout()
            row.addWidget(self._muted_label("Cesta:"))
            path_edit = self._styled_line_edit(action.get("value", ""), "Cesta k aplikaci")
            path_edit.editingFinished.connect(lambda a=action, e=path_edit: a.update({"value": e.text()}))
            row.addWidget(path_edit)
            browse_btn = QPushButton("Procházet…")
            browse_btn.setCursor(Qt.PointingHandCursor)
            browse_btn.clicked.connect(lambda a=action, e=path_edit: self._browse_for_path(a, e))
            row.addWidget(browse_btn)
            self.fields_layout.addLayout(row)

        elif input_type == "text":
            row = QHBoxLayout()
            row.addWidget(self._muted_label("Text:"))
            text_edit = self._styled_line_edit(action.get("value", ""), "Text k napsání")
            text_edit.editingFinished.connect(lambda a=action, e=text_edit: a.update({"value": e.text()}))
            row.addWidget(text_edit)
            self.fields_layout.addLayout(row)

        elif input_type == "hotkey":
            row = QHBoxLayout()
            row.addWidget(self._muted_label("Zkratka:"))
            hotkey_edit = self._styled_line_edit(action.get("value", ""), "např. ctrl+shift+s")
            hotkey_edit.editingFinished.connect(lambda a=action, e=hotkey_edit: a.update({"value": e.text()}))
            row.addWidget(hotkey_edit)
            self.fields_layout.addLayout(row)

        elif action.get("has_amount"):
            amount_row = QHBoxLayout()
            lo = QLabel("0")
            lo.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            hi = QLabel("100")
            hi.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(50)
            amount_row.addWidget(lo)
            amount_row.addWidget(slider)
            amount_row.addWidget(hi)
            self.fields_layout.addLayout(amount_row)

        if action.get("action_id") in TESTABLE_ACTION_IDS:
            self._add_test_row(action)

    def _save_title(self, action: dict, edit: QLineEdit, target):
        action["title"] = edit.text().strip()
        target.assign(action)  # prekresli ikonku/nazev na samotnem tlacitku/enkoderu
        self.header_label.setText(action.get("title") or action["name"])

    def _muted_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        return label

    def _styled_line_edit(self, value: str, placeholder: str) -> QLineEdit:
        edit = QLineEdit(value)
        edit.setPlaceholderText(placeholder)
        edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: #1c1c1f; border: 1px solid rgba(255,255,255,0.12);
                border-radius: 6px; padding: 4px 8px; color: {TEXT}; font-size: 12px;
            }}
        """)
        return edit

    def _add_test_row(self, action: dict):
        row = QHBoxLayout()
        row.addStretch()
        test_btn = QPushButton("Otestovat")
        test_btn.setCursor(Qt.PointingHandCursor)
        test_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ORANGE}; color: white; border: none;
                border-radius: 6px; padding: 5px 14px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #e8650f; }}
        """)
        test_btn.clicked.connect(lambda checked=False, a=action: self._run_action(a))
        row.addWidget(test_btn)
        self.fields_layout.addLayout(row)

    def _clear_fields(self):
        while self.fields_layout.count():
            item = self.fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                sub = item.layout()
                while sub.count():
                    sub_item = sub.takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().deleteLater()

    def _browse_for_path(self, action: dict, edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(self, "Vyber aplikaci")
        if path:
            edit.setText(path)
            action["value"] = path

    def _run_action(self, action: dict):
        # Bez hardwaru zatim takhle rucne overujeme, ze akce doopravdy neco dela.
        action_id = action.get("action_id")
        value = (action.get("value") or "").strip()

        if action_id == "open_website":
            if value:
                webbrowser.open(value)

        elif action_id == "open_app":
            if not value:
                return
            try:
                if sys.platform == "darwin":
                    subprocess.Popen(["open", value])
                elif sys.platform.startswith("win"):
                    os.startfile(value)  # noqa: only reached on Windows
                else:
                    subprocess.Popen([value])
            except Exception:
                pass

        elif action_id in ("type_text", "hotkey", "media_play_pause", "media_next", "media_prev"):
            if _keyboard is None:
                QMessageBox.warning(
                    self, "Chybí knihovna",
                    "Pro tuhle akci je potřeba nainstalovat knihovnu 'pynput':\n\npip install pynput",
                )
                return
            if action_id == "type_text":
                if value:
                    _keyboard.type(value)
            elif action_id == "hotkey":
                if value:
                    self._press_hotkey(value)
            elif action_id == "media_play_pause":
                self._tap_key(_Key.media_play_pause)
            elif action_id == "media_next":
                self._tap_key(_Key.media_next)
            elif action_id == "media_prev":
                self._tap_key(_Key.media_previous)

    def _tap_key(self, key):
        _keyboard.press(key)
        _keyboard.release(key)

    def _press_hotkey(self, combo: str):
        parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
        if not parts:
            return
        modifiers = []
        final_key = None
        for p in parts:
            if p in HOTKEY_NAME_MAP:
                modifiers.append(getattr(_Key, HOTKEY_NAME_MAP[p]))
            else:
                final_key = p

        for m in modifiers:
            _keyboard.press(m)
        if final_key:
            if len(final_key) == 1:
                _keyboard.press(final_key)
                _keyboard.release(final_key)
            else:
                special = getattr(_Key, final_key, None)
                if special:
                    _keyboard.press(special)
                    _keyboard.release(special)
        for m in reversed(modifiers):
            _keyboard.release(m)


class DeviceDetailPage(QWidget):
    back_requested = Signal()

    def __init__(self):
        super().__init__()
        self.pages = [self._blank_page()]
        self.current_page_index = 0
        self._selected_target = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(24, 20, 24, 12)
        back_btn = QPushButton("\u2190")
        back_btn.setFixedSize(36, 36)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; color: {TEXT}; font-size: 18px; border-radius: 18px; }}
            QPushButton:hover {{ background-color: rgba(255,255,255,0.08); }}
        """)
        back_btn.clicked.connect(self.back_requested.emit)
        self.title_label = QLabel("PeciDeck")
        self.title_label.setStyleSheet(f"color: {TEXT}; font-size: 24px; font-weight: 700; margin-left: 8px;")
        top_bar.addWidget(back_btn)
        top_bar.addWidget(self.title_label)
        top_bar.addStretch()
        root.addLayout(top_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # --- levy sloupec (~80 %): obrys + navigace stranek + konfiguracni panel, zarovnano nahoru ---
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 24, 0, 0)
        left_layout.setSpacing(0)
        left_layout.setAlignment(Qt.AlignTop)

        self.outline = DeviceOutline()
        left_layout.addWidget(self.outline, alignment=Qt.AlignHCenter)

        self.page_nav = PageNavBar(on_page_selected=self._go_to_page, on_add_page=self._add_page)
        left_layout.addWidget(self.page_nav)

        self.config_panel = ConfigPanel()
        left_layout.addWidget(self.config_panel)

        left_layout.addStretch()

        # --- pravy sloupec (~20 %, cela vyska) ---
        self.plugins_panel = PluginsPanel()

        body.addWidget(left_container, stretch=4)
        body.addWidget(self.plugins_panel, stretch=1)
        root.addLayout(body)

        for key in self.outline.keycaps:
            key.on_click = self._select_target
            key.on_remove = lambda k=key: self._on_target_removed(k)
            key.on_dropped = lambda k=key: self._on_keycap_dropped(k)
        for enc in self.outline.encoders:
            enc.on_click = self._select_target
            enc.on_remove = lambda e=enc: self._on_target_removed(e)
            enc.on_dropped = lambda e=enc: self._select_target(e)

        self.setStyleSheet(f"background-color: {BG};")

    def _blank_page(self):
        return [None] * 8

    def set_device_name(self, name: str):
        self.title_label.setText(name)

    def _select_target(self, target):
        if self._selected_target is not None and self._selected_target is not target:
            self._selected_target.set_selected(False)
        self._selected_target = target
        target.set_selected(True)
        self.config_panel.show_for(target)

    def _on_keycap_dropped(self, keycap: Keycap):
        self.pages[self.current_page_index][keycap.index] = keycap.assigned
        self._select_target(keycap)

    def _on_target_removed(self, target):
        if isinstance(target, Keycap):
            self.pages[self.current_page_index][target.index] = None
        if self._selected_target is target:
            self.config_panel.show_for(target)

    def _go_to_page(self, index: int):
        if index < 0 or index >= len(self.pages):
            return
        self.current_page_index = index
        page_data = self.pages[index]
        for i, key in enumerate(self.outline.keycaps):
            action = page_data[i]
            if action:
                key.assign(action)
            else:
                key.clear()
        self.page_nav.set_active(index)
        if self._selected_target in self.outline.keycaps:
            self.config_panel.show_for(self._selected_target)

    def _add_page(self):
        if len(self.pages) >= MAX_PAGES:
            return
        self.pages.append(self._blank_page())
        self.page_nav.set_page_count(len(self.pages))
        self._go_to_page(len(self.pages) - 1)