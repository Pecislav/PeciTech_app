"""
PeciTech - hlavni okno aplikace (PySide6)
------------------------------------------------------------------
Cerno/oranzovy design inspirovany Logi Options+ a vlastnim navrhem
uvodni obrazovky ("Moje Zařízení" - viz screenshot/kresba, co jsi poslal):
velky nadpis + podnadpis, karta pripojeneho zarizeni s malym nahledem
desky (ktery kopiruje realne priradene ikonky z prvni stranky) a
tlacitkem "Konfigurovat", + kostkovana karta "Přidat nové zařízení" s
tlacitkem "Skenovat".

Zavislosti:
    pip install PySide6 hidapi

Spusteni:
    python main_window.py

Testovani BEZ hardwaru:
    PECITECH_MOCK=1 python main_window.py
    (na Windows v PowerShellu: $env:PECITECH_MOCK=1; python main_window.py)

  Appka pak po ~3 vterinach "najde" simulovany PeciDeck (bez realneho HID)
  - takze muzeme delat a testovat cely zbytek appky, i kdyz fyzicka deska
    jeste nedorazila.

DULEZITE - VID/PID:
  Docasne testovaci PID pod Espressif VID (0x303A) - musi sedet s
  firmwarem (PeciDeck_MK1_firmware_HID.ino). Pred prodejem produktu
  pozadej o oficialni PID: https://github.com/espressif/usb-pids

Soubory:
  main_window.py - tohle - hlavni okno, karty zarizeni, detekce HID
  settings.py     - stranka nastaveni (vklada se do stejneho okna pres
                    QStackedWidget, neni to samostatny dialog/okno)
  device_view/    - detail zarizeni (mrizka tlacitek/enkoderu, pluginy)
"""

import os
import sys
import threading
import time

from PySide6.QtCore import Qt, QObject, Signal, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QFont, QColor, QPainter
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QGraphicsOpacityEffect,
    QGraphicsDropShadowEffect,
)

from settings import SettingsPage
from device_view.device_view import DeviceDetailPage

try:
    import hid
except ImportError:
    hid = None

MOCK_MODE = os.environ.get("PECITECH_MOCK") == "1"

# ---------- Barvy (cerno/oranzove) - settings.py ma stejne hodnoty, pri zmene upravit oboje ----------
BG = "#111113"
CARD_BG = "#1c1c1f"
CARD_BORDER = "rgba(255,255,255,0.06)"
DECK_BG = "#0d0d0f"
ORANGE = "#ff7a29"
TEXT = "#f2f2f0"
TEXT_MUTED = "#9a9aa0"

# ---------- Protokol (musi sedet s firmwarem) ----------
VENDOR_ID = 0x303A
PRODUCT_ID = 0x8123

REPORT_LEN = 64
MSG_INPUT_STATE = 0x01
MSG_CAPABILITIES = 0x02
MSG_REQUEST_CAPS = 0x10
MSG_SET_DISPLAY_TEXT = 0x20


class DeviceWatcher(QObject):
    """Bezi na pozadi ve vlastnim vlaknu a hlida pripojeni/odpojeni PeciDecku pres realny USB HID."""
    device_connected = Signal(dict)
    device_disconnected = Signal()

    def __init__(self):
        super().__init__()
        self._running = True
        self._connected = False

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            if hid is None:
                time.sleep(1)
                continue
            devices = [d for d in hid.enumerate()
                       if d["vendor_id"] == VENDOR_ID and d["product_id"] == PRODUCT_ID]
            if devices and not self._connected:
                caps = self._try_connect()
                if caps is not None:
                    self._connected = True
                    self.device_connected.emit(caps)
            elif not devices and self._connected:
                self._connected = False
                self.device_disconnected.emit()
            time.sleep(1)

    def _try_connect(self):
        try:
            dev = hid.device()
            dev.open(VENDOR_ID, PRODUCT_ID)
            dev.set_nonblocking(1)
            request = bytes([MSG_REQUEST_CAPS]) + bytes(REPORT_LEN - 1)
            dev.write(bytes([0]) + request)
            deadline = time.time() + 1.0
            while time.time() < deadline:
                data = dev.read(REPORT_LEN)
                if data and data[0] == MSG_CAPABILITIES:
                    return {
                        "name": "PeciDeck MK.1",
                        "num_buttons": data[1],
                        "num_encoders": data[2],
                        "has_display": bool(data[3]),
                        "fw_version": f"{data[4]}.{data[5]}.{data[6]}",
                        "model_id": data[7],
                    }
                time.sleep(0.05)
            return {"name": "PeciDeck"}
        except Exception:
            return None


