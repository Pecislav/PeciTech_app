"""
PeciTech - hlavni okno aplikace (PySide6)
------------------------------------------------------------------
Cerno/oranzovy design inspirovany Logi Options+ (velky nadpis, dlazdice
uprostred obrazovky, nastaveni jako soucast stejneho okna - ne popup).

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
  main_window.py - tohle - hlavni okno, dlazdice zarizeni, detekce HID
  settings.py     - stranka nastaveni (vklada se do stejneho okna pres
                    QStackedWidget, neni to samostatny dialog/okno)
"""

import os
import sys
import threading
import time

from PySide6.QtCore import Qt, QObject, Signal, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QFont, QColor, QPainter
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QGraphicsOpacityEffect,
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
            "fw_version": "0.1.0",
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


class AddDeviceTile(AnimatedCard):
    """
    Velka dlazdice uprostred okna. Stavy:
      idle       -> "+" a "Přidat zařízení", klik spusti hledani
      searching  -> loading linka + "Hledám zařízení..."
      not_found  -> po timeoutu "Nic jsem nenašel" + tlacitka Znovu/Zpátky
    """

    SEARCH_TIMEOUT_MS = 8000

    def __init__(self):
        super().__init__()
        self.setFixedSize(220, 220)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)

        self.icon_label = QLabel("+")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet(f"font-size: 52px; color: {ORANGE}; background: transparent;")
        self.icon_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.text_label = QLabel("Přidat zařízení")
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px; background: transparent;")
        self.text_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.loading_bar = LoadingBar()
        self.loading_bar.setFixedWidth(140)
        self.loading_bar.hide()

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

        self.buttons_row = QWidget()
        buttons_layout = QHBoxLayout(self.buttons_row)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.retry_btn)
        buttons_layout.addWidget(self.back_btn)
        buttons_layout.addStretch()
        self.buttons_row.hide()

        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addWidget(self.loading_bar, alignment=Qt.AlignCenter)
        layout.addWidget(self.buttons_row)

        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._on_search_timeout)

        self.state = "idle"

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.state == "idle":
            self.start_searching()
        super().mousePressEvent(event)

    def start_searching(self):
        self.state = "searching"
        self._timeout_timer.stop()
        self.icon_label.hide()
        self.buttons_row.hide()
        self.text_label.setText("Hledám zařízení...")
        self.loading_bar.show()
        self.loading_bar.start()
        self._timeout_timer.start(self.SEARCH_TIMEOUT_MS)

    def stop_searching(self, found: bool):
        """Vola DeviceWatcher, kdyz najde/ztrati zarizeni - i mimo rucni hledani."""
        self._timeout_timer.stop()
        self.loading_bar.stop()
        self.loading_bar.hide()
        self.buttons_row.hide()
        self.icon_label.show()
        self.state = "idle"
        self.text_label.setText("Přidat další zařízení" if found else "Přidat zařízení")

    def _on_search_timeout(self):
        if self.state != "searching":
            return
        self.state = "not_found"
        self.loading_bar.stop()
        self.loading_bar.hide()
        self.text_label.setText("Nic jsem nenašel")
        self.buttons_row.show()

    def reset_to_idle(self):
        self._timeout_timer.stop()
        self.state = "idle"
        self.loading_bar.stop()
        self.loading_bar.hide()
        self.buttons_row.hide()
        self.icon_label.show()
        self.text_label.setText("Přidat zařízení")


class DeviceTile(AnimatedCard):
    def __init__(self, name="PeciDeck", on_click=None):
        super().__init__()
        self._on_click = on_click
        self.setFixedSize(220, 220)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)

        photo = QLabel("\U0001F5A5")
        photo.setAlignment(Qt.AlignCenter)
        photo.setStyleSheet("font-size: 46px; background: transparent;")
        photo.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.name_label = QLabel(name)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet(f"color: {TEXT}; font-size: 15px; font-weight: 600; background: transparent;")
        self.name_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        status_row = QHBoxLayout()
        self.dot = QLabel("\u25CF")
        self.dot.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.status_text = QLabel("odpojeno")
        self.status_text.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;")
        self.status_text.setAttribute(Qt.WA_TransparentForMouseEvents)
        status_row.addStretch()
        status_row.addWidget(self.dot)
        status_row.addWidget(self.status_text)
        status_row.addStretch()

        layout.addWidget(photo)
        layout.addWidget(self.name_label)
        layout.addLayout(status_row)

        self.set_connected(False)

    def set_connected(self, connected: bool):
        if connected:
            self.dot.setStyleSheet(f"color: {ORANGE}; font-size: 14px; background: transparent;")
            self.status_text.setText("připojeno")
        else:
            self.dot.setStyleSheet("color: #e34b4b; font-size: 14px; background: transparent;")
            self.status_text.setText("odpojeno")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._on_click is not None:
            self._on_click()
        super().mousePressEvent(event)


class HomePage(QWidget):
    """Uvodni obrazovka - nadpis, tlacitko nastaveni, dlazdice vycentrovane."""

    def __init__(self, open_settings_callback, open_device_detail_callback):
        super().__init__()
        self._open_device_detail_callback = open_device_detail_callback
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)

        top_bar = QHBoxLayout()
        title = QLabel("PeciTech")
        title.setStyleSheet(f"color: {TEXT}; font-size: 38px; font-weight: 700;")
        top_bar.addWidget(title)
        top_bar.addStretch()

        settings_btn = QPushButton("\u2699")
        settings_btn.setObjectName("settingsBtn")
        settings_btn.setFixedSize(40, 40)
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.clicked.connect(open_settings_callback)
        top_bar.addWidget(settings_btn)
        root.addLayout(top_bar)

        # --- stred obrazovky: dlazdice vycentrovane na vysku i sirku ---
        center_wrap = QVBoxLayout()
        center_wrap.addStretch()
        row = QHBoxLayout()
        row.addStretch()

        self.add_tile = AddDeviceTile()
        row.addWidget(self.add_tile)
        self.device_tile = None
        self._row = row

        row.addStretch()
        center_wrap.addLayout(row)
        center_wrap.addStretch()
        root.addLayout(center_wrap)

    def on_device_connected(self, caps: dict):
        self.add_tile.stop_searching(found=True)
        name = caps.get("name", "PeciDeck")
        if self.device_tile is None:
            self.device_tile = DeviceTile(name, on_click=lambda: self._open_device_detail_callback(name))
            self._row.insertWidget(self._row.count() - 1, self.device_tile)
        self.device_tile.set_connected(True)

    def on_device_disconnected(self):
        self.add_tile.stop_searching(found=False)
        if self.device_tile is not None:
            self.device_tile.set_connected(False)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PeciTech")
        self.resize(900, 600)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.home_page = HomePage(self.show_settings, self.open_device_detail)
        self.settings_page = SettingsPage()
        self.settings_page.back_requested.connect(self.show_home)

        self.device_detail_page = DeviceDetailPage()
        self.device_detail_page.back_requested.connect(self.show_home)

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.device_detail_page)

        self._setup_watcher()
        self._apply_style()

    def show_settings(self):
        self.stack.setCurrentWidget(self.settings_page)

    def show_home(self):
        self.stack.setCurrentWidget(self.home_page)

    def open_device_detail(self, name: str):
        self.device_detail_page.set_device_name(name)
        self.stack.setCurrentWidget(self.device_detail_page)

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
            #settingsBtn {{
                background: transparent; border: none; color: {TEXT}; font-size: 18px;
                border-radius: 20px;
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