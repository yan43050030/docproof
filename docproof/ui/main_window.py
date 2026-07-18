"""Main application window."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QAction, QFont, QIcon, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from docproof.config import APP_NAME, PROJECT_MODELS_DIR, MODEL_SEARCH_DIRS
from docproof.document.docx_handler import DocxHandler
from docproof.engine.engine_manager import EngineManager
from docproof.ui.correction_view import CorrectionView
from docproof.ui.error_list import ErrorListPanel
from docproof.ui.dialogs.settings import SettingsDialog
from docproof.ui.welcome_wizard import WelcomeWizard


class ProofreadWorker(QThread):
    """Background thread for running proofreading."""

    finished = Signal(list)  # list of ErrorItem
    error = Signal(str)  # error message
    progress = Signal(str)  # progress message

    def __init__(self, engine_manager: EngineManager, text: str, parent=None):
        super().__init__(parent)
        self._engine_manager = engine_manager
        self._text = text

    def run(self):
        try:
            engine = self._engine_manager.engine
            if engine is None:
                self.error.emit("校对引擎未加载")
                return

            self.progress.emit("正在校对...")
            errors = engine.correct(self._text)
            self.finished.emit(errors)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """DocProof main window."""

    def __init__(self, engine_manager: EngineManager):
        super().__init__()
        self._engine_manager = engine_manager
        self._docx_handler: DocxHandler | None = None
        self._proofread_done = False
        self._current_errors: list = []

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1000, 700)
        self.setAcceptDrops(True)

        self._setup_menu()
        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()
        self._update_title()

    # ---- UI Setup ----

    def _setup_menu(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("文件(&F)")
        open_action = QAction("打开文档(&O)...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)

        export_menu = file_menu.addMenu("导出")
        export_clean = QAction("导出校对后文档（直接修改）", self)
        export_clean.triggered.connect(self._export_clean)
        export_menu.addAction(export_clean)

        export_marked = QAction("导出修订标记文档", self)
        export_marked.triggered.connect(self._export_marked)
        export_menu.addAction(export_marked)

        file_menu.addSeparator()
        quit_action = QAction("退出(&Q)", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = menu_bar.addMenu("帮助(&H)")
        about_action = QAction("关于 DocProof", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        model_action = QAction("管理语言模型...", self)
        model_action.triggered.connect(self._show_model_manager)
        help_menu.addAction(model_action)

    def _setup_toolbar(self):
        toolbar = QToolBar("工具栏")
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar { padding: 4px; spacing: 6px; background: #F8F9FA;
                       border-bottom: 1px solid #E0E0E0; }
        """)
        self.addToolBar(toolbar)

        open_btn = QPushButton("📂 打开文档")
        open_btn.clicked.connect(self._open_file)
        open_btn.setStyleSheet(self._btn_style("#2563EB"))
        toolbar.addWidget(open_btn)

        toolbar.addSeparator()

        self.proofread_btn = QPushButton("🔍 开始校对")
        self.proofread_btn.clicked.connect(self._start_proofread)
        self.proofread_btn.setEnabled(False)
        self.proofread_btn.setStyleSheet(self._btn_style("#16A34A"))
        toolbar.addWidget(self.proofread_btn)

        toolbar.addSeparator()

        self.export_btn = QPushButton("💾 导出")
        self.export_btn.clicked.connect(self._export_clean)
        self.export_btn.setEnabled(False)
        self.export_btn.setStyleSheet(self._btn_style("#6B7280"))
        toolbar.addWidget(self.export_btn)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Drop hint overlay
        self._drop_hint = QLabel("拖放 Word 文档 (.docx) 到这里，或点击「打开文档」")
        self._drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_hint.setStyleSheet("""
            QLabel {
                color: #9CA3AF;
                font-size: 18px;
                border: 2px dashed #D1D5DB;
                border-radius: 12px;
                background: #FAFAFA;
                padding: 60px;
                margin: 20px;
            }
        """)
        layout.addWidget(self._drop_hint)

        # Splitter (text view + error list)
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setVisible(False)

        self._correction_view = CorrectionView()
        self._error_list = ErrorListPanel()

        self._splitter.addWidget(self._correction_view)
        self._splitter.addWidget(self._error_list)
        self._splitter.setSizes([650, 300])

        # Connect signals
        self._error_list.error_selected.connect(self._on_error_selected)
        self._error_list.error_accepted.connect(self._on_error_accepted)
        self._error_list.error_ignored.connect(self._on_error_ignored)

        layout.addWidget(self._splitter)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setMaximum(0)  # indeterminate
        self._progress.setMaximumHeight(3)
        self._progress.setTextVisible(False)
        layout.addWidget(self._progress)

    def _setup_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)

        self._status_icon = QLabel("🟢")
        self._statusbar.addWidget(self._status_icon)

        self._status_text = QLabel("就绪")
        self._statusbar.addWidget(self._status_text)

        self._statusbar.addPermanentWidget(QLabel("  "))

        self._char_count = QLabel("字数: 0")
        self._statusbar.addPermanentWidget(self._char_count)

    # ---- Actions ----

    def _open_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "打开文档", "",
            "Word 文档 (*.docx);;所有文件 (*)"
        )
        if filepath:
            self._load_document(filepath)

    def _load_document(self, filepath: str):
        """Load a .docx file and display its content."""
        try:
            self._docx_handler = DocxHandler(filepath)
            self._docx_handler.load()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开文档:\n{e}")
            return

        self._proofread_done = False
        self._current_errors = []

        text = self._docx_handler.get_full_text()
        self._correction_view.load_text(text)
        self._error_list.set_errors([])

        self._drop_hint.setVisible(False)
        self._splitter.setVisible(True)
        self.proofread_btn.setEnabled(True)
        self.export_btn.setEnabled(False)

        self._update_title(filepath)
        self._status_text.setText(f"已加载: {os.path.basename(filepath)}")
        self._char_count.setText(f"字数: {len(text)}")

    def _start_proofread(self):
        """Run the proofreading engine on the loaded document."""
        if self._docx_handler is None:
            return

        self.proofread_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status_text.setText("正在校对...")

        text = self._docx_handler.get_full_text()

        self._worker = ProofreadWorker(self._engine_manager, text)
        self._worker.finished.connect(self._on_proofread_done)
        self._worker.error.connect(self._on_proofread_error)
        self._worker.progress.connect(lambda msg: self._status_text.setText(msg))
        self._worker.start()

    def _on_proofread_done(self, errors):
        """Handle proofreading completion."""
        self._progress.setVisible(False)
        self.proofread_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self._proofread_done = True
        self._current_errors = errors

        text = self._docx_handler.get_full_text()
        self._correction_view.show_corrections(text, errors)
        self._error_list.set_errors(errors)

        self._status_text.setText(
            f"校对完成 — 发现 {len(errors)} 处疑似错误"
            if errors else "校对完成 — 未发现错误 ✓"
        )

    def _on_proofread_error(self, msg: str):
        """Handle proofreading error."""
        self._progress.setVisible(False)
        self.proofread_btn.setEnabled(True)
        QMessageBox.warning(self, "校对错误", msg)
        self._status_text.setText("校对失败")

    def _on_error_selected(self, idx: int):
        """Highlight an error in the text view."""
        self._correction_view.highlight_error(idx)

    def _on_error_accepted(self, idx: int):
        """Accept a correction."""
        self._status_text.setText(
            f"已接受 {len(self._error_list.get_accepted_errors())} 处修改"
        )

    def _on_error_ignored(self, idx: int):
        """Ignore a correction."""
        remaining = len(self._error_list.get_remaining_errors())
        self._status_text.setText(f"剩余 {remaining} 处待处理")

    def _export_clean(self):
        """Export document with accepted corrections applied directly."""
        if self._docx_handler is None or not self._proofread_done:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出校对后文档", "",
            "Word 文档 (*.docx)"
        )
        if not filepath:
            return

        try:
            accepted = self._error_list.get_accepted_errors()
            if accepted:
                self._docx_handler.apply_corrections(accepted, markup=False)
            self._docx_handler.save(filepath)
            self._status_text.setText(f"已导出: {os.path.basename(filepath)}")
            QMessageBox.information(
                self, "导出成功",
                f"文档已保存到:\n{filepath}\n\n"
                f"共应用 {len(accepted)} 处修改。"
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _export_marked(self):
        """Export document with revision markup visible."""
        if self._docx_handler is None or not self._proofread_done:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出修订标记文档", "",
            "Word 文档 (*.docx)"
        )
        if not filepath:
            return

        try:
            # Apply all errors with markup
            self._docx_handler.apply_corrections(
                self._current_errors, markup=True
            )
            self._docx_handler.save(filepath)
            self._status_text.setText(f"已导出修订版: {os.path.basename(filepath)}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    # ---- Drag and Drop ----

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().endswith(".docx"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            filepath = url.toLocalFile()
            if filepath.endswith(".docx"):
                self._load_document(filepath)
                return

    # ---- Dialogs ----

    def _show_about(self):
        QMessageBox.about(
            self, "关于 DocProof",
            "<h3>DocProof</h3>"
            "<p>中文文档离线校对工具 v0.1.0</p>"
            "<p>基于 pycorrector 校对引擎</p>"
            "<p>校对引擎: Kenlm 统计语言模型 (Apache 2.0)</p>"
            "<p>模型搜索目录（按优先级）:</p>"
            f"<p>1. <code>{PROJECT_MODELS_DIR}</code></p>"
            f"<p>2. <code>{MODEL_SEARCH_DIRS[1]}</code></p>"
        )

    def _show_model_manager(self):
        """Show the settings dialog for model management."""
        dialog = SettingsDialog(self._engine_manager, self)
        dialog.exec()
        # Update status after settings change
        if self._engine_manager.is_loaded:
            from docproof.config import MODELS
            key = self._engine_manager.current_model_key
            name = MODELS[key]['name'] if key else '未知'
            self._status_text.setText(f"已切换模型: {name}")

    # ---- Helpers ----

    def _update_title(self, filepath: str | None = None):
        if filepath:
            self.setWindowTitle(f"{os.path.basename(filepath)} - {APP_NAME}")
        else:
            self.setWindowTitle(APP_NAME)

    @staticmethod
    def _btn_style(color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 13px;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
            QPushButton:disabled {{ background-color: #D1D5DB; color: #9CA3AF; }}
        """
