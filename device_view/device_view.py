"""
device_view/device_view.py
------------------------------------------------------------------
Detail zarizeni PeciDeck - otevre se kliknutim na pripojenou dlazdici
na hlavni obrazovce (viz main_window.py). Vlevo (~80% sirky) je lehky
obrys desky - tlacitka jako obrys keycapu (4x2), pod tim displej, pod
tim 3 enkodery. Vpravo (~20%) je seznam pluginu (plugins_panel.py).

Prirazeni pluginu na tlacitko je zatim zjednodusene: klikni na plugin
vpravo (zvyrazni se), pak klikni na tlacitko vlevo - plugin se na nej
priradi (zobrazi se jeho ikonka). Pretahovani (drag & drop) by bylo
prijemnejsi, ale az bude zbytek funkcni.

Odebrani prirazeni: pravy klik na tlacitko/enkoder -> "Odebrat" (stejny
princip jako kontextove menu v Elgato appce).

Enkodery: klik na PRAZDNY enkoder (kdyz nic neni vybrane z beznych
slozek) otevre v pravem panelu filtrovany seznam jen akci vhodnych pro
otaceni (hlasitost, posun stopy...) - viz plugins_panel.py. Kliknuti na
polozku v tomhle filtrovanem seznamu priradi rovnou tomu enkoderu.

Pod mrizkou tlacitek je navigacni panel stranek (<, cisla, +, >) - jako
v Elgato appce. Kazda stranka ma vlastni sadu prirazeni tlacitek; nove
stranky zacinaji prazdne. Enkodery zatim stranky nemaji (nebylo v zadani).
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QFrame, QMenu,
)

BG = "#111113"
TEXT = "#f2f2f0"
TEXT_MUTED = "#9a9aa0"
ORANGE = "#ff7a29"
OUTLINE = "rgba(255,255,255,0.25)"

from .plugins_panel import PluginsPanel  # noqa: E402 (musi byt az po definici barev vyse)


class Keycap(QPushButton):
    """Jedno tlacitko PeciDecku - vzhled jako obrys keycapu, klik = prirazeni vybraneho pluginu."""

    def __init__(self, index: int):
        super().__init__(str(index + 1))
        self.index = index
        self.assigned = None
        self.on_remove = None  # nastavi DeviceDetailPage
        self.setFixedSize(80, 80)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._apply_style()

    def assign(self, plugin: dict):
        self.assigned = plugin
        self._apply_style()
        self.setToolTip(plugin["name"])

    def clear(self):
        self.assigned = None
        self._apply_style()
        self.setToolTip("")

    def _show_context_menu(self, pos):
        if self.assigned is None:
            return
        menu = QMenu(self)
        remove_action = menu.addAction("Odebrat")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == remove_action:
            self.clear()
            if self.on_remove:
                self.on_remove()

    def _apply_style(self):
        border = ORANGE if self.assigned else OUTLINE
        text_color = TEXT if self.assigned else TEXT_MUTED
        self.setText(self.assigned["icon"] if self.assigned else str(self.index + 1))
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1.5px solid {border};
                border-radius: 12px;
                color: {text_color};
                font-size: 20px;
            }}
            QPushButton:hover {{ background-color: rgba(255,255,255,0.04); }}
        """)


