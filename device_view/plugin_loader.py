"""
device_view/plugin_loader.py
------------------------------------------------------------------
Stahovani a dynamicke nacitani pluginu ze slozky plugins/, presne podle
architektury, kterou jsi navrhl:

  1. STORE_CATALOG nize je seznam pluginu k dispozici v zalozce "Obchod" -
     kazdy ma odkaz na .zip na GitHubu. NAHRAĎ zip_url u kazdeho svoji
     skutecnou GitHub adresou (napr. odkaz na "Source code (zip)" u
     releasu, nebo .../archive/refs/heads/main.zip).
  2. Klik na "Instalovat" (viz plugins_panel.py) zavola download_and_install() -
     stahne ten zip a rozbali ho do plugins/<plugin_id>/.
  3. load_installed_plugins() projde slozku plugins/ a kazdou podslozku
     nacte pres importlib jako Python modul.
  4. Kazdy plugin.py musi definovat:
       PLUGIN_INFO = {"id": ..., "name": ..., "icon": ..., volitelne "version"/"description"}
       ACTIONS = [ {"id", "name", "icon", volitelne "input_type"/"has_amount"/"target"}, ... ]
       def run(action_id: str, value: str = "") -> None: ...
     Presny priklad je v plugins/_example_plugin/plugin.py (ta slozka
     zacina podtrzitkem, takze se needetekuje jako "nainstalovana" -
     je to jen referencni ukazka formatu).

     "version"/"description" se pouzivaji jen k zobrazeni ve spravci
     pluginu (Nastaveni -> Pluginy, viz settings.py) - pokud chybi,
     appka pouzije "—" / prazdny popis.

  Spravce pluginu (Nastaveni -> Pluginy) navic umoznuje plugin
  POVOLIT/ZAKAZAT (bez odinstalovani - viz set_plugin_enabled(), stav
  se uklada do plugins/_disabled.json) a ODINSTALOVAT (smaze slozku -
  viz uninstall_plugin()). Zakazany plugin se v prave panelu na hlavni
  obrazovce (Akce) neukazuje a jeho run() nejde zavolat.

  5. VOLITELNE - pokud plugin potrebuje vlastni nastaveni (heslo, port...),
     muze navic definovat:
       SETTINGS = [ {"id", "name", "input_type" ("text"/"password"), "default"}, ... ]
       def get_settings() -> dict: ...
       def save_settings(values: dict) -> None: ...
       def test_connection() -> tuple[bool, str]: ...
     Kdyz run() narazi na problem, ktery jde vyresit jen tak, ze uzivatel
     neco nastavi (spatne heslo apod.), vyhod RuntimeError se zpravou
     zacinajici "NEEDS_SETTINGS:" - appka pak misto obycejne chybove
     hlasky rovnou otevre dialog s nastavenim (viz plugins/obs/plugin.py).

  6. VOLITELNE - pokud nejaka akce ma mit misto textoveho pole rozbalovaci
     seznam s hodnotami natazenymi primo ze zdroje (napr. nazvy scen v
     OBS), oznac tu akci v ACTIONS jako "input_type": "choice" a plugin
     definuj:
       def get_choices(action_id: str) -> list[str]: ...
     Appka ho zavola pri kazdem otevreni konfiguracniho panelu (a pri
     kliknuti na "Obnovit") - viz plugins/obs/plugin.py (scenu/mikrofony).

BEZPECNOST: tohle spousti kod stazeny z internetu bez sandboxu a bez
overeni puvodu/podpisu. Pro vyvoj/prototyp je to v poradku, ale pred
realnym vydanim produktu by stalo za to aspon overovat, ze zip pochazi
z duveryhodneho zdroje (napr. kontrola SHA256 proti hodnote z vlastniho
"obchodniho" indexu) - zatim to tu neresime, jen o tom vez.

Zname zjednoduseni: stahovani je zatim synchronni (blokuje UI na chvíli
pri instalaci) - u vetsich pluginu by stalo za to presunout to do
vlakna a ukazovat progress, stejne jako detekci HID zarizeni v
main_window.py.
"""

import importlib.util
import io
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"

# --- "Obchod": co jde stahnout, nez je nainstalovane ---
# Zatim jen OBS - az bude hotovy a fakt funkcni, pridame dalsi stejnym zpusobem.
STORE_CATALOG = [
    {
        "id": "obs", "name": "OBS Studio", "icon": "\U0001F3A5",
        "description": "Ovládání OBS Studia přes obs-websocket (stream, scény, mikrofon).",
        "zip_url": "https://github.com/<tvuj-ucet>/pecitech-plugin-obs/archive/refs/heads/main.zip",
    },
]

DISABLED_PATH = PLUGINS_DIR / "_disabled.json"

# plugin_id -> nacteny modul (pristup k run/get_settings/save_settings/test_connection),
# naplni ho load_installed_plugins()
_RUNTIME_REGISTRY = {}


def installed_plugin_ids() -> set:
    if not PLUGINS_DIR.exists():
        return set()
    return {p.name for p in PLUGINS_DIR.iterdir() if p.is_dir() and not p.name.startswith("_")}