class MockDeviceWatcher(QObject):
    """
    Simulovane zarizeni pro vyvoj appky bez fyzickeho hardwaru.
    Stejne signaly jako DeviceWatcher, takze zbytek appky nepozna rozdil.
    Spustit s: PECITECH_MOCK=1 python main_window.py
    """
    device_connected = Signal(dict)
    device_disconnected = Signal()

    def __init__(self):
        super().__init__()
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        time.sleep(3)  # simulace doby hledani
        if not self._running:
            return
        self.device_connected.emit({
            "name": "PeciDeck MK.1 (mock)",
            "num_buttons": 8,
            "num_encoders": 3,
            "has_display": True,
            "fw_version": "1.0.1 Beta",
            "model_id": 1,
        })
        while self._running:
            time.sleep(1)


class AnimatedCard(QFrame):
    """
    Karta s plynulym zesvetlenim pri najeti mysi - pruhledny bily overlay,
    jehoz opacity se animuje pres QPropertyAnimation.
    """

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self._overlay = QWidget(self)
        self._overlay.setStyleSheet("background-color: white; border-radius: 16px;")
        self._overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._effect = QGraphicsOpacityEffect(self._overlay)
        self._effect.setOpacity(0.0)
        self._overlay.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity")
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.setGeometry(self.rect())

    def enterEvent(self, event):
        self._animate_to(0.06)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_to(0.0)
        super().leaveEvent(event)

    def _animate_to(self, value):
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(value)
        self._anim.start()


