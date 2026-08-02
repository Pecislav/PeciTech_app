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
       PLUGIN_INFO = {"id": ..., "name": ..., "icon": ...}
       ACTIONS = [ {"id", "name", "icon", volitelne "input_type"/"has_amount"}, ... ]
       def run(action_id: str, value: str = "") -> None: ...
     Presny priklad je v plugins/_example_plugin/plugin.py (ta slozka
     zacina podtrzitkem, takze se needetekuje jako "nainstalovana" -
     je to jen referencni ukazka formatu).

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
import shutil
import urllib.request
import zipfile
from pathlib import Path

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"

# --- "Obchod": co jde stahnout, nez je nainstalovane ---
# zip_url jsou zatim placeholdery - nahrad je realnymi GitHub adresami.
STORE_CATALOG = [
    {
        "id": "obs", "name": "OBS Studio", "icon": "\U0001F3A5",
        "zip_url": "https://github.com/<tvuj-ucet>/pecitech-plugin-obs/archive/refs/heads/main.zip",
    },
    {
        "id": "spotify", "name": "Spotify", "icon": "\U0001F3B5",
        "zip_url": "https://github.com/<tvuj-ucet>/pecitech-plugin-spotify/archive/refs/heads/main.zip",
    },
    {
        "id": "discord", "name": "Discord", "icon": "\U0001F4AC",
        "zip_url": "https://github.com/<tvuj-ucet>/pecitech-plugin-discord/archive/refs/heads/main.zip",
    },
    {
        "id": "volume", "name": "Hlasitost", "icon": "\U0001F50A",
        "zip_url": "https://github.com/<tvuj-ucet>/pecitech-plugin-volume/archive/refs/heads/main.zip",
    },
    {
        "id": "twitch", "name": "Twitch", "icon": "\U0001F4FA",
        "zip_url": "https://github.com/<tvuj-ucet>/pecitech-plugin-twitch/archive/refs/heads/main.zip",
    },
]

# plugin_id -> run(action_id, value) callable, naplni ho load_installed_plugins()
_RUNTIME_REGISTRY = {}


def installed_plugin_ids() -> set:
    if not PLUGINS_DIR.exists():
        return set()
    return {p.name for p in PLUGINS_DIR.iterdir() if p.is_dir() and not p.name.startswith("_")}


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


def load_installed_plugins() -> list:
    """
    Projde plugins/, kazdou podslozku nacte pres importlib. Vraci seznam
    ve stejnem tvaru jako vestavene kategorie (Navigace/Systém), takze
    CategorySection v plugins_panel.py nemusi rozlisovat puvod:
      {"id", "name", "icon", "installed": True, "modules": [...]}
    Zaroven naplni _RUNTIME_REGISTRY (plugin_id -> run()), aby slo akce
    skutecne spustit - viz run_plugin_action().
    """
    global _RUNTIME_REGISTRY
    _RUNTIME_REGISTRY = {}
    plugins = []

    if not PLUGINS_DIR.exists():
        return plugins

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
            actions = getattr(module, "ACTIONS", [])
            run_fn = getattr(module, "run", None)

            if run_fn is not None:
                _RUNTIME_REGISTRY[plugin_id] = run_fn

            plugins.append({
                "id": plugin_id,
                "name": info.get("name", folder.name),
                "icon": info.get("icon", "\U0001F9E9"),
                "installed": True,
                "modules": actions,
            })
        except Exception as exc:
            print(f"[PeciTech] Nepodařilo se načíst plugin '{folder.name}': {exc}")

    return plugins


def run_plugin_action(plugin_id: str, action_id: str, value: str = ""):
    """Zavola run() nactenho pluginu. Vraci (uspech: bool, chyba: str)."""
    run_fn = _RUNTIME_REGISTRY.get(plugin_id)
    if run_fn is None:
        return False, f"Plugin '{plugin_id}' není načtený (zkus appku restartovat po instalaci)."
    try:
        run_fn(action_id, value)
        return True, ""
    except Exception as exc:
        return False, str(exc)