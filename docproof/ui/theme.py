"""Application theme (light / dark / follow-system).

The document area (text view, error list) keeps a light background in both
themes for readability — only the window chrome (menus, toolbar, status bar,
dialogs) switches — which is a common, low-risk pattern for editors.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

LIGHT_QSS = """
    QWidget { color: #1a1a1a; background-color: #FFFFFF; }
    QMenuBar { background-color: #F5F5F5; }
    QMenuBar::item:selected { background-color: #E0E0E0; }
    QStatusBar { background-color: #F5F5F5; }
    QToolBar { background-color: #F8F9FA; }
    QToolTip { background-color: #333; color: white; border: none; padding: 4px; }
"""

DARK_QSS = """
    QWidget { color: #E6E6E6; background-color: #2B2B2B; }
    QMainWindow, QDialog { background-color: #2B2B2B; }
    QMenuBar { background-color: #3A3A3A; color: #E6E6E6; }
    QMenuBar::item:selected { background-color: #505050; }
    QMenu { background-color: #3A3A3A; color: #E6E6E6; }
    QMenu::item:selected { background-color: #505050; }
    QStatusBar { background-color: #3A3A3A; }
    QToolBar { background-color: #333333; border-bottom: 1px solid #444; }
    QGroupBox { border: 1px solid #555; margin-top: 6px; }
    QComboBox, QLineEdit { background: #3A3A3A; color: #E6E6E6; border: 1px solid #555; }
    QToolTip { background-color: #111; color: #EEE; border: none; padding: 4px; }
"""


def resolve_mode(mode: str, app: QApplication | None = None) -> str:
    """Resolve 'system' to 'light' or 'dark'; pass through 'light'/'dark'."""
    if mode in ("light", "dark"):
        return mode
    # system: use Qt's reported color scheme when available.
    try:
        from PySide6.QtCore import Qt
        scheme = (app or QApplication.instance()).styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
    except Exception:
        pass
    return "light"


def apply_theme(app: QApplication, mode: str) -> None:
    """Apply a theme to the application. mode = system | light | dark."""
    resolved = resolve_mode(mode, app)
    app.setStyle("Fusion")
    if resolved == "dark":
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, QColor("#2B2B2B"))
        pal.setColor(QPalette.ColorRole.WindowText, QColor("#E6E6E6"))
        pal.setColor(QPalette.ColorRole.Base, QColor("#333333"))
        pal.setColor(QPalette.ColorRole.Text, QColor("#E6E6E6"))
        pal.setColor(QPalette.ColorRole.Button, QColor("#3A3A3A"))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor("#E6E6E6"))
        app.setPalette(pal)
        app.setStyleSheet(DARK_QSS)
    else:
        app.setPalette(QPalette())
        app.setStyleSheet(LIGHT_QSS)