def _load_disabled() -> set:
    if DISABLED_PATH.exists():
        try:
            return set(json.loads(DISABLED_PATH.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def _save_disabled(ids: set) -> None:
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    DISABLED_PATH.write_text(json.dumps(sorted(ids), indent=2), encoding="utf-8")


def is_plugin_enabled(plugin_id: str) -> bool:
    return plugin_id not in _load_disabled()


def set_plugin_enabled(plugin_id: str, enabled: bool) -> None:
    """Zapne/vypne plugin bez odinstalovani - viz Nastaveni -> Pluginy (settings.py)."""
    disabled = _load_disabled()
    if enabled:
        disabled.discard(plugin_id)
    else:
        disabled.add(plugin_id)
    _save_disabled(disabled)


def uninstall_plugin(plugin_id: str):
    """Smaze slozku plugins/<plugin_id>/ z disku. Vrati (uspech: bool, chyba: str)."""
    target = PLUGINS_DIR / plugin_id
    if not target.exists():
        return False, "Plugin nenalezen na disku."
    try:
        shutil.rmtree(target)
        disabled = _load_disabled()
        disabled.discard(plugin_id)
        _save_disabled(disabled)
        _RUNTIME_REGISTRY.pop(plugin_id, None)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def download_and_install(plugin_id: str, zip_url: str):
    """Stahne .zip a rozbali ho do plugins/<plugin_id>/. Vrati (uspech: bool, chyba: str)."""
    tmp_dir = PLUGINS_DIR / f"_tmp_{plugin_id}"
    try:
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(zip_url, timeout=20) as response:
            data = response.read()

        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            if not names:
                return False, "Stažený .zip je prázdný."
            top_level = names[0].split("/")[0]
            zf.extractall(tmp_dir)

        extracted_root = tmp_dir / top_level
        target_dir = PLUGINS_DIR / plugin_id
        if target_dir.exists():
            shutil.rmtree(target_dir)
        extracted_root.rename(target_dir)
        return True, ""
    except Exception as exc:
        return False, str(exc)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def load_installed_plugins(include_disabled: bool = False) -> list:
    """
    Projde plugins/, kazdou podslozku nacte pres importlib. Vraci seznam
    ve stejnem tvaru jako vestavene kategorie (Navigace/Systém), takze
    CategorySection v plugins_panel.py nemusi rozlisovat puvod:
      {"id", "name", "icon", "version", "description", "installed": True,
       "enabled": bool, "modules": [...], "has_settings": bool}

    include_disabled=False (vychozi, pouziva prave panel na hlavni
    obrazovce): preskoci zakazane pluginy, ukaze jen povolene.
    include_disabled=True (pouziva Nastaveni -> Pluginy): vrati uplne
    vsechny nainstalovane, aby je slo v UI videt a prepinat.

    Zaroven naplni _RUNTIME_REGISTRY (plugin_id -> modul) pro POVOLENE
    pluginy, aby slo akce skutecne spustit - viz run_plugin_action().
    """
    global _RUNTIME_REGISTRY
    _RUNTIME_REGISTRY = {}
    plugins = []

    if not PLUGINS_DIR.exists():
        return plugins

    disabled_ids = _load_disabled()

    for folder in sorted(PLUGINS_DIR.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        entry_file = folder / "plugin.py"
        if not entry_file.exists():
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"pecitech_plugin_{folder.name}", entry_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            info = getattr(module, "PLUGIN_INFO", {})
            plugin_id = info.get("id", folder.name)
            enabled = plugin_id not in disabled_ids

            if not enabled and not include_disabled:
                continue

            actions = getattr(module, "ACTIONS", [])
            settings_schema = getattr(module, "SETTINGS", [])

            if enabled and getattr(module, "run", None) is not None:
                _RUNTIME_REGISTRY[plugin_id] = module

            plugins.append({
                "id": plugin_id,
                "name": info.get("name", folder.name),
                "icon": info.get("icon", "\U0001F9E9"),
                "version": info.get("version", "—"),
                "description": info.get("description", ""),
                "installed": True,
                "enabled": enabled,
                "modules": actions if enabled else [],
                "has_settings": bool(settings_schema),
            })
        except Exception as exc:
            print(f"[PeciTech] Nepodařilo se načíst plugin '{folder.name}': {exc}")

    return plugins


def get_plugin_module(plugin_id: str):
    """Vrati nacteny modul pluginu (pro pristup k get_settings/save_settings/test_connection), nebo None."""
    return _RUNTIME_REGISTRY.get(plugin_id)


def get_plugin_choices(plugin_id: str, action_id: str) -> list:
    """
    Pro akce s "input_type": "choice" - zavola plugin.get_choices(action_id)
    a vrati seznam retezcu pro rozbalovaci seznam (napr. nazvy scen v OBS).
    Prazdny seznam, kdyz plugin get_choices nema, nebo se neco nepovede
    (napr. OBS zrovna nebezi) - appka pak ukaze prazdny/informativni dropdown.
    """
    module = _RUNTIME_REGISTRY.get(plugin_id)
    if module is None or not hasattr(module, "get_choices"):
        return []
    try:
        return list(module.get_choices(action_id) or [])
    except Exception:
        return []


def run_plugin_action(plugin_id: str, action_id: str, value: str = ""):
    """
    Zavola run() nacteneho pluginu. Vraci (uspech: bool, chyba: str, potrebuje_nastaveni: bool).
    Plugin muze rict "potrebuju nastaveni od uzivatele" tak, ze vyhodi
    RuntimeError, jehoz zprava zacina "NEEDS_SETTINGS:" (viz plugins/obs/plugin.py) -
    appka pak misto obycejne chybove hlasky rovnou otevre dialog s nastavenim pluginu.
    """
    module = _RUNTIME_REGISTRY.get(plugin_id)
    if module is None:
        return False, f"Plugin '{plugin_id}' není načtený (zkus appku restartovat po instalaci).", False
    try:
        module.run(action_id, value)
        return True, "", False
    except Exception as exc:
        message = str(exc)
        needs_settings = message.startswith("NEEDS_SETTINGS:")
        if needs_settings:
            message = message[len("NEEDS_SETTINGS:"):].strip()
        return False, message, needs_settings