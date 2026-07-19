# DocProof 实现计划

## 一、项目目标

开发一款**完全离线**的中文文档校对桌面软件，支持 Word (.docx) 和 WPS 文档，以修订模式显示修改建议。

### 核心功能

1. 拖放或选择文档，自动扫描错别字、语法错误
2. 以修订模式显示修改（原文红色删除线 + 建议蓝色）
3. 逐条接受/忽略/加入白名单
4. 导出修订后的文档，可选择保留修订标记或直接应用修改
5. 完全离线运行，无需网络，数据不出本机

### 技术亮点

- **双引擎架构**：轻量统计模型（实时校对）+ 深度学习模型（深度校对）
- **文档格式完整保留**：校对仅替换文本，不改字体、字号、颜色等格式
- **用户词典**：支持自定义混淆集、白名单，持续学习用户偏好

---

## 二、参考项目分析

### pycorrector（主要参考）

- **定位**：中文文本纠错工具包，提供从统计模型到 LLM 的多级纠错方案
- **可复用部分**：
  - `Corrector` 类（Kenlm 统计模型，150MB，CPU 运行）
  - `MacBertCorrector` 类（MacBERT 深度学习，400MB，F1=0.83）
  - 同音字/形似字混淆集数据
  - 自定义混淆集机制
- **API 返回格式**：`{'source': str, 'target': str, 'errors': [(错词, 正词, 位置), ...]}`
- **许可证**：Apache 2.0

### LanguageTool（架构参考）

- **定位**：多语言校对引擎，成熟的文档插件体系
- **可借鉴部分**：
  - Office 插件架构：`XProofreader` UNO 组件 → `SingleDocument` → `DocumentCache` 分层
  - 文本提取→校对→定位回写的管道模式
  - 后台队列机制处理长文档
  - FlatParagraph 遍历实现格式无损替换
  - 校对结果展示：波浪线（被动）+ 对话框（主动）双模式
- **局限性**：中文支持极弱（仅 1863 条规则，无拼写检查），不能直接用于中文校对
- **许可证**：LGPL 2.1

---

## 三、架构设计

```
┌─────────────────────────────────────────────────────┐
│                   GUI 层 (PySide6)                      │
│                                                       │
│  ┌──────────┐  ┌──────────────────────────────────┐  │
│  │ 文件管理  │  │         修订模式显示区            │  │
│  │          │  │                                  │  │
│  │ - 拖放   │  │  原句: 少先队员[因该]为老人[让坐]  │  │
│  │ - 打开   │  │        ~~红色删除线~~  ~~红色~~    │  │
│  │ - 最近   │  │  改后: 少先队员[应该]为老人[让座]  │  │
│  │          │  │        蓝色粗体       蓝色粗体     │  │
│  ├──────────┤  ├──────────────────────────────────┤  │
│  │ 校对控制  │  │         错误列表 (侧栏)           │  │
│  │          │  │  ┌─────────────────────────────┐  │  │
│  │ - 开始   │  │  │ 1. 因该 → 应该    [接受][忽略]│  │  │
│  │ - 暂停   │  │  │ 2. 让坐 → 让座    [接受][忽略]│  │  │
│  │ - 模式   │  │  │ 3. ...                      │  │  │
│  │          │  │  └─────────────────────────────┘  │  │
│  ├──────────┤  ├──────────────────────────────────┤  │
│  │ 导出     │  │         状态栏                     │  │
│  │ - 导出   │  │  已检查: 1200字 | 发现: 5处 | ✓  │  │
│  └──────────┘  └──────────────────────────────────┘  │
├─────────────────────────────────────────────────────┤
│                 文档处理层                            │
│                                                       │
│  DocxHandler: python-docx 读写 .docx                 │
│  - extract_text(): 段落级提取，记录 run 级位置        │
│  - apply_corrections(): 按位置写回，保留原格式         │
│  - 表格/页眉页脚/文本框 单独处理                       │
├─────────────────────────────────────────────────────┤
│                 校对引擎层                            │
│                                                       │
│  EngineManager: 统一管理多个引擎                      │
│  ├── KenlmEngine: 150MB 小模型，CPU 实时 (QPS≈9)     │
│  ├── MacBertEngine: 400MB，CPU 可用 (QPS≈224)        │
│  └── 用户词典: 自定义混淆集 + 白名单                   │
│                                                       │
│  输出统一格式: [{error_word, correct_word, position}] │
└─────────────────────────────────────────────────────┘
```

