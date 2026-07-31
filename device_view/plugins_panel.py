"""
device_view/plugins_panel.py
------------------------------------------------------------------
Prava cast (~20 %) obrazovky detailu zarizeni.

UX (podle Elgato Stream Deck appky): kazdy plugin (OBS, Spotify...)
funguje jako slozka - klikem se "otevre" a uvnitr uvidis konkretni
moduly/akce (napr. u OBS: Spustit stream, Prepnout scenu...). Vyber
konkretni akci (zvyrazni se oranzove), pak klikni na tlacitko/enkoder
v obrysu PeciDecku vlevo - ta konkretni akce (ne cely plugin) se na
nej priradi.

"Navigace" je specialni vestavena kategorie (vzdy dostupna, neni to
stahovatelny plugin) - obsahuje Dalsi/Predchozi stranka, aby slo
prepinat stranky tlacitek stejne jako v Elgato appce.

Enkodery: kliknuti na PRAZDNY enkoder (viz device_view.py) otevre
misto normalniho seznamu slozek rovnou FILTROVANY seznam akci
oznacenych jako "encoder_ok" (napr. hlasitost, posun stopy) - napric
vsemi pluginy, bez nutnosti prochazet slozky. Klik na polozku ji
rovnou priradi danemu enkoderu.

Seznam pluginu/modulu je zatim staticky a vsechny jsou "nainstalovane" -
skutecny system stahovani/instalace jednotlivych pluginu (aby napr.
clovek nemusel mit OBS modul vubec zobrazeny, pokud si ho nestahne)
je vetsi samostatna funkce na priste.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QStackedWidget

from .device_view import BG, TEXT, TEXT_MUTED, ORANGE

CARD_BG = "#1c1c1f"

PLUGINS = [
    {
        "id": "navigation", "name": "Navigace", "icon": "\U0001F9ED", "installed": True, "builtin": True,
        "modules": [
            {"id": "next_page", "name": "Další stránka", "icon": "\u25B6"},
            {"id": "prev_page", "name": "Předchozí stránka", "icon": "\u25C0"},
        ],
    },
    {
        "id": "obs", "name": "OBS Studio", "icon": "\U0001F3A5", "installed": True,
        "modules": [
            {"id": "start_stream", "name": "Spustit stream", "icon": "\U0001F534"},
            {"id": "stop_stream", "name": "Zastavit stream", "icon": "\u23F9"},
            {"id": "switch_scene", "name": "Přepnout scénu", "icon": "\U0001F3AC"},
            {"id": "mute_mic", "name": "Ztlumit mikrofon", "icon": "\U0001F507"},
        ],
    },
    {
        "id": "spotify", "name": "Spotify", "icon": "\U0001F3B5", "installed": True,
        "modules": [
            {"id": "play_pause", "name": "Play / Pauza", "icon": "\u23EF"},
            {"id": "next_track", "name": "Další skladba", "icon": "\u23ED", "encoder_ok": True},
            {"id": "prev_track", "name": "Předchozí skladba", "icon": "\u23EE", "encoder_ok": True},
        ],
    },
    {
        "id": "discord", "name": "Discord", "icon": "\U0001F4AC", "installed": True,
        "modules": [
            {"id": "toggle_mute", "name": "Mute / Unmute", "icon": "\U0001F3A4"},
            {"id": "toggle_deafen", "name": "Deafen", "icon": "\U0001F3A7"},
        ],
    },
    {
        "id": "volume", "name": "Hlasitost", "icon": "\U0001F50A", "installed": True,
        "modules": [
            {"id": "vol_up", "name": "Zvýšit hlasitost", "icon": "\U0001F50A", "encoder_ok": True},
            {"id": "vol_down", "name": "Snížit hlasitost", "icon": "\U0001F509", "encoder_ok": True},
            {"id": "vol_mute", "name": "Ztlumit", "icon": "\U0001F507"},
        ],
    },
    {
        "id": "twitch", "name": "Twitch", "icon": "\U0001F4FA", "installed": True,
        "modules": [
            {"id": "marker", "name": "Přidat marker", "icon": "\U0001F4CD"},
        ],
    },
]


class ListItem(QFrame):
    """Jeden radek v seznamu - plugin (slozka) i konkretni modul/akce pouzivaji stejny vzhled."""

    def __init__(self, icon: str, name: str, on_click):
        super().__init__()
        self.selected = False
        self.on_click = on_click
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(52)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        label = QLabel(f"{icon}  {name}")
        label.setStyleSheet(f"color: {TEXT}; font-size: 13px; background: transparent; border: none;")
        label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(label)

        self._apply_style()

    def mousePressEvent(self, event):
        self.on_click()
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self.selected = selected
        self._apply_style()

    def _apply_style(self):
        border = ORANGE if self.selected else "rgba(255,255,255,0.06)"
        bg = "rgba(255,122,41,0.08)" if self.selected else CARD_BG
        self.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 10px; }}")


class PluginsPanel(QWidget):
    """Dve stranky: seznam pluginu (slozky) a moduly otevreneho pluginu (s tlacitkem zpet)."""

    def __init__(self, on_action_selected):
        super().__init__()
        self._on_action_selected = on_action_selected
        self._open_plugin = None
        self._module_entries = []  # list of (ListItem, module_dict)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 24, 16, 16)
        outer.setSpacing(10)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack)

        # --- stranka 1: seznam pluginu ---
        self.plugins_page = QWidget()
        plugins_layout = QVBoxLayout(self.plugins_page)
        plugins_layout.setContentsMargins(0, 0, 0, 0)
        plugins_layout.setSpacing(10)
        plugins_layout.setAlignment(Qt.AlignTop)

        heading = QLabel("Pluginy")
        heading.setStyleSheet(f"color: {TEXT}; font-size: 16px; font-weight: 700;")
        plugins_layout.addWidget(heading)

        hint = QLabel("Klikni na plugin a vyber\nkonkrétní akci.")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        plugins_layout.addWidget(hint)

        for plugin in PLUGINS:
            item = ListItem(plugin["icon"], plugin["name"], on_click=lambda p=plugin: self._open_plugin_page(p))
            plugins_layout.addWidget(item)

        plugins_layout.addStretch()

        # --- stranka 2: moduly otevreneho pluginu ---
        self.modules_page = QWidget()
        self.modules_layout = QVBoxLayout(self.modules_page)
        self.modules_layout.setContentsMargins(0, 0, 0, 0)
        self.modules_layout.setSpacing(10)
        self.modules_layout.setAlignment(Qt.AlignTop)

        # --- stranka 3: filtrovany seznam pro enkodery (jen "encoder_ok" akce) ---
        self.encoder_page = QWidget()
        self.encoder_layout = QVBoxLayout(self.encoder_page)
        self.encoder_layout.setContentsMargins(0, 0, 0, 0)
        self.encoder_layout.setSpacing(10)
        self.encoder_layout.setAlignment(Qt.AlignTop)
        self._encoder_pick_callback = None

        self.stack.addWidget(self.plugins_page)
        self.stack.addWidget(self.modules_page)
        self.stack.addWidget(self.encoder_page)

        self.setStyleSheet(f"background-color: {BG}; border-left: 1px solid rgba(255,255,255,0.06);")

    def show_encoder_suggestions(self, on_pick):
        """
        Otevre filtrovany seznam jen s akcemi vhodnymi pro otaceni (encoder_ok).
        Klik na polozku rovnou zavola on_pick(action) - encoder se priradi bez
        dalsiho kroku, protoze uz vime, ktereho enkoderu se to tyka.
        """
        self._encoder_pick_callback = on_pick

        while self.encoder_layout.count():
            item = self.encoder_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        back_container = QWidget()
        back_layout = QHBoxLayout(back_container)
        back_layout.setContentsMargins(0, 0, 0, 0)
        back_btn = QPushButton("\u2190 Pluginy")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {TEXT}; font-size: 13px; font-weight: 700; }}"
        )
        back_btn.clicked.connect(lambda: self.stack.setCurrentWidget(self.plugins_page))
        back_layout.addWidget(back_btn)
        back_layout.addStretch()
        self.encoder_layout.addWidget(back_container)

        heading = QLabel("Vhodné pro enkodér")
        heading.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 700;")
        self.encoder_layout.addWidget(heading)

        found_any = False
        for plugin in PLUGINS:
            for module in plugin.get("modules", []):
                if module.get("encoder_ok"):
                    found_any = True
                    item = ListItem(
                        module["icon"], f"{plugin['name']} \u2013 {module['name']}",
                        on_click=lambda m=module, p=plugin: self._pick_for_encoder(m, p),
                    )
                    self.encoder_layout.addWidget(item)

        if not found_any:
            empty = QLabel("Zatím žádné akce vhodné\npro otáčení.")
            empty.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            self.encoder_layout.addWidget(empty)

        self.encoder_layout.addStretch()
        self.stack.setCurrentWidget(self.encoder_page)

    def _pick_for_encoder(self, module: dict, plugin: dict):
        action = {
            "icon": module["icon"],
            "name": f"{plugin['name']} \u2013 {module['name']}",
            "plugin_id": plugin["id"],
            "action_id": module["id"],
        }
        if self._encoder_pick_callback:
            self._encoder_pick_callback(action)
        self.stack.setCurrentWidget(self.plugins_page)

    def _open_plugin_page(self, plugin: dict):
        self._open_plugin = plugin
        self._module_entries = []

        while self.modules_layout.count():
            item = self.modules_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        back_container = QWidget()
        back_layout = QHBoxLayout(back_container)
        back_layout.setContentsMargins(0, 0, 0, 0)
        back_btn = QPushButton(f"\u2190 {plugin['name']}")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {TEXT}; font-size: 13px; font-weight: 700; }}"
        )
        back_btn.clicked.connect(lambda: self.stack.setCurrentWidget(self.plugins_page))
        back_layout.addWidget(back_btn)
        back_layout.addStretch()
        self.modules_layout.addWidget(back_container)

        for module in plugin.get("modules", []):
            item = ListItem(module["icon"], module["name"], on_click=lambda m=module: self._select_module(m))
            self._module_entries.append((item, module))
            self.modules_layout.addWidget(item)

        self.modules_layout.addStretch()
        self.stack.setCurrentWidget(self.modules_page)

    def _select_module(self, module: dict):
        for item, mod in self._module_entries:
            item.set_selected(mod is module)
        self._on_action_selected({
            "icon": module["icon"],
            "name": f"{self._open_plugin['name']} \u2013 {module['name']}",
            "plugin_id": self._open_plugin["id"],
            "action_id": module["id"],
        })