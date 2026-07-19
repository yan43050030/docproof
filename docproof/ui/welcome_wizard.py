"""First-run welcome wizard: guides user to download and place the language model."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from docproof.config import (
    MODELS,
    MODEL_SEARCH_DIRS,
    PROJECT_MODELS_DIR,
    DEFAULT_MODEL,
    get_available_model,
)


class WelcomeWizard(QDialog):
    """First-run dialog that shows model download instructions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DocProof - 首次运行设置")
        self.setMinimumSize(620, 480)
        self.setModal(True)
        self._selected_model = None
        self._setup_ui()
        self._check_models()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel("欢迎使用 DocProof 中文文档校对工具")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("首次使用需要下载语言模型。请按以下步骤操作：")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # Step 1: Model list
        step1 = QLabel("<b>步骤 1：选择一个模型（推荐标准模型）</b>")
        layout.addWidget(step1)

        self.model_list = QListWidget()
        self.model_list.setMinimumHeight(100)
        for key, info in MODELS.items():
            item = QListWidgetItem()
            item.setText(f"{info['name']}  —  {info['description']}  [{info['size_mb']}MB]")
            item.setData(Qt.ItemDataRole.UserRole, key)
            if info.get("recommended"):
                item.setSelected(True)
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.model_list.addItem(item)
        self.model_list.currentItemChanged.connect(self._on_model_selected)
        layout.addWidget(self.model_list)

        # Step 2: Download URL
        step2 = QLabel("<b>步骤 2：复制下载地址，在浏览器或下载工具中下载</b>")
        layout.addWidget(step2)

        url_layout = QHBoxLayout()
        self.url_display = QTextEdit()
        self.url_display.setReadOnly(True)
        self.url_display.setMaximumHeight(50)
        self.url_display.setPlaceholderText("请在上面选择一个模型...")
        url_layout.addWidget(self.url_display)

        self.copy_btn = QPushButton("复制地址")
        self.copy_btn.clicked.connect(self._copy_url)
        self.copy_btn.setEnabled(False)
        url_layout.addWidget(self.copy_btn)

        self.open_btn = QPushButton("浏览器打开")
        self.open_btn.clicked.connect(self._open_url)
        self.open_btn.setEnabled(False)
        url_layout.addWidget(self.open_btn)

        layout.addLayout(url_layout)

        # Step 3: Target folder
        step3 = QLabel(
            "<b>步骤 3：下载完成后，将模型文件放入以下文件夹（任选其一）</b>"
            "<br><span style='color:#2563EB;'>推荐放入项目目录，方便拷贝分发</span>"
        )
        layout.addWidget(step3)

        # Primary: project-local
        folder_layout1 = QHBoxLayout()
        label1 = QLabel("推荐 → 项目内:  ")
        label1.setStyleSheet("color: #2563EB; font-weight: bold;")
        folder_layout1.addWidget(label1)
        self.folder_display = QTextEdit()
        self.folder_display.setReadOnly(True)
        self.folder_display.setMaximumHeight(36)
        self.folder_display.setPlainText(PROJECT_MODELS_DIR)
        folder_layout1.addWidget(self.folder_display)
        self.folder_btn1 = QPushButton("打开")
        self.folder_btn1.clicked.connect(lambda: self._open_folder(PROJECT_MODELS_DIR))
        folder_layout1.addWidget(self.folder_btn1)
        layout.addLayout(folder_layout1)

        # Secondary: user data dir
        folder_layout2 = QHBoxLayout()
        label2 = QLabel("备选 → 用户目录:  ")
        label2.setStyleSheet("color: #888;")
        folder_layout2.addWidget(label2)
        self.folder_display2 = QTextEdit()
        self.folder_display2.setReadOnly(True)
        self.folder_display2.setMaximumHeight(36)
        self.folder_display2.setPlainText(MODEL_SEARCH_DIRS[1])
        folder_layout2.addWidget(self.folder_display2)
        self.folder_btn2 = QPushButton("打开")
        self.folder_btn2.clicked.connect(lambda: self._open_folder(MODEL_SEARCH_DIRS[1]))
        folder_layout2.addWidget(self.folder_btn2)
        layout.addLayout(folder_layout2)

        # Status
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #888;")
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("刷新检测")
        self.refresh_btn.clicked.connect(self._check_models)
        btn_layout.addWidget(self.refresh_btn)

        btn_layout.addStretch()

        self.start_btn = QPushButton("开始使用")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.accept)
        self.start_btn.setMinimumWidth(120)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                padding: 8px 24px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #AAA;
            }
        """)
        btn_layout.addWidget(self.start_btn)

        layout.addLayout(btn_layout)

        # Select recommended model
        for i in range(self.model_list.count()):
            item = self.model_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == DEFAULT_MODEL:
                self.model_list.setCurrentItem(item)
                break

    def _on_model_selected(self, current, previous):
        if current is None:
            return
        key = current.data(Qt.ItemDataRole.UserRole)
        info = MODELS[key]
        self.url_display.setPlainText(info["url"])
        self._selected_model = key
        self.copy_btn.setEnabled(True)
        self.open_btn.setEnabled(True)

        filename = info["filename"]
        self.status_label.setText(
            f"请下载文件: {filename} ({info['size_mb']}MB)\n"
            f"下载后放入项目 models/ 目录"
        )

    def _copy_url(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.url_display.toPlainText())
        self.status_label.setText("地址已复制到剪贴板！")

    def _open_url(self):
        url = self.url_display.toPlainText()
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _open_folder(self, path: str):
        os.makedirs(path, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _check_models(self):
        """Check if any model files are present and update UI."""
        available = get_available_model()
        if available:
            from docproof.config import get_model_path as gmp
            info = MODELS[available]
            path = gmp(available)
            self.start_btn.setEnabled(True)
            self.status_label.setText(
                f"✓ 已检测到模型: {info['filename']}\n"
                f"位置: {path}\n"
                f"可以开始使用了！"
            )
            self.status_label.setStyleSheet("color: #16A34A; font-weight: bold;")
            for i in range(self.model_list.count()):
                item = self.model_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == available:
                    self.model_list.setCurrentItem(item)
                    break
        else:
            self.start_btn.setEnabled(False)
            self.status_label.setText(
                "尚未检测到模型文件。\n"
                f"请下载后放入: {PROJECT_MODELS_DIR}\n"
                f"或: {MODEL_SEARCH_DIRS[1]}"
            )
            self.status_label.setStyleSheet("color: #DC2626;")

    def get_selected_model(self) -> str | None:
        """Return the model key the user wants to use."""
        return self._selected_model or get_available_model()