### 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| GUI 框架 | PySide6 | 成熟稳定，支持富文本渲染，跨平台 |
| 默认引擎 | Kenlm 小模型 | 150MB，CPU 友好，下载量小，适合离线分发 |
| 文档格式 | 先支持 .docx，后续 .txt/.wps | .docx 最通用，python-docx 成熟 |
| 修订定位 | 字符级（非段落级） | pycorrector 返回字符位置，天然支持精确定位 |
| 打包工具 | PyInstaller | 最成熟的 Python 打包方案 |

---

## 四、模块划分

### 模块 1：校对引擎封装 (`docproof/engine/`)

**职责**：封装 pycorrector，提供统一的校对接口

```
engine/
├── __init__.py
├── base_engine.py        # 引擎基类，定义统一接口
├── kenlm_engine.py       # Kenlm 统计模型引擎
├── macbert_engine.py     # MacBERT 深度学习引擎（可选，需 pip install torch）
├── engine_manager.py     # 引擎管理器，切换/加载/卸载
└── user_dict.py          # 用户词典管理（混淆集+白名单）
```

**统一接口**：
```python
class BaseEngine:
    def correct(self, text: str) -> list[dict]:
        """返回 [{'error': str, 'correct': str, 'start': int, 'end': int}]"""
    def load(self): ...
    def unload(self): ...
```

### 模块 2：文档处理 (`docproof/document/`)

**职责**：读写 Word 文档，提取文本，定位回写

```
document/
├── __init__.py
├── docx_handler.py       # .docx 读写
├── text_handler.py       # 纯文本处理
└── position_mapper.py    # 字符偏移 ↔ 文档位置映射
```

**核心难点——位置映射**：

python-docx 的最小文本单元是 `run`（一段连续相同格式的文本）。段落内可能有多个 run。校对引擎返回的是全文中的字符位置，需要反向映射到具体的 run 和 run 内偏移。

```python
# 建立映射
class PositionMapper:
    def build_map(self, paragraphs: list) -> None:
        """遍历所有 paragraph → run，记录每个字符的 (run, offset_in_run)"""
    def char_to_run(self, char_pos: int) -> (Run, int):
        """给定全文字符位置，返回对应的 run 对象和 run 内偏移"""
```

### 模块 3：GUI 界面 (`docproof/ui/`)

**职责**：PySide6 桌面界面

```
ui/
├── __init__.py
├── main_window.py        # 主窗口
├── correction_view.py    # 修订模式显示组件（核心）
├── error_list.py         # 错误列表面板
├── toolbar.py            # 工具栏
├── file_drop_area.py     # 拖放区域
└── dialogs/
    ├── settings.py       # 设置对话框（切换引擎、用户词典等）
    └── export.py         # 导出选项对话框
```

**修订模式显示方案**：

使用 `QTextEdit` 的 HTML 渲染能力，将校对结果显示为：
- 原文错误词：`<span style='color:red; text-decoration:line-through;'>因该</span>`
- 修改建议词：`<span style='color:#2563eb; font-weight:bold;'>应该</span>`

两种显示模式可切换：
1. **修订模式**：原文+标记，错误词红色删除线，改后词蓝色紧邻显示
2. **预览模式**：直接显示校对后的文本

### 模块 4：应用入口 (`docproof/`)

```
docproof/
├── __init__.py
├── __main__.py           # python -m docproof 入口
├── app.py                # 应用初始化、引擎预加载
├── config.py             # 配置管理（模型路径、用户词典路径等）
└── resources/            # 图标等静态资源
```

---

## 五、实现阶段

### 第一阶段：核心管道（MVP）— 约 4-5 天

**目标**：跑通"读文档 → 校对 → 显示结果 → 导出"的完整管道

- [ ] 搭建项目骨架和开发环境
- [ ] 实现 `engine/kenlm_engine.py`，封装 pycorrector Corrector
- [ ] 实现 `document/docx_handler.py`，提取段落文本
- [ ] 实现 `document/position_mapper.py`，字符位置→文档位置映射
- [ ] 命令行工具验证：`python -m docproof --file test.docx --output result.docx`

### 第二阶段：GUI 界面 — 约 4-5 天

**目标**：可用的桌面应用

- [ ] 主窗口框架（菜单栏、工具栏、状态栏）
- [ ] 拖放区域 + 文件选择对话框
- [ ] 修订模式视图（QTextEdit + HTML 渲染）
- [ ] 错误列表面板（可点击定位）
- [ ] 接受/忽略/白名单 交互
- [ ] 导出功能（保留修订 / 直接应用）

### 第三阶段：增强与优化 — 约 3-4 天

**目标**：更好的体验和性能

