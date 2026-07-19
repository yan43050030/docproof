"""Main application window."""

from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl
from PySide6.QtGui import (
    QAction, QFont, QIcon, QDragEnterEvent, QDropEvent, QDesktopServices,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from docproof.config import APP_NAME, MODELS, PROJECT_MODELS_DIR, MODEL_SEARCH_DIRS
from docproof.version import __version__
from docproof.document.docx_handler import DocxHandler
from docproof.document.text_handler import TextHandler
from docproof.engine.engine_manager import EngineManager
from docproof.engine.user_dict import UserDict
from docproof.settings_store import SettingsStore
from docproof import report
from docproof.ui.correction_view import CorrectionView
from docproof.ui.error_list import ErrorListPanel
from docproof.ui.dialogs.settings import SettingsDialog
from docproof.ui.welcome_wizard import WelcomeWizard

# File dialog filters and the extensions we can open.
_DOCX_EXTS = (".docx",)
_TEXT_EXTS = (".txt", ".md")
_OPENABLE_EXTS = _DOCX_EXTS + _TEXT_EXTS
_LEGACY_EXTS = (".doc", ".wps", ".wpt")  # binary formats we can't parse


def _make_handler(filepath: str):
    """Return a handler appropriate for the file's extension."""
    if filepath.lower().endswith(_TEXT_EXTS):
        return TextHandler(filepath)
    return DocxHandler(filepath)


class ProofreadWorker(QThread):
    """Background thread for running proofreading."""

    finished = Signal(list)  # list of ErrorItem
    error = Signal(str)  # error message
    progress = Signal(str)  # progress message
    progress_pct = Signal(int, int)  # (done, total) for a determinate bar

    def __init__(self, engine_manager: EngineManager, text: str, parent=None):
        super().__init__(parent)
        self._engine_manager = engine_manager
        self._text = text
        self._should_stop = False

    def stop(self):
        """Request cancellation."""
        self._should_stop = True

    def run(self):
        try:
            if self._engine_manager.engine is None:
                self.error.emit("校对引擎未加载")
                return

            self.progress.emit("正在校对...")
            errors = self._engine_manager.proofread(
                self._text,
                progress=lambda d, t: self.progress_pct.emit(d, t),
                should_stop=lambda: self._should_stop,
            )
            if self._should_stop:
                return
            self.finished.emit(errors)
        except Exception as e:
            if not self._should_stop:
                self.error.emit(str(e))


class MainWindow(QMainWindow):
    """DocProof main window."""

    def __init__(self, engine_manager: EngineManager):
        super().__init__()
        self._engine_manager = engine_manager
        self._docx_handler: DocxHandler | None = None
        self._worker: ProofreadWorker | None = None
        self._proofread_done = False
        self._current_errors: list = []
        self._user_dict = UserDict()
        self._recent_files: list[str] = []
        self._recent_menu = None
        self._load_recent_files()

        # Persisted settings; apply to the engine before first use.
        self._settings = SettingsStore()
        self._engine_manager.set_threshold(self._settings.threshold)
        self._engine_manager.set_rule_check(self._settings.rule_check_enabled)

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1000, 700)
        self.setAcceptDrops(True)

        self._setup_menu()
        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()
        self._update_title()
        self._restore_geometry()

    # ---- UI Setup ----

    def _setup_menu(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("文件(&F)")
        open_action = QAction("打开文档(&O)...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)

        # Recent files submenu
        self._recent_menu = file_menu.addMenu("最近打开的文件")
        self._refresh_recent_menu()

        file_menu.addSeparator()

        export_menu = file_menu.addMenu("导出")
        export_clean = QAction("导出校对后文档（直接修改）", self)
        export_clean.triggered.connect(self._export_clean)
        export_menu.addAction(export_clean)

        export_tracked = QAction("导出 Word 修订版（可接受/拒绝）", self)
        export_tracked.triggered.connect(self._export_tracked)
        export_menu.addAction(export_tracked)

        export_marked = QAction("导出彩色标记文档", self)
        export_marked.triggered.connect(self._export_marked)
        export_menu.addAction(export_marked)

        export_report = QAction("导出校对报告 (HTML/TXT)...", self)
        export_report.triggered.connect(self._export_report)
        export_menu.addAction(export_report)

        file_menu.addSeparator()
        batch_action = QAction("批量校对文件夹...", self)
        batch_action.triggered.connect(self._batch_proofread)
        file_menu.addAction(batch_action)

        file_menu.addSeparator()
        quit_action = QAction("退出(&Q)", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Tools menu
        tools_menu = menu_bar.addMenu("工具(&T)")
        settings_action = QAction("设置...", self)
        settings_action.triggered.connect(self._show_model_manager)
        tools_menu.addAction(settings_action)
        dict_action = QAction("编辑用户词典...", self)
        dict_action.triggered.connect(self._edit_user_dict)
        tools_menu.addAction(dict_action)

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

        open_btn = QPushButton("打开文档")
        open_btn.clicked.connect(self._open_file)
        open_btn.setStyleSheet(self._btn_style("#2563EB"))
        toolbar.addWidget(open_btn)

        toolbar.addSeparator()

        self.proofread_btn = QPushButton("开始校对")
        self.proofread_btn.clicked.connect(self._start_proofread)
        self.proofread_btn.setEnabled(False)
        self.proofread_btn.setStyleSheet(self._btn_style("#16A34A"))
        toolbar.addWidget(self.proofread_btn)

        self.cancel_btn = QPushButton("取消校对")
        self.cancel_btn.clicked.connect(self._cancel_proofread)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setStyleSheet(self._btn_style("#DC2626"))
        toolbar.addWidget(self.cancel_btn)

        toolbar.addSeparator()

        self.edit_btn = QPushButton("编辑")
        self.edit_btn.setCheckable(True)
        self.edit_btn.clicked.connect(self._toggle_edit_mode)
        self.edit_btn.setEnabled(False)
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background: #F0F0F0;
                color: #333;
                border: 1px solid #CCC;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:checked {
                background: #FEF3C7;
                border-color: #F59E0B;
                color: #92400E;
                font-weight: bold;
            }
            QPushButton:hover { background: #E0E0E0; }
            QPushButton:disabled { background: #F5F5F5; color: #CCC; }
        """)
        toolbar.addWidget(self.edit_btn)

        self.export_btn = QPushButton("导出")
        self.export_btn.clicked.connect(self._export_clean)
        self.export_btn.setEnabled(False)
        self.export_btn.setStyleSheet(self._btn_style("#6B7280"))
        toolbar.addWidget(self.export_btn)

        toolbar.addSeparator()

        # Model selector
        model_label = QLabel("模型:")
        model_label.setStyleSheet("font-weight: bold; padding-left: 8px;")
        toolbar.addWidget(model_label)

        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(220)
        self._model_combo.setStyleSheet("""
            QComboBox {
                padding: 4px 8px;
                border: 1px solid #CCC;
                border-radius: 4px;
                background: white;
            }
            QComboBox:hover { border-color: #2563EB; }
        """)
        self._model_combo.currentIndexChanged.connect(self._on_model_combo_changed)
        toolbar.addWidget(self._model_combo)

        # Manage models button
        manage_btn = QPushButton("管理")
        manage_btn.clicked.connect(self._show_model_manager)
        manage_btn.setStyleSheet("""
            QPushButton {
                background: #F0F0F0;
                color: #333;
                border: 1px solid #CCC;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #E0E0E0; }
        """)
        toolbar.addWidget(manage_btn)

        self._refresh_model_combo()

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
        self._error_list.accept_all.connect(self._on_accept_all)

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

        self._status_icon = QLabel("[OK]")
        self._statusbar.addWidget(self._status_icon)

        self._status_text = QLabel("就绪")
        self._statusbar.addWidget(self._status_text)

        self._statusbar.addPermanentWidget(QLabel("  "))

        self._char_count = QLabel("字数: 0")
        self._statusbar.addPermanentWidget(self._char_count)

    def closeEvent(self, event):
        """Persist geometry and wait for the worker to finish before closing."""
        try:
            geo = bytes(self.saveGeometry().toHex().data()).decode("ascii")
            self._settings.set("window_geometry", geo)
        except Exception:
            pass
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(5000)
        event.accept()

    def _restore_geometry(self):
        """Restore the last window geometry if one was saved."""
        geo = self._settings.get("window_geometry")
        if not geo:
            return
        try:
            from PySide6.QtCore import QByteArray
            self.restoreGeometry(QByteArray.fromHex(bytes(geo, "ascii")))
        except Exception:
            pass

    # ---- Actions ----

    def _open_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "打开文档", "",
            "可校对文档 (*.docx *.txt *.md);;Word 文档 (*.docx);;"
            "文本文件 (*.txt *.md);;所有文件 (*)"
        )
        if filepath:
            self._load_document(filepath)

    def _load_document(self, filepath: str):
        """Load a .docx / .txt / .md file and display its content."""
        lower = filepath.lower()
        if lower.endswith(_LEGACY_EXTS):
            QMessageBox.information(
                self, "暂不支持该格式",
                "DocProof 无法直接读取 .doc / .wps 等旧二进制格式。\n\n"
                "请在 Word 或 WPS 中用「另存为」转换为 .docx 后再打开。"
            )
            return
        if not lower.endswith(_OPENABLE_EXTS):
            QMessageBox.warning(
                self, "不支持的文件",
                "仅支持 .docx、.txt、.md 文件。"
            )
            return
        try:
            self._docx_handler = _make_handler(filepath)
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

        self._add_recent_file(filepath)

    def _start_proofread(self):
        """Run the proofreading engine on the loaded document."""
        if self._docx_handler is None:
            return

        # Stop any previous worker before starting a new one
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(3000)
        self._worker = None

        self.proofread_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self._progress.setVisible(True)
        self._status_text.setText("正在校对...")

        text = self._docx_handler.get_full_text()

        self._progress.setMaximum(0)  # start indeterminate until first tick
        self._worker = ProofreadWorker(self._engine_manager, text)
        self._worker.finished.connect(self._on_proofread_done)
        self._worker.error.connect(self._on_proofread_error)
        self._worker.progress.connect(lambda msg: self._status_text.setText(msg))
        self._worker.progress_pct.connect(self._on_proofread_progress)
        self._worker.start()

    def _on_proofread_progress(self, done: int, total: int):
        """Update the progress bar with a real percentage."""
        if total > 0:
            self._progress.setMaximum(total)
            self._progress.setValue(done)
            self._status_text.setText(f"正在校对... {done}/{total} 段")

    def _cancel_proofread(self):
        """Cancel a running proofreading operation."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        self._progress.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.proofread_btn.setEnabled(True)
        self._status_text.setText("校对已取消")

    def _on_proofread_done(self, errors):
        """Handle proofreading completion."""
        self._progress.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.proofread_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.edit_btn.setEnabled(True)
        self.edit_btn.setChecked(False)
        self._proofread_done = True

        # Filter through user dictionary
        filtered_count = len(errors)
        errors = self._user_dict.filter_errors(errors)
        filtered_count -= len(errors)

        self._current_errors = errors

        text = self._docx_handler.get_full_text()
        self._correction_view.show_corrections(text, errors)
        self._error_list.set_errors(errors)

        msg = f"校对完成 — 发现 {len(errors)} 处疑似错误"
        if filtered_count > 0:
            msg += f" (用户词典过滤 {filtered_count} 处)"
        self._status_text.setText(
            msg if errors else "校对完成 — 未发现错误 ✓"
        )

    def _on_proofread_error(self, msg: str):
        """Handle proofreading error."""
        self._progress.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.proofread_btn.setEnabled(True)
        QMessageBox.warning(self, "校对错误", msg)
        self._status_text.setText("校对失败")

    def _on_error_selected(self, idx: int):
        """Highlight an error in the text view."""
        self._correction_view.highlight_error(idx)

    def _on_error_accepted(self, idx: int):
        """Accept a correction and refresh the text view."""
        # Exit edit mode if active
        if self._correction_view.edit_mode:
            self._toggle_edit_mode()
        self._refresh_correction_view()
        self._status_text.setText(
            f"已接受 {len(self._error_list.get_accepted_errors())} 处修改"
        )

    def _on_error_ignored(self, idx: int):
        """Ignore a correction and refresh the text view."""
        if self._correction_view.edit_mode:
            self._toggle_edit_mode()
        self._refresh_correction_view()
        remaining = len(self._error_list.get_remaining_errors())
        self._status_text.setText(f"剩余 {remaining} 处待处理")

    def _on_accept_all(self):
        """Accept all remaining errors."""
        if self._correction_view.edit_mode:
            self._toggle_edit_mode()
        self._refresh_correction_view()
        self._status_text.setText(
            f"已接受 {len(self._error_list.get_accepted_errors())} 处修改"
        )

    def _toggle_edit_mode(self):
        """Toggle between review mode and editable text mode."""
        enabled = self.edit_btn.isChecked()
        self._correction_view.set_edit_mode(enabled)

        if enabled:
            self._status_text.setText("编辑模式 — 可直接修改文本，完成后点击保存")
            self.edit_btn.setText("完成编辑")
        else:
            self._status_text.setText("已返回校对模式")
            self.edit_btn.setText("编辑")
            self._refresh_correction_view()

    def _refresh_correction_view(self):
        """Re-render the text view with accepted corrections applied."""
        if self._docx_handler is None:
            return
        base_text = self._docx_handler.get_full_text()
        self._correction_view.show_partial(
            base_text,
            self._current_errors,
            self._error_list.accepted_indices,
        )

    def _is_text_doc(self) -> bool:
        return isinstance(self._docx_handler, TextHandler)

    def _fresh_handler(self):
        """Load a clean copy from disk so exports never stack mutations."""
        handler = _make_handler(self._docx_handler.filepath)
        handler.load()
        return handler

    def _save_filter(self) -> str:
        return "文本文件 (*.txt)" if self._is_text_doc() else "Word 文档 (*.docx)"

    def _export_clean(self):
        """Export document with accepted (or hand-edited) changes applied."""
        if self._docx_handler is None or not self._proofread_done:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出校对后文档", "", self._save_filter()
        )
        if not filepath:
            return

        try:
            if self._correction_view.edit_mode:
                edited_text = self._correction_view.get_edited_text()
                handler = self._fresh_handler()
                handler.replace_full_text(edited_text)
                handler.save(filepath)
                note = "已保存所有手动修改。"
            else:
                accepted = self._error_list.get_accepted_errors()
                handler = self._fresh_handler()
                if accepted:
                    handler.apply_corrections(accepted, markup=False)
                handler.save(filepath)
                note = f"共应用 {len(accepted)} 处修改。"
            self._status_text.setText(f"已导出: {os.path.basename(filepath)}")
            QMessageBox.information(
                self, "导出成功", f"文档已保存到:\n{filepath}\n\n{note}"
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _export_tracked(self):
        """Export document with genuine Word tracked changes (accept/reject)."""
        if self._docx_handler is None or not self._proofread_done:
            return
        if self._is_text_doc():
            QMessageBox.information(
                self, "不适用", "纯文本文件没有修订格式，请使用「导出校对后文档」。"
            )
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出 Word 修订版", "", "Word 文档 (*.docx)"
        )
        if not filepath:
            return
        errors = self._export_errors()
        try:
            handler = self._fresh_handler()
            handler.apply_corrections(errors, track_changes=True)
            handler.save(filepath)
            self._status_text.setText(f"已导出修订版: {os.path.basename(filepath)}")
            QMessageBox.information(
                self, "导出成功",
                f"已保存 Word 修订版:\n{filepath}\n\n"
                f"共 {len(errors)} 处修订，可在 Word/WPS 中逐条接受或拒绝。"
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _export_marked(self):
        """Export document with visible colored markup (not real revisions)."""
        if self._docx_handler is None or not self._proofread_done:
            return
        if self._is_text_doc():
            QMessageBox.information(
                self, "不适用", "纯文本文件不支持彩色标记，请使用「导出校对后文档」。"
            )
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出彩色标记文档", "", "Word 文档 (*.docx)"
        )
        if not filepath:
            return
        errors = self._export_errors()
        try:
            handler = self._fresh_handler()
            handler.apply_corrections(errors, markup=True)
            handler.save(filepath)
            self._status_text.setText(f"已导出标记版: {os.path.basename(filepath)}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _export_errors(self) -> list:
        """Errors to write when exporting markup/revisions: accepted if any were
        explicitly accepted, otherwise all remaining (un-ignored) findings."""
        accepted = self._error_list.get_accepted_errors()
        if accepted:
            return accepted
        return self._error_list.get_remaining_errors()

    def _export_report(self):
        """Export a proofreading report (HTML or TXT)."""
        if self._docx_handler is None or not self._proofread_done:
            QMessageBox.information(self, "提示", "请先打开文档并完成校对。")
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出校对报告", "docproof-report.html",
            "HTML 报告 (*.html);;文本报告 (*.txt)"
        )
        if not filepath:
            return
        try:
            report.save_report(
                filepath, os.path.basename(self._docx_handler.filepath),
                self._current_errors,
            )
            self._status_text.setText(f"已导出报告: {os.path.basename(filepath)}")
            QMessageBox.information(self, "导出成功", f"报告已保存到:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _batch_proofread(self):
        """Proofread every supported file in a folder and export corrected copies."""
        if not self._engine_manager.is_loaded:
            QMessageBox.warning(self, "无引擎", "请先加载一个校对模型。")
            return
        src_dir = QFileDialog.getExistingDirectory(self, "选择待校对文件夹")
        if not src_dir:
            return
        files = [
            os.path.join(src_dir, f) for f in sorted(os.listdir(src_dir))
            if f.lower().endswith(_OPENABLE_EXTS)
            and not f.startswith("~$")
        ]
        if not files:
            QMessageBox.information(self, "无文件", "该文件夹内没有 .docx/.txt/.md 文件。")
            return
        out_dir = QFileDialog.getExistingDirectory(self, "选择输出文件夹（保存修订版）")
        if not out_dir:
            return

        dlg = QProgressDialog("正在批量校对...", "取消", 0, len(files), self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        done = 0
        total_errors = 0
        for i, path in enumerate(files):
            dlg.setValue(i)
            dlg.setLabelText(f"正在校对: {os.path.basename(path)}")
            QApplication.processEvents()
            if dlg.wasCanceled():
                break
            try:
                handler = _make_handler(path)
                handler.load()
                errors = self._engine_manager.proofread(handler.get_full_text())
                errors = self._user_dict.filter_errors(errors)
                total_errors += len(errors)
                if errors:
                    if isinstance(handler, TextHandler):
                        handler.apply_corrections(errors, markup=False)
                    else:
                        handler.apply_corrections(errors, track_changes=True)
                base, ext = os.path.splitext(os.path.basename(path))
                handler.save(os.path.join(out_dir, f"{base}-校对{ext}"))
                done += 1
            except Exception:
                continue
        dlg.setValue(len(files))
        self._status_text.setText(
            f"批量校对完成 — {done}/{len(files)} 个文件，共 {total_errors} 处修订"
        )
        QMessageBox.information(
            self, "批量校对完成",
            f"已处理 {done}/{len(files)} 个文件，共 {total_errors} 处修订。\n\n"
            f"修订版保存在:\n{out_dir}"
        )

    # ---- Drag and Drop ----

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        modifiers = event.modifiers()
        key = event.key()

        ctrl = modifiers & Qt.KeyboardModifier.ControlModifier
        shift = modifiers & Qt.KeyboardModifier.ShiftModifier

        if ctrl and key == Qt.Key.Key_Return:
            # Ctrl+Enter: accept current error
            if self._proofread_done:
                self._error_list._accept_current()
            return

        if ctrl and shift and key == Qt.Key.Key_Return:
            # Ctrl+Shift+Enter: accept all
            if self._proofread_done:
                self._error_list._accept_all()
            return

        if ctrl and key == Qt.Key.Key_D:
            # Ctrl+D: ignore current error
            if self._proofread_done:
                self._error_list._ignore_current()
            return

        if ctrl and key == Qt.Key.Key_Z:
            # Ctrl+Z: undo last ignore
            if self._proofread_done:
                idx = self._error_list.undo_last_ignore()
                if idx is not None:
                    self._on_error_ignored(idx)
                    self._refresh_correction_view()
            return

        if key == Qt.Key.Key_Escape:
            # Escape: cancel proofread or close
            if (self._worker is not None and self._worker.isRunning()):
                self._cancel_proofread()
            return

        if key == Qt.Key.Key_Down or key == Qt.Key.Key_Up:
            # Arrow keys: navigate error list
            if self._proofread_done and self._error_list.isVisible():
                list_widget = self._error_list.list_widget
                if list_widget.count() == 0:
                    return
                delta = 1 if key == Qt.Key.Key_Down else -1
                new_row = list_widget.currentRow() + delta
                if 0 <= new_row < list_widget.count():
                    list_widget.setCurrentRow(new_row)
            return

        super().keyPressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(_OPENABLE_EXTS):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            filepath = url.toLocalFile()
            if filepath.lower().endswith(_OPENABLE_EXTS):
                self._load_document(filepath)
                return

    # ---- Dialogs ----

    def _show_about(self):
        QMessageBox.about(
            self, "关于 DocProof",
            "<h3>DocProof</h3>"
            f"<p>中文文档离线校对工具 v{__version__}</p>"
            "<p>校对引擎: pycorrector (Kenlm 统计模型 / MacBERT 深度模型, Apache 2.0)"
            " + 内置标点规范规则</p>"
            "<p>支持格式: .docx（含表格、页眉页脚）/ .txt / .md</p>"
            "<p>模型搜索目录（按优先级）:</p>"
            f"<p>1. <code>{PROJECT_MODELS_DIR}</code></p>"
            f"<p>2. <code>{MODEL_SEARCH_DIRS[1]}</code></p>"
        )

    def _show_model_manager(self):
        """Show the settings dialog for model management."""
        dialog = SettingsDialog(self._engine_manager, self, settings=self._settings)
        dialog.exec()
        # Persist the model that ended up active.
        if self._engine_manager.current_model_key:
            self._settings.set("last_model", self._engine_manager.current_model_key)
        # Update status after settings change
        self._refresh_model_combo()
        if self._engine_manager.is_loaded:
            from docproof.config import MODELS
            key = self._engine_manager.current_model_key
            name = MODELS[key]['name'] if key else '未知'
            self._status_text.setText(f"已切换模型: {name}")

    def _refresh_model_combo(self):
        """Refresh the model selector combo box."""
        self._model_combo.blockSignals(True)
        self._model_combo.clear()

        from docproof.config import MODELS, is_model_available, get_available_model
        current_key = self._engine_manager.current_model_key

        for key, info in MODELS.items():
            label = info['name']
            if not is_model_available(key):
                label += " (需下载)"
            self._model_combo.addItem(label, key)

            # Select current model
            if key == current_key:
                self._model_combo.setCurrentIndex(self._model_combo.count() - 1)

        # If no model loaded, select the first available
        if current_key is None:
            available = get_available_model()
            if available:
                for i in range(self._model_combo.count()):
                    if self._model_combo.itemData(i) == available:
                        self._model_combo.setCurrentIndex(i)
                        break

        self._model_combo.blockSignals(False)

    def _on_model_combo_changed(self, index: int):
        """Handle model selection change from combo box."""
        if index < 0:
            return
        key = self._model_combo.itemData(index)
        if key == self._engine_manager.current_model_key:
            return

        from docproof.config import MODELS
        info = MODELS[key]

        # Show progress feedback during model loading
        def on_progress(msg: str):
            self._status_text.setText(msg)
            QApplication.processEvents()

        self._status_text.setText(f"正在加载: {info['name']}...")
        QApplication.processEvents()

        # Try to load the selected model
        ok, msg = self._engine_manager.load(key, progress_callback=on_progress)
        if ok:
            self._status_text.setText(f"已切换模型: {info['name']}")
            self._status_text.setStyleSheet("color: #16A34A; font-weight: bold;")
        else:
            self._status_text.setText(f"切换失败: {msg.split(chr(10))[0]}")
            self._status_text.setStyleSheet("color: #DC2626;")
            # Revert combo selection
            self._refresh_model_combo()

    # ---- Helpers ----

    def _update_title(self, filepath: str | None = None):
        if filepath:
            self.setWindowTitle(f"{os.path.basename(filepath)} - {APP_NAME}")
        else:
            self.setWindowTitle(APP_NAME)

    def _edit_user_dict(self):
        """Open the user dictionary file for editing."""
        dict_path = self._user_dict.dict_path
        # Ensure file exists
        if not os.path.exists(dict_path):
            self._user_dict._save()
        # Cross-platform open (Windows / macOS / Linux) via Qt.
        QDesktopServices.openUrl(QUrl.fromLocalFile(dict_path))
        QMessageBox.information(
            self, "用户词典",
            "编辑完成后保存文件，然后重新校对即可应用新词典。\n\n"
            "词典位置:\n"
            f"{dict_path}\n\n"
            f"当前词条数: {self._user_dict.word_count}"
        )

    # ---- Recent files ----

    def _recent_files_path(self) -> Path:
        return Path(os.path.expanduser("~/.docproof/recent.json"))

    def _load_recent_files(self):
        try:
            path = self._recent_files_path()
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                self._recent_files = [f for f in data.get("files", [])
                                      if os.path.exists(f)]
        except (OSError, json.JSONDecodeError):
            self._recent_files = []

    def _save_recent_files(self):
        try:
            path = self._recent_files_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"files": self._recent_files}, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except OSError:
            pass

    def _add_recent_file(self, filepath: str):
        filepath = os.path.abspath(filepath)
        if filepath in self._recent_files:
            self._recent_files.remove(filepath)
        self._recent_files.insert(0, filepath)
        self._recent_files = self._recent_files[:5]
        self._save_recent_files()
        self._refresh_recent_menu()

    def _refresh_recent_menu(self):
        if self._recent_menu is None:
            return
        self._recent_menu.clear()
        if not self._recent_files:
            empty = QAction("(无)", self)
            empty.setEnabled(False)
            self._recent_menu.addAction(empty)
        else:
            for f in self._recent_files:
                action = QAction(os.path.basename(f), self)
                action.setToolTip(f)
                action.triggered.connect(
                    lambda checked=False, path=f: self._load_document(path)
                )
                self._recent_menu.addAction(action)
            self._recent_menu.addSeparator()
            clear_action = QAction("清除最近文件列表", self)
            clear_action.triggered.connect(self._clear_recent_files)
            self._recent_menu.addAction(clear_action)

    def _clear_recent_files(self):
        self._recent_files = []
        self._save_recent_files()
        self._refresh_recent_menu()

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
