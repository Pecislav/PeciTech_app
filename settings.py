"""
PeciTech - stranka Nastaveni (PySide6)
------------------------------------------------------------------
Vklada se primo do hlavniho okna pres QStackedWidget (viz main_window.py) -
NENI to samostatny popup/dialog. Sipka vlevo nahore posle signal
back_requested, na ktery hlavni okno reaguje prepnutim zpet na uvodni
obrazovku.

Layout inspirovany "Application Settings" z Logi Options+: leva lista
sekci + prava strana s obsahem vybrane sekce.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QStackedWidget, QComboBox, QFrame,
)

# Stejne barvy jako v main_window.py - pri zmene tam, zmenit i tady.
BG = "#111113"
CARD_BG = "#1c1c1f"
SIDEBAR_BG = "#0d0d0f"
ORANGE = "#ff7a29"
TEXT = "#f2f2f0"
TEXT_MUTED = "#9a9aa0"


class ThemeSwatch(QFrame):
    """Nahled tematu - zatim jen vizualni volba, realne prepinani tematu doresime pristi verzi."""

    def __init__(self, label: str, selected: bool = False):
        super().__init__()
        self.setFixedSize(120, 80)
        self.setCursor(Qt.PointingHandCursor)
        border = ORANGE if selected else "rgba(255,255,255,0.12)"
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 2px solid {border};
                border-radius: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.addStretch()
        text = QLabel(label)
        text.setAlignment(Qt.AlignCenter)
        text.setStyleSheet(f"color: {TEXT}; font-size: 11px; border: none; background: transparent;")
        layout.addWidget(text)


class GeneralSection(QWidget):
    """Obecne: jazyk, motiv, chovani appky, profily."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)

        heading = QLabel("Obecné")
        heading.setStyleSheet(f"color: {TEXT}; font-size: 22px; font-weight: 700;")
        layout.addWidget(heading)

        layout.addWidget(self._section_label("Jazyk aplikace"))
        lang = QComboBox()
        lang.addItems(["Čeština", "English"])
        lang.setFixedWidth(220)
        layout.addWidget(lang)

        layout.addWidget(self._section_label("Motiv"))
        themes_row = QHBoxLayout()
        themes_row.addWidget(ThemeSwatch("Systémové"))
        themes_row.addWidget(ThemeSwatch("Černo/oranžové", selected=True))
        themes_row.addWidget(ThemeSwatch("Bílo/oranžové"))
        themes_row.addStretch()
        layout.addLayout(themes_row)

        layout.addWidget(self._section_label("Chování aplikace"))
        for text in ["Spustit při startu systému", "Spustit v pozadí", "Zobrazovat oznámení"]:
            row = QHBoxLayout()
            row.addWidget(QLabel(text))
            row.addStretch()
            layout.addLayout(row)

        layout.addWidget(self._section_label("Profily"))
        profiles_row = QHBoxLayout()
        for text in ["Exportovat profil", "Importovat profil", "Tovární reset"]:
            btn = QPushButton(text)
            btn.setCursor(Qt.PointingHandCursor)
            profiles_row.addWidget(btn)
        profiles_row.addStretch()
        layout.addLayout(profiles_row)

        layout.addStretch()

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; font-weight: 600; margin-top: 6px;")
        return lbl


class PlaceholderSection(QWidget):
    """Docasny obsah pro sekce, co jeste nejsou hotove."""

    def __init__(self, title: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        heading = QLabel(title)
        heading.setStyleSheet(f"color: {TEXT}; font-size: 22px; font-weight: 700;")
        layout.addWidget(heading)
        note = QLabel("(obsah přidáme v další verzi)")
        note.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; margin-top: 8px;")
        layout.addWidget(note)
        layout.addStretch()


class SettingsPage(QWidget):
    back_requested = Signal()

    SECTIONS = ["Obecné", "Aktualizace", "Pluginy", "Support"]

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- horni lista se sipkou zpet ---
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
        title = QLabel("Nastavení")
        title.setStyleSheet(f"color: {TEXT}; font-size: 24px; font-weight: 700; margin-left: 8px;")
        top_bar.addWidget(back_btn)
        top_bar.addWidget(title)
        top_bar.addStretch()
        root.addLayout(top_bar)

        # --- telo: bocni lista + obsah ---
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(200)
        self.nav_list.setStyleSheet(f"""
            QListWidget {{ background-color: {SIDEBAR_BG}; border: none; padding-top: 8px; }}
            QListWidget::item {{ color: {TEXT_MUTED}; padding: 10px 20px; font-size: 13px; }}
            QListWidget::item:selected {{
                color: {ORANGE}; background-color: rgba(255,122,41,0.08); border-left: 3px solid {ORANGE};
            }}
        """)
        for section in self.SECTIONS:
            QListWidgetItem(section, self.nav_list)
        self.nav_list.currentRowChanged.connect(self._on_section_changed)

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self._wrap(GeneralSection()))
        self.content_stack.addWidget(self._wrap(PlaceholderSection("Aktualizace")))
        self.content_stack.addWidget(self._wrap(PlaceholderSection("Pluginy")))
        self.content_stack.addWidget(self._wrap(PlaceholderSection("Support")))

        body.addWidget(self.nav_list)
        body.addWidget(self.content_stack, stretch=1)
        root.addLayout(body)

        self.nav_list.setCurrentRow(0)
        self.setStyleSheet(f"background-color: {BG};")

    def _wrap(self, widget: QWidget) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 16, 28, 16)
        layout.addWidget(widget)
        return container

    def _on_section_changed(self, index: int):
        self.content_stack.setCurrentIndex(index)