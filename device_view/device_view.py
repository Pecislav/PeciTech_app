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
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QFrame,
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
        self.setFixedSize(80, 80)
        self.setCursor(Qt.PointingHandCursor)
        self._apply_style()

    def assign(self, plugin: dict):
        self.assigned = plugin
        self._apply_style()
        self.setToolTip(plugin["name"])

    def clear(self):
        self.assigned = None
        self._apply_style()
        self.setToolTip("")

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
    """Jeden enkoder - kolecko s cislem (klikatelnost pro prirazeni pridame stejne jako u Keycap pozdeji)."""

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.setFixedSize(70, 70)
        self.setStyleSheet(f"""
            QFrame {{ background-color: transparent; border: 1.5px solid {OUTLINE}; border-radius: 35px; }}
        """)
        layout = QVBoxLayout(self)
        label = QLabel(f"E{index + 1}")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px; border: none; background: transparent;")
        layout.addWidget(label)


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


class DeviceDetailPage(QWidget):
    back_requested = Signal()

    def __init__(self):
        super().__init__()
        self.selected_action = None

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

        for key in self.outline.keycaps:
            key.clicked.connect(lambda checked=False, k=key: self._on_keycap_clicked(k))

        self.setStyleSheet(f"background-color: {BG};")

    def set_device_name(self, name: str):
        self.title_label.setText(name)

    def _on_action_selected(self, action: dict):
        self.selected_action = action

    def _on_keycap_clicked(self, keycap: Keycap):
        if self.selected_action is not None:
            keycap.assign(self.selected_action)
        elif keycap.assigned is not None:
            keycap.clear()