"""
device_view/persistence.py
------------------------------------------------------------------
Ukladani/nacitani kompletniho stavu vsech stranek (tlacitka + enkodery)
do user_config.json v korenu projektu, aby prirazeni prezila restart
appky. DeviceDetailPage (device_view.py) vola save_pages() po kazde
zmene (pretazeni akce, odebrani, zmena nazvu/hodnoty v konfiguracnim
panelu, pridani/odebrani stranky) a load_pages() jednou pri startu.

Format souboru:
    {"pages": [ {"buttons": [akce nebo null, ...8], "encoders": [...3]}, ... ]}

Kazda "akce" je presne ten slovnik, co uz appka pouziva bezne (icon,
name, plugin_id, action_id, ...), takze zadny extra prevod netreba -
je to uplne stejna struktura jako DeviceDetailPage.pages v pameti.
"""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "user_config.json"


def save_pages(pages: list) -> None:
    try:
        CONFIG_PATH.write_text(
            json.dumps({"pages": pages}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[PeciTech] Uložení nastavení selhalo: {exc}")


def load_pages():
    """
    Vrati seznam stranek nactenych ze souboru, nebo None kdyz soubor
    neexistuje / je poskozeny / prazdny - v tom pripade appka zacne s
    jednou prazdnou strankou jako doted.
    """
    if not CONFIG_PATH.exists():
        return None
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        pages = data.get("pages")
        if not isinstance(pages, list) or not pages:
            return None
        return pages
    except Exception as exc:
        print(f"[PeciTech] Načtení nastavení selhalo, začínám s prázdnou konfigurací: {exc}")
        return None