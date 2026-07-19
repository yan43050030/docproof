"""Application entry point. Handles startup flow and engine initialization."""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from docproof.config import (
    APP_NAME, PROJECT_MODELS_DIR, MODEL_SEARCH_DIRS,
    get_available_model, DEFAULT_MODEL, init_config,
)
from docproof.engine.engine_manager import EngineManager
from docproof.ui.main_window import MainWindow
from docproof.ui.welcome_wizard import WelcomeWizard


class DocProofApp:
    """Main application controller."""

    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setApplicationName(APP_NAME)

        # Force light theme so text is visible regardless of system dark mode
        self._app.setStyle("Fusion")
        self._app.setStyleSheet("""
            QWidget {
                color: #1a1a1a;
                background-color: #FFFFFF;
            }
            QMenuBar {
                background-color: #F5F5F5;
            }
            QMenuBar::item:selected {
                background-color: #E0E0E0;
            }
            QStatusBar {
                background-color: #F5F5F5;
            }
            QToolBar {
                background-color: #F8F9FA;
            }
            QToolTip {
                background-color: #333;
                color: white;
                border: none;
                padding: 4px;
            }
        """)

        self._engine_manager = EngineManager()
        self._main_window: MainWindow | None = None

    def run(self) -> int:
        """Run the application. Returns exit code."""
        # Setup directories, env vars, and import paths
        init_config()

        # Check if a model is available
        available = get_available_model()
        if available is None:
            # No model - show wizard
            ok = self._show_welcome()
            if not ok:
                return 0  # user cancelled

        # Try to load engine
        ok, msg = self._engine_manager.auto_load()
        if not ok:
            QMessageBox.critical(
                None, "引擎加载失败",
                f"{msg}\n\n"
                f"请将语言模型文件放入以下目录后重新启动程序:\n"
                f"  {PROJECT_MODELS_DIR}\n"
                f"或:\n"
                f"  {MODEL_SEARCH_DIRS[1]}"
            )
            return 1

        # Show main window
        self._main_window = MainWindow(self._engine_manager)
        self._main_window.show()

        ret = self._app.exec()

        # Clean up engine before interpreter shutdown
        self._engine_manager.unload()
        return ret

    def _show_welcome(self) -> bool:
        """Show the welcome wizard. Returns True if user proceeds."""
        wizard = WelcomeWizard()
        result = wizard.exec()
        return result == WelcomeWizard.DialogCode.Accepted


def main():
    app = DocProofApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