class LoadingBar(QWidget):
    """Tenka oranzova linka jezdici zleva doprava - klasicky loading indikator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(3)
        self._bar_x = 0.0
        self._anim = QPropertyAnimation(self, b"barX")
        self._anim.setDuration(1100)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.InOutSine)
        self._anim.setLoopCount(-1)

    def start(self):
        self._anim.start()

    def stop(self):
        self._anim.stop()

    def getBarX(self):
        return self._bar_x

    def setBarX(self, value):
        self._bar_x = value
        self.update()

    barX = Property(float, getBarX, setBarX)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(CARD_BG))
        bar_w = max(30, int(self.width() * 0.22))
        x = int(self._bar_x * max(1, self.width() - bar_w))
        painter.fillRect(x, 0, bar_w, self.height(), QColor(ORANGE))


class MiniDeckPreview(QWidget):
    """
    Maly nahled PeciDecku uvnitr karty zarizeni - 4x2 mrizka + 3 enkodery,
    kopiruje realne priradene ikonky z prvni stranky (viz DeviceDetailPage.pages[0]).
    Cistě vizualni, neni interaktivni.
    """

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignCenter)

        body = QFrame()
        body.setStyleSheet(f"QFrame {{ background-color: {DECK_BG}; border-radius: 14px; }}")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(14, 14, 14, 14)
        body_layout.setSpacing(10)

        grid_wrap = QWidget()
        grid = QGridLayout(grid_wrap)
        grid.setSpacing(6)
        self.key_labels = []
        for i in range(8):
            row, col = divmod(i, 4)
            lbl = QLabel("")
            lbl.setFixedSize(28, 28)
            lbl.setAlignment(Qt.AlignCenter)
            self.key_labels.append(lbl)
            grid.addWidget(lbl, row, col)

        encoders_col = QVBoxLayout()
        encoders_col.setSpacing(6)
        self.encoder_dots = []
        for _ in range(3):
            dot = QLabel("")
            dot.setFixedSize(20, 20)
            dot.setStyleSheet(
                "background-color: #1c1c1f; border: 1.5px solid rgba(255,255,255,0.15); border-radius: 10px;"
            )
            self.encoder_dots.append(dot)
            encoders_col.addWidget(dot)

        body_layout.addWidget(grid_wrap)
        body_layout.addLayout(encoders_col)
        outer.addWidget(body)

        self.set_icons([None] * 8)

    def set_icons(self, icons):
        """icons: seznam 8 polozek (retezec ikonky, nebo None pro prazdne tlacitko)."""
        for i, label in enumerate(self.key_labels):
            icon = icons[i] if i < len(icons) else None
            if icon:
                label.setText(icon)
                label.setStyleSheet(f"""
                    background-color: rgba(255,122,41,0.18); border: 1.5px solid {ORANGE};
                    border-radius: 6px; font-size: 12px;
                """)
            else:
                label.setText("")
                label.setStyleSheet("""
                    background-color: #1c1c1f; border: 1.5px solid rgba(255,255,255,0.12);
                    border-radius: 6px;
                """)


class AddDeviceCard(AnimatedCard):
    """
    Kostkovana karta "Přidat nové zařízení". Stavy:
      idle       -> velke zarici "+", nadpis, podnadpis, tlacitko "Skenovat"
      searching  -> loading linka + "Hledám zařízení..."
      not_found  -> po timeoutu "Nic jsem nenašel" + tlacitka Znovu/Zpátky
    """

    SEARCH_TIMEOUT_MS = 8000

    def __init__(self):
        super().__init__()
        self.setObjectName("addCard")
        self.setFixedSize(300, 320)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 24, 24, 24)

        self.icon_circle = QLabel("+")
        self.icon_circle.setFixedSize(64, 64)
        self.icon_circle.setAlignment(Qt.AlignCenter)
        self.icon_circle.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.icon_circle.setStyleSheet(f"""
            background-color: rgba(255,122,41,0.18); color: {ORANGE};
            font-size: 30px; font-weight: 700; border-radius: 32px;
        """)
        glow = QGraphicsDropShadowEffect(self.icon_circle)
        glow.setBlurRadius(40)
        glow.setOffset(0, 0)
        glow.setColor(QColor(ORANGE))
        self.icon_circle.setGraphicsEffect(glow)

        self.title_label = QLabel("Přidat nové zařízení")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(f"color: {TEXT}; font-size: 15px; font-weight: 700; background: transparent;")
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.subtitle_label = QLabel("Zaregistrovat nový hardware PeciTech.")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;")
        self.subtitle_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.loading_bar = LoadingBar()
        self.loading_bar.setFixedWidth(160)
        self.loading_bar.hide()

        self.scan_btn = QPushButton("Skenovat")
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ORANGE}; color: white; border: none; border-radius: 8px;
                padding: 8px 22px; font-size: 12px; font-weight: 700;
            }}
            QPushButton:hover {{ background-color: #e8650f; }}
        """)
        self.scan_btn.clicked.connect(self.start_searching)

        self.retry_btn = QPushButton("Znovu")
        self.retry_btn.setCursor(Qt.PointingHandCursor)
        self.retry_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ORANGE}; color: white; border: none; border-radius: 8px;
                padding: 6px 14px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #e8650f; }}
        """)
        self.retry_btn.clicked.connect(self.start_searching)

        self.back_btn = QPushButton("Zpátky")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {TEXT_MUTED};
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 8px; padding: 6px 14px; font-size: 12px;
            }}
            QPushButton:hover {{ background-color: rgba(255,255,255,0.06); }}
        """)
        self.back_btn.clicked.connect(self.reset_to_idle)

        self.retry_row = QWidget()
        retry_layout = QHBoxLayout(self.retry_row)
        retry_layout.setContentsMargins(0, 0, 0, 0)
        retry_layout.addStretch()
        retry_layout.addWidget(self.retry_btn)
        retry_layout.addWidget(self.back_btn)
        retry_layout.addStretch()
        self.retry_row.hide()

        layout.addWidget(self.icon_circle, alignment=Qt.AlignCenter)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addWidget(self.loading_bar, alignment=Qt.AlignCenter)
        layout.addWidget(self.scan_btn, alignment=Qt.AlignCenter)
        layout.addWidget(self.retry_row)

        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._on_search_timeout)

        self.state = "idle"

    def start_searching(self):
        if self.state == "searching":
            return
        self.state = "searching"
        self._timeout_timer.stop()
        self.icon_circle.hide()
        self.scan_btn.hide()
        self.retry_row.hide()
        self.title_label.setText("Hledám zařízení...")
        self.subtitle_label.setText("")
        self.loading_bar.show()
        self.loading_bar.start()
        self._timeout_timer.start(self.SEARCH_TIMEOUT_MS)

    def stop_searching(self, found: bool):
        """Vola DeviceWatcher, kdyz najde/ztrati zarizeni - i mimo rucni hledani."""
        self._timeout_timer.stop()
        self.loading_bar.stop()
        self.loading_bar.hide()
        self.retry_row.hide()
        self.icon_circle.show()
        self.scan_btn.show()
        self.state = "idle"
        self.title_label.setText("Přidat další zařízení" if found else "Přidat nové zařízení")
        self.subtitle_label.setText("Zaregistrovat nový hardware PeciTech.")

    def _on_search_timeout(self):
        if self.state != "searching":
            return
        self.state = "not_found"
        self.loading_bar.stop()
        self.loading_bar.hide()
        self.title_label.setText("Nic jsem nenašel")
        self.retry_row.show()

    def reset_to_idle(self):
        self._timeout_timer.stop()
        self.state = "idle"
        self.loading_bar.stop()
        self.loading_bar.hide()
        self.retry_row.hide()
        self.icon_circle.show()
        self.scan_btn.show()
        self.title_label.setText("Přidat nové zařízení")
        self.subtitle_label.setText("Zaregistrovat nový hardware PeciTech.")


