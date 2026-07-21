"""Settings dialog — model selection and management."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from docproof.config import (
    MODELS,
    MODEL_SEARCH_DIRS,
    is_model_available,
    get_model_path,
    _check_dependencies,
)
from docproof.engine.engine_manager import EngineManager
from docproof.ui.welcome_wizard import WelcomeWizard


class SettingsDialog(QDialog):
    """Settings dialog with model management."""

    def __init__(self, engine_manager: EngineManager, parent=None, settings=None):
        super().__init__(parent)
        self._engine_manager = engine_manager
        self._settings = settings
        self.setWindowTitle("设置")
        self.setMinimumSize(560, 520)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # ---- Model Selection ----
        model_group = QGroupBox("语言模型选择")
        model_layout = QVBoxLayout(model_group)

        desc = QLabel("选择一个已下载的模型，切换后立即生效：")
        desc.setStyleSheet("color: #666;")
        model_layout.addWidget(desc)

        self.model_list = QListWidget()
        self.model_list.setMinimumHeight(140)
        self.model_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #DDD;
                border-radius: 4px;
                background: #FAFAFA;
            }
            QListWidget::item { padding: 8px 12px; }
            QListWidget::item:selected { background: #EFF6FF; color: black; }
        """)
        self._refresh_model_list()
        model_layout.addWidget(self.model_list)

        self.model_status = QLabel()
        self.model_status.setStyleSheet("color: #888; padding: 4px;")
        model_layout.addWidget(self.model_status)

        btn_layout = QHBoxLayout()
        self.apply_btn = QPushButton("切换到此模型")
        self.apply_btn.clicked.connect(self._switch_model)
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background: #2563EB; color: white;
                padding: 6px 16px; border-radius: 4px;
            }
            QPushButton:disabled { background: #AAA; }
        """)
        btn_layout.addWidget(self.apply_btn)

        btn_layout.addStretch()

        self.download_btn = QPushButton("下载更多模型...")
        self.download_btn.clicked.connect(self._open_wizard)
        btn_layout.addWidget(self.download_btn)

        model_layout.addLayout(btn_layout)
        layout.addWidget(model_group)

        # ---- Proofreading options ----
        opt_group = QGroupBox("校对选项")
        opt_layout = QVBoxLayout(opt_group)

        thr_row = QHBoxLayout()
        thr_row.addWidget(QLabel("MacBERT 灵敏度:"))
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setMinimum(10)   # 0.10
        self.threshold_slider.setMaximum(90)   # 0.90
        cur_thr = int(round((self._settings.threshold if self._settings else 0.5) * 100))
        self.threshold_slider.setValue(max(10, min(90, cur_thr)))
        self.threshold_value = QLabel(f"{self.threshold_slider.value()/100:.2f}")
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)
        thr_row.addWidget(self.threshold_slider)
        thr_row.addWidget(self.threshold_value)
        opt_layout.addLayout(thr_row)
        hint = QLabel("数值越低越敏感（发现更多，可能误报）；越高越保守。")
        hint.setStyleSheet("color:#888; font-size:12px;")
        opt_layout.addWidget(hint)

        self.rule_check = QCheckBox("启用标点/规范检查")
        enabled = self._settings.rule_check_enabled if self._settings \
            else self._engine_manager.rule_check_enabled
        self.rule_check.setChecked(enabled)
        self.rule_check.toggled.connect(self._on_rule_toggled)
        opt_layout.addWidget(self.rule_check)

        # Per-rule sub-options
        def _sub(key: str, label: str):
            cb = QCheckBox(label)
            cb.setStyleSheet("margin-left: 24px;")
            checked = bool(self._settings.get(key, True)) if self._settings else True
            cb.setChecked(checked)
            cb.toggled.connect(lambda on, k=key: self._on_rule_option(k, on))
            cb.setEnabled(enabled)
            opt_layout.addWidget(cb)
            return cb

        self.rule_ascii = _sub("rule_ascii_punct", "半角标点（如 , : → ，：）")
        self.rule_space = _sub("rule_han_space", "汉字之间的多余空格")
        self.rule_repeat = _sub("rule_repeat_punct", "重复标点（如 。。 → 。）")
        self.rule_check.toggled.connect(self._sync_rule_subs)

        self.parallel_check = QCheckBox("多核并行（仅超大文档、Kenlm 模型）")
        par = bool(self._settings.get("parallel_enabled", False)) if self._settings else False
        self.parallel_check.setChecked(par)
        self.parallel_check.toggled.connect(self._on_parallel_toggled)
        opt_layout.addWidget(self.parallel_check)
        par_hint = QLabel("每个进程需重新加载模型，仅超长文档（>200段）受益。")
        par_hint.setStyleSheet("color:#888; font-size:12px;")
        opt_layout.addWidget(par_hint)

        layout.addWidget(opt_group)

        # ---- Model directories ----
        dir_group = QGroupBox("模型搜索目录")
        dir_layout = QVBoxLayout(dir_group)
        for i, d in enumerate(MODEL_SEARCH_DIRS):
            prefix = "→ " if i == 0 else "  "
            exists = "✓" if os.path.isdir(d) else "✗"
            dir_layout.addWidget(QLabel(f"{prefix}{exists} {d}"))
        layout.addWidget(dir_group)

        # ---- Close button ----
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

    def _on_threshold_changed(self, value: int):
        thr = value / 100.0
        self.threshold_value.setText(f"{thr:.2f}")
        self._engine_manager.set_threshold(thr)
        if self._settings:
            self._settings.set("macbert_threshold", thr)

    def _on_rule_toggled(self, checked: bool):
        self._engine_manager.set_rule_check(checked)
        if self._settings:
            self._settings.set("rule_check_enabled", checked)

    def _sync_rule_subs(self, enabled: bool):
        for cb in (self.rule_ascii, self.rule_space, self.rule_repeat):
            cb.setEnabled(enabled)

    def _on_rule_option(self, key: str, checked: bool):
        mapping = {
            "rule_ascii_punct": "ascii_punct",
            "rule_han_space": "han_space",
            "rule_repeat_punct": "repeat_punct",
        }
        self._engine_manager.set_rule_options(**{mapping[key]: checked})
        if self._settings:
            self._settings.set(key, checked)

    def _on_parallel_toggled(self, checked: bool):
        self._engine_manager.set_parallel(checked)
        if self._settings:
            self._settings.set("parallel_enabled", checked)

    def _refresh_model_list(self):
        """Refresh the model list showing status of each model."""
        self.model_list.clear()
        current_key = self._engine_manager.current_model_key

        for key, info in MODELS.items():
            ready = is_model_available(key)
            engine_type = info.get("engine_type", "kenlm")

            if engine_type == "macbert":
                # MacBERT: check if torch/transformers installed
                deps_ok = _check_dependencies(info.get("requires", []))
                if deps_ok:
                    status = "✓ 依赖已安装，首次使用自动下载模型"
                    color = Qt.GlobalColor.black
                else:
                    status = "需要安装 torch, transformers"
                    color = Qt.GlobalColor.gray
                size_text = "~400MB"
            else:
                # Kenlm: check if .klm file exists
                path = get_model_path(key)
                if path and os.path.exists(path):
                    size_text = f"{os.path.getsize(path)/1024/1024:.0f}MB"
                    status = "✓ 已下载"
                    color = Qt.GlobalColor.black
                else:
                    size_text = f"{info['size_mb']}MB"
                    status = "未下载"
                    color = Qt.GlobalColor.gray

            active = " [当前使用]" if key == current_key else ""
            rec = " ★推荐" if info.get("recommended") else ""
            text = f"{info['name']} — {status} ({size_text}){active}{rec}"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setForeground(color)

            if key == current_key:
                font = item.font()
                font.setBold(True)
                item.setFont(font)

            self.model_list.addItem(item)

        # Select current model
        if current_key:
            for i in range(self.model_list.count()):
                if self.model_list.item(i).data(Qt.ItemDataRole.UserRole) == current_key:
                    self.model_list.setCurrentRow(i)
                    break

    def _switch_model(self):
        """Switch to the selected model."""
        item = self.model_list.currentItem()
        if item is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        info = MODELS[key]
        engine_type = info.get("engine_type", "kenlm")

        # For kenlm, verify file exists
        if engine_type == "kenlm":
            path = get_model_path(key)
            if not path or not os.path.exists(path):
                self.model_status.setText(
                    f"模型文件不存在，请下载后放入 models/ 目录:\n"
                    f"{info.get('url', '')}"
                )
                self.model_status.setStyleSheet("color: #DC2626; padding: 4px;")
                return

        # For macbert, check dependencies
        if engine_type == "macbert":
            deps_ok = _check_dependencies(info.get("requires", []))
            if not deps_ok:
                self.model_status.setText(
                    "MacBERT 需要额外依赖，请在终端运行:\n"
                    "  pip install torch transformers\n\n"
                    "安装完成后重新点击「切换到此模型」。"
                )
                self.model_status.setStyleSheet("color: #DC2626; padding: 4px;")
                return

        ok, msg = self._engine_manager.load(key)
        if ok:
            self.model_status.setText(f"✓ {msg}")
            self.model_status.setStyleSheet(
                "color: #16A34A; font-weight: bold; padding: 4px;"
            )
            self._refresh_model_list()
        else:
            self.model_status.setText(f"✗ {msg}")
            self.model_status.setStyleSheet("color: #DC2626; padding: 4px;")

    def _open_wizard(self):
        """Open the welcome wizard for downloading more models."""
        wizard = WelcomeWizard(self)
        wizard.exec()
        self._refresh_model_list()