- [ ] MacBERT 引擎集成（可选启用）
- [ ] 引擎切换（轻量/深度模式）
- [ ] 设置对话框（自定义词典、模型选择）
- [ ] 长文档分段校对 + 进度条
- [ ] 校对结果缓存（避免重复校对）
- [ ] 表格/页眉页脚支持

### 第四阶段：打包与发布 — 约 2 天

**目标**：可分发的一键安装包

- [ ] PyInstaller 配置
- [ ] macOS .app 打包 + 签名
- [ ] Windows .exe 打包（需 Windows 环境）
- [ ] 模型文件自动下载/首次启动引导

---

## 六、技术要点

### 6.1 python-docx 格式保留

python-docx 操作 `run` 级别。校对只替换 `run.text`，不改变 `run.font` 相关属性，即可保留格式。

```python
def apply_correction(run, offset_in_run, error_len, correct_word):
    """在 run 内替换指定位置的文本，保留格式"""
    original = run.text
    run.text = original[:offset_in_run] + correct_word + original[offset_in_run + error_len:]
```

### 6.2 模型首次下载

首次运行时自动下载 Kenlm 模型（约 150MB）到 `~/.docproof/models/`，有进度提示。后续完全离线。

### 6.3 分段校对策略

长文档不能整篇丢给引擎（Kenlm 按句子切分后分别处理）。流程：
1. 按段落分割文档
2. 每个段落按标点符号切句子
3. 逐句校对
4. 合并结果

---

## 七、目录结构总览

```
docproof/
├── README.md
├── PLAN.md                    # 本文件
├── LICENSE                    # MIT
├── .gitignore
├── pyproject.toml             # 项目配置和依赖
├── third_party/               # 集成的第三方源码（可修改）
│   └── pycorrector/           # 中文纠错引擎（fork 自 shibing624/pycorrector, Apache 2.0）
├── references/                # 参考项目源码（本地，gitignored）
│   └── languagetool/          # 浅克隆
│
├── docproof/                  # 主包
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.py
│   ├── config.py
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── base_engine.py
│   │   ├── kenlm_engine.py
│   │   ├── macbert_engine.py
│   │   ├── engine_manager.py
│   │   └── user_dict.py
│   ├── document/
│   │   ├── __init__.py
│   │   ├── docx_handler.py
│   │   ├── text_handler.py
│   │   └── position_mapper.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py
│   │   ├── correction_view.py
│   │   ├── error_list.py
│   │   ├── toolbar.py
│   │   ├── file_drop_area.py
│   │   └── dialogs/
│   │       ├── settings.py
│   │       └── export.py
│   └── resources/
│       └── icon.png
│
└── tests/
    ├── test_engine.py
    ├── test_document.py
    └── test_data/
        └── sample.docx
```

---

## 八、依赖项

```toml
[project]
name = "docproof"
requires-python = ">=3.10"
dependencies = [
    "pycorrector>=1.1.0",    # 校对引擎
    "kenlm",                  # 语言模型
    "python-docx>=1.0.0",    # Word 文档读写
    "PySide6>=6.5.0",        # GUI 框架
]

[project.optional-dependencies]
deep = [
    "torch>=2.0.0",          # MacBERT 引擎（需要时安装）
    "transformers>=4.30.0",
]

dev = [
    "pytest>=7.0.0",
    "pyinstaller>=6.0.0",
]
```

---

## 九、风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| python-docx 对复杂格式（批注、修订、公式）支持有限 | 部分文档校对后可能丢失特殊元素 | 先支持常规文本段落，特殊元素跳过并提示 |
| MacBERT 需 PyTorch，打包后体积大（>2GB） | 下载分发困难 | 默认内置 Kenlm（150MB 小模型），MacBERT 作为可选升级 |
| Kenlm 模型准确度不如深度学习 | 部分错误检不出 | 提供自定义混淆集入口，用户可自行扩展 |
| WPS 文档格式（.wps）无 Python 库支持 | WPS 支持延期 | 先支持 .docx，WPS 用户另存为 .docx 后使用 |
| macOS/Windows 打包兼容性差异 | 跨平台体验不一致 | CI 中分别构建和测试 |

---

## 十、许可兼容性

| 组件 | 许可证 | 是否可商用 |
|------|--------|------------|
| pycorrector | Apache 2.0 | 是 |
| kenlm | MIT | 是 |
| python-docx | MIT | 是 |
| PySide6 | LGPL v3 | 允许闭源商用，无需购买 |
| LanguageTool（仅参考架构） | LGPL 2.1 | 参考架构不引入代码，无许可问题 |
| DocProof 本身 | Apache 2.0 | 是 |

> **说明**：项目使用 PySide6（LGPL 许可），允许闭源商用。