class DeviceCard(AnimatedCard):
    """Karta pripojeneho zarizeni - nahled desky, nazev, stav, verze FW, tlacitko Konfigurovat."""

    def __init__(self, name="PeciDeck", on_configure=None):
        super().__init__()
        self.setFixedSize(340, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(8)

        self.preview = MiniDeckPreview()
        layout.addWidget(self.preview)

        self.name_label = QLabel(name)
        self.name_label.setStyleSheet(f"color: {TEXT}; font-size: 16px; font-weight: 700; background: transparent;")
        self.name_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.name_label)

        status_row = QHBoxLayout()
        self.dot = QLabel("\u25CF")
        self.dot.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.status_text = QLabel("Odpojeno")
        self.status_text.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;")
        self.status_text.setAttribute(Qt.WA_TransparentForMouseEvents)
        status_row.addWidget(self.dot)
        status_row.addWidget(self.status_text)
        status_row.addStretch()
        layout.addLayout(status_row)

        self.fw_label = QLabel("")
        self.fw_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;")
        self.fw_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.fw_label)

        layout.addStretch()

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        self.configure_btn = QPushButton("Konfigurovat")
        self.configure_btn.setCursor(Qt.PointingHandCursor)
        self.configure_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1.5px solid {ORANGE}; color: {ORANGE};
                border-radius: 8px; padding: 7px 18px; font-size: 12px; font-weight: 700;
            }}
            QPushButton:hover {{ background-color: rgba(255,122,41,0.12); }}
        """)
        if on_configure is not None:
            self.configure_btn.clicked.connect(on_configure)
        bottom_row.addWidget(self.configure_btn)
        layout.addLayout(bottom_row)

        self.set_connected(False)

    def set_connected(self, connected: bool, fw_version: str = ""):
        if connected:
            self.dot.setStyleSheet(f"color: {ORANGE}; font-size: 13px; background: transparent;")
            self.status_text.setText("Připojeno přes USB")
        else:
            self.dot.setStyleSheet("color: #e34b4b; font-size: 13px; background: transparent;")
            self.status_text.setText("Odpojeno")
        if fw_version:
            self.fw_label.setText(f"Verze FW: {fw_version}")

    def set_name(self, name: str):
        self.name_label.setText(name)


class HomePage(QWidget):
    """Uvodni obrazovka "Moje Zařízení" - nadpis, podnadpis, karty zarizeni zarovnane nahoru/vlevo."""

    def __init__(self, open_settings_callback, open_device_detail_callback, get_preview_icons=None):
        super().__init__()
        self._open_device_detail_callback = open_device_detail_callback
        self._get_preview_icons = get_preview_icons

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 28)
        root.setSpacing(0)
        root.setAlignment(Qt.AlignTop)

        top_bar = QHBoxLayout()
        title = QLabel("PeciTech")
        title.setStyleSheet(f"color: {TEXT}; font-size: 20px; font-weight: 700;")
        top_bar.addWidget(title)
        top_bar.addStretch()

        settings_btn = QPushButton("\u2699")
        settings_btn.setObjectName("settingsBtn")
        settings_btn.setFixedSize(36, 36)
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.clicked.connect(open_settings_callback)
        top_bar.addWidget(settings_btn)
        root.addLayout(top_bar)

        heading = QLabel("Moje Zařízení")
        heading.setStyleSheet(f"color: {TEXT}; font-size: 30px; font-weight: 700; margin-top: 20px;")
        root.addWidget(heading)

        subtitle = QLabel("Spravujte a přizpůsobte si svá zařízení.")
        subtitle.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px; margin-top: 4px; margin-bottom: 24px;")
        root.addWidget(subtitle)

        row = QHBoxLayout()
        row.setSpacing(20)
        row.setAlignment(Qt.AlignLeft)

        self.add_card = AddDeviceCard()
        self.device_card = None
        self._row = row

        row.addWidget(self.add_card)
        row.addStretch()
        root.addLayout(row)
        root.addStretch()

    def on_device_connected(self, caps: dict):
        self.add_card.stop_searching(found=True)
        name = caps.get("name", "PeciDeck")
        fw_version = caps.get("fw_version", "")
        if self.device_card is None:
            self.device_card = DeviceCard(name, on_configure=lambda: self._open_device_detail_callback(name))
            self._row.insertWidget(0, self.device_card)
        else:
            self.device_card.set_name(name)
        self.device_card.set_connected(True, fw_version)
        self.refresh_device_preview()

    def on_device_disconnected(self):
        self.add_card.stop_searching(found=False)
        if self.device_card is not None:
            self.device_card.set_connected(False)

    def refresh_device_preview(self):
        """Prekresli mini-nahled desky podle aktualnich prirazeni na prvni strance (viz MainWindow)."""
        if self.device_card is None or self._get_preview_icons is None:
            return
        self.device_card.preview.set_icons(self._get_preview_icons())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PeciTech")
        self.resize(960, 640)
        self.setMinimumSize(960, 650)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.device_detail_page = DeviceDetailPage()
        self.device_detail_page.back_requested.connect(self.show_home)

        self.home_page = HomePage(
            self.show_settings, self.open_device_detail,
            get_preview_icons=self._get_preview_icons,
        )
        self.settings_page = SettingsPage()
        self.settings_page.back_requested.connect(self.show_home)

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.device_detail_page)

        self._setup_watcher()
        self._apply_style()

    def show_settings(self):
        self.stack.setCurrentWidget(self.settings_page)

    def show_home(self):
        self.home_page.refresh_device_preview()
        self.stack.setCurrentWidget(self.home_page)

    def open_device_detail(self, name: str):
        self.device_detail_page.set_device_name(name)
        self.stack.setCurrentWidget(self.device_detail_page)

    def _get_preview_icons(self):
        if not self.device_detail_page.pages:
            return [None] * 8
        first_page = self.device_detail_page.pages[0]
        return [action["icon"] if action else None for action in first_page["buttons"]]

    def _setup_watcher(self):
        watcher_cls = MockDeviceWatcher if MOCK_MODE else DeviceWatcher
        self.watcher = watcher_cls()
        self.watcher.device_connected.connect(self.home_page.on_device_connected)
        self.watcher.device_disconnected.connect(self.home_page.on_device_disconnected)
        self.watcher_thread = threading.Thread(target=self.watcher.run, daemon=True)
        self.watcher_thread.start()

    def _apply_style(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {BG}; }}
            QWidget {{ background-color: {BG}; }}
            #card {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 16px;
            }}
            #addCard {{
                background-color: {CARD_BG};
                border: 1.5px dashed rgba(255,122,41,0.35);
                border-radius: 16px;
            }}
            #settingsBtn {{
                background: transparent; border: none; color: {TEXT}; font-size: 16px;
                border-radius: 18px;
            }}
            #settingsBtn:hover {{ background-color: rgba(255,255,255,0.08); }}
            QLabel {{ color: {TEXT}; }}
        """)

    def closeEvent(self, event):
        self.watcher.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()