class EncoderDial(QFrame):
    """Jeden enkoder - kolecko, klik = prirazeni vybrane akce (stejny princip jako Keycap)."""

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.assigned = None
        self.on_click = None  # nastavi DeviceDetailPage po vytvoreni
        self.on_remove = None
        self.setFixedSize(70, 70)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self._label)

        self._apply_style()

    def assign(self, action: dict):
        self.assigned = action
        self._apply_style()
        self.setToolTip(action["name"])

    def clear(self):
        self.assigned = None
        self._apply_style()
        self.setToolTip("")

    def _show_context_menu(self, pos):
        if self.assigned is None:
            return
        menu = QMenu(self)
        remove_action = menu.addAction("Odebrat")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == remove_action:
            self.clear()
            if self.on_remove:
                self.on_remove()

    def _apply_style(self):
        border = ORANGE if self.assigned else OUTLINE
        text_color = TEXT if self.assigned else TEXT_MUTED
        text = self.assigned["icon"] if self.assigned else f"E{self.index + 1}"
        self._label.setText(text)
        self._label.setStyleSheet(f"color: {text_color}; font-size: 16px; border: none; background: transparent;")
        self.setStyleSheet(f"""
            QFrame {{ background-color: transparent; border: 1.5px solid {border}; border-radius: 35px; }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.on_click:
            self.on_click(self)
        super().mousePressEvent(event)


class DeviceOutline(QWidget):
    """Leva cast (~80%) - obrys PeciDecku: 4x2 tlacitka, displej, 3 enkodery."""

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

        layout.addStretch()
        layout.addWidget(grid_wrap, alignment=Qt.AlignCenter)
        layout.addWidget(display, alignment=Qt.AlignCenter)
        layout.addLayout(encoders_row)
        layout.addStretch()

    def assign_to_button(self, index: int, plugin: dict):
        self.keycaps[index].assign(plugin)


class PageNavBar(QWidget):
    """
    Navigacni panel pod mrizkou tlacitek: <, cisla stranek (1,2,3...), +, >.
    Stejny princip jako v Elgato appce - klik na cislo NEBO na sipku prepne
    aktivni stranku; "+" prida novou (prazdnou) stranku.
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


class DeviceDetailPage(QWidget):
    back_requested = Signal()

    def __init__(self):
        super().__init__()
        self.selected_action = None
        self.pages = [self._blank_page()]
        self.current_page_index = 0

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

        self.outline = DeviceOutline()
        self.plugins_panel = PluginsPanel(on_action_selected=self._on_action_selected)

        body.addWidget(self.outline, stretch=4)   # ~80 %
        body.addWidget(self.plugins_panel, stretch=1)  # ~20 %
        root.addLayout(body)

        self.page_nav = PageNavBar(on_page_selected=self._go_to_page, on_add_page=self._add_page)
        root.addWidget(self.page_nav)

        for key in self.outline.keycaps:
            key.clicked.connect(lambda checked=False, k=key: self._on_keycap_clicked(k))
            key.on_remove = lambda k=key: self._on_keycap_removed(k)
        for enc in self.outline.encoders:
            enc.on_click = self._on_encoder_clicked
            enc.on_remove = lambda e=enc: self._on_encoder_removed(e)

        self.setStyleSheet(f"background-color: {BG};")

    def _blank_page(self):
        return [None] * 8

    def set_device_name(self, name: str):
        self.title_label.setText(name)

    def _on_action_selected(self, action: dict):
        self.selected_action = action

    def _on_keycap_clicked(self, keycap: Keycap):
        # Odebrani uz jde jen pravym klikem -> "Odebrat" (viz Keycap._show_context_menu),
        # aby nedoslo k nechtenemu smazani obycejnym kliknutim.
        if self.selected_action is not None:
            keycap.assign(self.selected_action)
            self.pages[self.current_page_index][keycap.index] = self.selected_action

    def _on_keycap_removed(self, keycap: Keycap):
        self.pages[self.current_page_index][keycap.index] = None

    def _on_encoder_clicked(self, encoder: EncoderDial):
        # Enkodery zatim nejsou soucasti stranek (globalni pro cele zarizeni) - viz poznamka v modulovem docstringu.
        if self.selected_action is not None:
            encoder.assign(self.selected_action)
        elif encoder.assigned is None:
            # Prazdny enkoder + nic vybrane z beznych slozek -> rovnou nabidnout jen akce vhodne pro otaceni.
            self.plugins_panel.show_encoder_suggestions(on_pick=lambda action, e=encoder: e.assign(action))
        # Uz prirazeny enkoder + klik bez vybrane akce -> nic (odebrani je pravym klikem).

    def _on_encoder_removed(self, encoder: EncoderDial):
        pass  # enkodery nejsou v self.pages, encoder.clear() uz vizualne zresetoval stav

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

    def _add_page(self):
        self.pages.append(self._blank_page())
        self.page_nav.set_page_count(len(self.pages))
        self._go_to_page(len(self.pages) - 1)