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
    QListWidgetItem, QStackedWidget, QComboBox, QFrame, QScrollArea,
    QMessageBox, QCheckBox, QApplication,
)

from device_view import plugin_loader

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


class InstalledPluginCard(QFrame):
    """Karta jednoho nainstalovaneho pluginu: ikona, nazev, verze, popis, Povolit/Odinstalovat."""

    def __init__(self, plugin: dict, on_toggle_enabled, on_uninstall):
        super().__init__()
        self.plugin = plugin
        self.setStyleSheet(f"QFrame {{ background-color: {CARD_BG}; border-radius: 10px; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        title = QLabel(f"{plugin['icon']}  {plugin['name']}  ·  v{plugin.get('version', '—')}")
        title.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700; background: transparent;")
        header_row.addWidget(title)
        header_row.addStretch()
        layout.addLayout(header_row)

        if plugin.get("description"):
            desc = QLabel(plugin["description"])
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;")
            layout.addWidget(desc)

        actions_row = QHBoxLayout()
        enabled_check = QCheckBox("Povoleno")
        enabled_check.setChecked(plugin.get("enabled", True))
        enabled_check.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        enabled_check.toggled.connect(lambda checked, pid=plugin["id"]: on_toggle_enabled(pid, checked))
        actions_row.addWidget(enabled_check)
        actions_row.addStretch()

        uninstall_btn = QPushButton("Odinstalovat")
        uninstall_btn.setCursor(Qt.PointingHandCursor)
        uninstall_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid rgba(255,80,80,0.4); color: #ff6b6b;
                border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: rgba(255,80,80,0.12); }}
        """)
        uninstall_btn.clicked.connect(lambda checked=False, pid=plugin["id"], name=plugin["name"]: on_uninstall(pid, name))
        actions_row.addWidget(uninstall_btn)
        layout.addLayout(actions_row)


class StorePluginCard(QFrame):
    """Karta pluginu v Obchode - jeste nenainstalovany, tlacitko Instalovat stahne .zip z GitHubu."""

    def __init__(self, plugin: dict, on_install):
        super().__init__()
        self.plugin = plugin
        self.setStyleSheet(f"QFrame {{ background-color: {CARD_BG}; border-radius: 10px; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        title = QLabel(f"{plugin['icon']}  {plugin['name']}")
        title.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700; background: transparent;")
        layout.addWidget(title)

        if plugin.get("description"):
            desc = QLabel(plugin["description"])
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;")
            layout.addWidget(desc)

        self.install_btn = QPushButton("Instalovat")
        self.install_btn.setCursor(Qt.PointingHandCursor)
        self.install_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ORANGE}; color: white; border: none;
                border-radius: 6px; padding: 5px 12px; font-size: 11px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #e8650f; }}
        """)
        self.install_btn.clicked.connect(lambda checked=False, p=plugin: on_install(p, self.install_btn))
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.install_btn)
        layout.addLayout(row)


class PluginsManagementSection(QWidget):
    """
    Nastaveni -> Pluginy: dvousloupcova sprava. Vlevo "Moje pluginy"
    (nactene ze slozky plugins/, vcetne zakazanych - jde je tu povolit/
    zakazat/odinstalovat), vpravo "Dostupné ke stažení" (STORE_CATALOG
    minus uz nainstalovane). Presne odpovida tomu, co v pravem panelu na
    hlavni obrazovce chybi - tam uz je jen cisty seznam akci k pretazeni,
    zadna zalozka Obchod (viz plugins_panel.py).
    """

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setAlignment(Qt.AlignTop)

        heading = QLabel("Pluginy")
        heading.setStyleSheet(f"color: {TEXT}; font-size: 22px; font-weight: 700;")
        root.addWidget(heading)

        columns = QHBoxLayout()
        columns.setSpacing(20)

        left_col = QVBoxLayout()
        left_heading = self._sub_heading("Moje pluginy")
        left_col.addWidget(left_heading)
        self.installed_scroll = self._make_scroll_area()
        left_col.addWidget(self.installed_scroll)

        right_col = QVBoxLayout()
        right_heading = self._sub_heading("Dostupné ke stažení")
        right_col.addWidget(right_heading)
        self.store_scroll = self._make_scroll_area()
        right_col.addWidget(self.store_scroll)

        columns.addLayout(left_col, 1)
        columns.addLayout(right_col, 1)
        root.addLayout(columns)

        self._refresh_installed()
        self._refresh_store()

    def _sub_heading(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; font-weight: 600;")
        return label

    def _make_scroll_area(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumHeight(280)
        return scroll

    def _refresh_installed(self):
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 4, 4, 4)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignTop)

        installed = plugin_loader.load_installed_plugins(include_disabled=True)
        if not installed:
            empty = QLabel("Zatím nemáš nainstalovaný\nžádný plugin.")
            empty.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            layout.addWidget(empty)
        for plugin in installed:
            layout.addWidget(InstalledPluginCard(plugin, self._toggle_enabled, self._uninstall))

        layout.addStretch()
        self.installed_scroll.setWidget(inner)

    def _refresh_store(self):
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 4, 4, 4)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignTop)

        installed_ids = plugin_loader.installed_plugin_ids()
        available = [p for p in plugin_loader.STORE_CATALOG if p["id"] not in installed_ids]

        if not available:
            empty = QLabel("Všechny dostupné pluginy\njsou už nainstalované.")
            empty.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            layout.addWidget(empty)
        for plugin in available:
            layout.addWidget(StorePluginCard(plugin, self._install))

        layout.addStretch()
        self.store_scroll.setWidget(inner)

    def _install(self, plugin: dict, button: QPushButton):
        button.setEnabled(False)
        button.setText("Stahuji…")
        QApplication.processEvents()  # aby se "Stahuji…" stihlo vykreslit pred blokujicim stahovanim

        ok, error = plugin_loader.download_and_install(plugin["id"], plugin["zip_url"])

        if not ok:
            button.setEnabled(True)
            button.setText("Instalovat")
            QMessageBox.warning(
                self, "Instalace se nezdařila",
                f"Plugin '{plugin['name']}' se nepodařilo stáhnout/nainstalovat:\n\n{error}",
            )
            return

        self._refresh_installed()
        self._refresh_store()

    def _uninstall(self, plugin_id: str, plugin_name: str):
        answer = QMessageBox.question(
            self, "Odinstalovat plugin",
            f"Opravdu chceš odinstalovat '{plugin_name}'? Smaže se celá jeho složka z disku "
            "a všechna přiřazení jeho akcí na tlačítkách/enkodérech přestanou fungovat.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        ok, error = plugin_loader.uninstall_plugin(plugin_id)
        if not ok:
            QMessageBox.warning(self, "Odinstalace se nezdařila", error or "Neznámá chyba.")
            return
        self._refresh_installed()
        self._refresh_store()

    def _toggle_enabled(self, plugin_id: str, enabled: bool):
        plugin_loader.set_plugin_enabled(plugin_id, enabled)


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
        self.content_stack.addWidget(self._wrap(PluginsManagementSection()))
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