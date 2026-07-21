"""Application entry point. Handles startup flow and engine initialization."""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from docproof.config import (
    APP_NAME, PROJECT_MODELS_DIR, MODEL_SEARCH_DIRS,
    init_config,
)
from docproof.engine.engine_manager import EngineManager
from docproof.ui.main_window import MainWindow


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

        # Try to load engine (non-blocking — app starts even without a model)
        ok, msg = self._engine_manager.auto_load()
        if not ok:
            QMessageBox.warning(
                None, "未找到语言模型",
                f"{msg}\n\n"
                f"校对功能暂时不可用。请通过「设置 → 语言模型选择」下载并加载模型。\n"
                f"模型文件可放入以下目录（支持子目录递归搜索）:\n"
                f"  {PROJECT_MODELS_DIR}\n"
                f"或:\n"
                f"  {MODEL_SEARCH_DIRS[1]}"
            )

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
