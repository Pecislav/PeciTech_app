"""
PeciTech plugin - OBS Studio
------------------------------------------------------------------
Skutecny funkcni plugin (ne jen maketa) - pripojuje se na OBS pres
obs-websocket v5 (vestaveny v OBS 28 a novejsich, Tools -> WebSocket
Server Settings v OBS).

INSTALACE:
    pip install obsws-python

JAK FUNGUJE PRIPOJENI (bez rucniho upravovani souboru):
  1. Prvni pokus je vzdy automaticky - localhost:4455, bez hesla. Pokud
     mas v OBS WebSocket server zapnuty bez autentizace, funguje to
     rovnou a nic dalsiho reset nemusis.
  2. Pokud tenhle pokus selze (typicky spatne/chybejici heslo), appka
     sama otevre okno "Nastavení pluginu", kam zadas heslo (pripadne
     port) primo v PySide6 rozhrani - viz plugins_panel.py
     (PluginSettingsDialog) a device_view.py (ConfigPanel._run_action).
  3. Po ulozeni appka rovnou zkusi znovu pripojit (test_connection()) a
     rekne ti, jestli to prošlo.

  Konfigurace se pod kapotou porad uklada do "config.json" vedle tohodle
  souboru, ale ty uz do nej rucne nesahas - jen ho ctou/pisou funkce
  nize podle toho, co zadas v UI appky.

Akce:
  start_stream  - spusti stream
  stop_stream   - zastavi stream
  switch_scene  - prepne na scenu podle nazvu (presne podle OBS)
  mute_mic      - ztlumi/zapne dany zvukovy zdroj (napr. "Mic/Aux")

POZNAMKA: Nazvy metod v obsws-python vychazi z oficialniho obs-websocket
protokolu v5 (napr. StartStream -> start_stream). Detekce "je potreba
heslo" nize je zalozena na hledani slova "auth" v chybove zprave - podle
verze obsws-python se muze presna chybova zprava/typ vyjimky lisit, tak
to pripadne uprav podle toho, co ti to skutecne vyhodi (nemam tu bohuzel
bezici OBS, abych si to overil naziv).
"""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
DEFAULT_CONFIG = {"host": "localhost", "port": 4455, "password": ""}

PLUGIN_INFO = {
    "id": "obs",
    "name": "OBS Studio",
    "icon": "\U0001F3A5",
}

ACTIONS = [
    {"id": "start_stream", "name": "Spustit stream", "icon": "\U0001F534"},
    {"id": "stop_stream", "name": "Zastavit stream", "icon": "\u23F9"},
    {
        "id": "switch_scene", "name": "Přepnout scénu", "icon": "\U0001F3AC",
        "input_type": "text", "placeholder": "Přesný název scény v OBS",
    },
    {
        "id": "mute_mic", "name": "Ztlumit mikrofon", "icon": "\U0001F507",
        "input_type": "text", "placeholder": "Název zdroje, např. Mic/Aux",
    },
]

# --- Nastaveni pluginu - appka podle tohohle sama vykresli dialog (viz
# PluginSettingsDialog v plugins_panel.py). Zadne rucni upravovani souboru. ---
SETTINGS = [
    {"id": "password", "name": "Heslo (OBS WebSocket)", "input_type": "password", "default": ""},
    {"id": "port", "name": "Port", "input_type": "text", "default": "4455"},
]


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return {**DEFAULT_CONFIG, **data}
        except Exception:
            return dict(DEFAULT_CONFIG)
    # Prvni spusteni - vytvor si config potichu s vychozimi hodnotami
    # (localhost:4455, bez hesla), aby fungoval automaticky pokus o pripojeni.
    CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
    return dict(DEFAULT_CONFIG)


def _save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def get_settings() -> dict:
    """Appka tímhle naplní dialog nastavení - viz PluginSettingsDialog."""
    cfg = _load_config()
    return {"password": cfg.get("password", ""), "port": str(cfg.get("port", 4455))}


def save_settings(values: dict) -> None:
    """Appka zavola po kliknuti na 'Uložit a připojit' v dialogu nastavení."""
    cfg = _load_config()
    if "password" in values:
        cfg["password"] = values["password"]
    if "port" in values:
        try:
            cfg["port"] = int(values["port"])
        except (TypeError, ValueError):
            pass
    _save_config(cfg)


def _connect():
    import obsws_python as obs  # dovnitr funkce, aby appka nespadla pri importu, kdyz knihovna chybi

    cfg = _load_config()
    return obs.ReqClient(host=cfg["host"], port=cfg["port"], password=cfg["password"], timeout=3)


def test_connection():
    """Zavola appka hned po ulozeni nastaveni, aby rekla uzivateli, jestli to proslo."""
    try:
        client = _connect()
        client.disconnect()
        return True, ""
    except ImportError:
        return False, "Chybí knihovna 'obsws-python' - nainstaluj: pip install obsws-python"
    except Exception as exc:
        return False, str(exc)


def run(action_id: str, value: str = "") -> None:
    """Appka zavola tuhle funkci pri "Otestovat" (a pozdeji pri skutecnem stisku tlacitka)."""
    try:
        client = _connect()
    except ImportError:
        raise RuntimeError("Chybí knihovna 'obsws-python' - nainstaluj: pip install obsws-python")
    except Exception as exc:
        msg = str(exc)
        if "auth" in msg.lower():
            # Appka na tohle zareaguje rovnou otevrenim okna s nastavenim,
            # misto obycejne chybove hlasky - viz NEEDS_SETTINGS konvence
            # v plugin_loader.run_plugin_action().
            raise RuntimeError(f"NEEDS_SETTINGS: Nepodařilo se přihlásit k OBS - zkontroluj heslo. ({msg})")
        raise RuntimeError(f"Nepodařilo se připojit k OBS (běží a je zapnutý WebSocket server?): {msg}")

    try:
        if action_id == "start_stream":
            client.start_stream()
        elif action_id == "stop_stream":
            client.stop_stream()
        elif action_id == "switch_scene":
            if value.strip():
                client.set_current_program_scene(value.strip())
        elif action_id == "mute_mic":
            input_name = value.strip() or "Mic/Aux"
            client.toggle_input_mute(input_name)
    finally:
        client.disconnect()