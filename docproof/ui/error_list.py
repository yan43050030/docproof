"""Side panel listing all proofreading errors."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from docproof.engine.base_engine import ErrorItem


class ErrorListPanel(QWidget):
    """Panel showing a list of errors with accept/ignore buttons."""

    error_selected = Signal(int)  # error index
    error_accepted = Signal(int)  # error index
    error_ignored = Signal(int)  # error index
    accept_all = Signal()  # accept all errors at once

    def __init__(self, parent=None):
        super().__init__(parent)
        self._errors: list[ErrorItem] = []
        self._ignored: set[int] = set()
        self._accepted: set[int] = set()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel("校对结果")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title.setFont(title_font)
        header.addWidget(title)

        header.addStretch()

        self.count_label = QLabel("0 处")
        self.count_label.setStyleSheet("color: #888;")
        header.addWidget(self.count_label)

        layout.addLayout(header)

        # Error list
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                background: #FAFAFA;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #EEE;
            }
            QListWidget::item:selected {
                background: #EFF6FF;
                color: black;
            }
            QListWidget::item:alternate {
                background: #F5F5F5;
            }
        """)
        layout.addWidget(self.list_widget)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.accept_all_btn = QPushButton("✓ 全部接受")
        self.accept_all_btn.setStyleSheet("""
            QPushButton {
                background: #2563EB;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1D4ED8; }
        """)
        self.accept_all_btn.clicked.connect(self._accept_all)
        btn_layout.addWidget(self.accept_all_btn)

        self.accept_btn = QPushButton("✓ 接受")
        self.accept_btn.setStyleSheet("""
            QPushButton {
                background: #16A34A;
                color: white;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #15803D; }
        """)
        self.accept_btn.clicked.connect(self._accept_current)
        btn_layout.addWidget(self.accept_btn)

        self.ignore_btn = QPushButton("忽略")
        self.ignore_btn.setStyleSheet("""
            QPushButton {
                background: #9CA3AF;
                color: white;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #6B7280; }
        """)
        self.ignore_btn.clicked.connect(self._ignore_current)
        btn_layout.addWidget(self.ignore_btn)

        layout.addLayout(btn_layout)

    def set_errors(self, errors: list[ErrorItem]) -> None:
        """Load a new set of errors."""
        self._errors = errors
        self._ignored = set()
        self._accepted = set()
        self._rebuild_list()

    def _rebuild_list(self) -> None:
        """Rebuild the list widget from current state."""
        self.list_widget.clear()

        visible_count = 0
        for i, err in enumerate(self._errors):
            if i in self._ignored or i in self._accepted:
                continue
            visible_count += 1

            text = f"{err.error} → {err.correct}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, i)

            self.list_widget.addItem(item)

        self.count_label.setText(f"{visible_count} 处")
        self.accept_all_btn.setEnabled(visible_count > 0)

    def _on_row_changed(self, row: int) -> None:
        if row >= 0:
            item = self.list_widget.item(row)
            idx = item.data(Qt.ItemDataRole.UserRole)
            self.error_selected.emit(idx)

    def _accept_current(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        self._accepted.add(idx)
        self.error_accepted.emit(idx)
        self._rebuild_list()

    def _accept_all(self) -> None:
        """Accept all remaining visible errors."""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item is None:
                continue
            idx = item.data(Qt.ItemDataRole.UserRole)
            self._accepted.add(idx)
        self.accept_all.emit()
        self._rebuild_list()

    def _ignore_current(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        self._ignored.add(idx)
        self.error_ignored.emit(idx)
        self._rebuild_list()

    def get_accepted_errors(self) -> list[ErrorItem]:
        """Get list of accepted corrections."""
        return [self._errors[i] for i in self._accepted]

    def get_remaining_errors(self) -> list[ErrorItem]:
        """Get errors that haven't been accepted or ignored."""
        remaining = []
        for i, err in enumerate(self._errors):
            if i not in self._ignored and i not in self._accepted:
                remaining.append(err)
        return remaining

    @property
    def accepted_indices(self) -> set[int]:
        return self._accepted
