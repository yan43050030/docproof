"""Application entry point. Handles startup flow and engine initialization."""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from docproof.config import APP_NAME, PROJECT_MODELS_DIR, MODEL_SEARCH_DIRS, get_available_model, DEFAULT_MODEL
from docproof.engine.engine_manager import EngineManager
from docproof.ui.main_window import MainWindow
from docproof.ui.welcome_wizard import WelcomeWizard


class DocProofApp:
    """Main application controller."""

    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setApplicationName(APP_NAME)
        self._engine_manager = EngineManager()
        self._main_window: MainWindow | None = None

    def run(self) -> int:
        """Run the application. Returns exit code."""
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

        return self._app.exec()

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
