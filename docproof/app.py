"""Application entry point. Handles startup flow and engine initialization."""

import sys

from PySide6.QtWidgets import QApplication

from docproof.config import APP_NAME, init_config
from docproof.engine.engine_manager import EngineManager
from docproof.ui.main_window import MainWindow


class DocProofApp:
    """Main application controller."""

    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setApplicationName(APP_NAME)

        # Apply the saved theme (system / light / dark).
        from docproof.settings_store import SettingsStore
        from docproof.ui.theme import apply_theme
        theme = SettingsStore().get("theme", "light")
        apply_theme(self._app, theme)

        self._engine_manager = EngineManager()
        self._main_window: MainWindow | None = None

    def run(self) -> int:
        """Run the application. Returns exit code."""
        # Setup directories, env vars, and import paths
        init_config()

        # Try to load engine silently on startup.
        # The app starts even without a model — the user can select and load
        # a model later through Settings → Language Model Selection.
        self._engine_manager.auto_load()

        # Show main window
        self._main_window = MainWindow(self._engine_manager)
        self._main_window.show()

        ret = self._app.exec()

        # Clean up engine before interpreter shutdown
        self._engine_manager.unload()
        return ret


def main():
    from docproof.logging_setup import init_logging
    from docproof.version import __version__
    logger = init_logging()
    logger.info("DocProof v%s 启动", __version__)
    app = DocProofApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
