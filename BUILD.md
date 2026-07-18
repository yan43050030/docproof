# DocProof 构建指南

## Windows 便携版构建

### 自动构建（推荐）

推送 `v*` 标签即可触发 GitHub Actions 自动构建：

```bash
git tag v0.1.0
git push origin v0.1.0
```

构建完成后在 [Releases](https://github.com/yan43050030/docproof/releases) 下载 `DocProof-windows-portable.zip`。

解压后放入模型文件到 `models/` 目录，双击 `DocProof.exe` 即可使用。

### 手动构建（在 Windows 上）

**前置条件：**
- Python 3.10+ ([下载](https://www.python.org/downloads/))
- Git ([下载](https://git-scm.com/download/win))

**步骤：**

```batch
# 1. 克隆项目
git clone https://github.com/yan43050030/docproof.git
cd docproof

# 2. 运行构建脚本
scripts\build_portable.bat
```

构建完成后便携版位于 `dist\DocProof-portable\`。

---

## 便携版结构

```
DocProof-portable/
├── DocProof.exe              ← 双击启动
├── models/                   ← 模型文件放这里
│   ├── people2014corpus_chars.klm   (141MB, 推荐)
│   └── zh_giga.no_cna_cmn.prune01244.klm  (2.95GB, 最优)
├── pycorrector/              ← 校对引擎
├── _internal/                ← Python 运行时
└── 使用说明.txt
```

---

## 在 macOS 上开发运行

```bash
# 创建虚拟环境（需要 Python 3.12）
python3.12 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 下载模型到 models/ 目录（选其一）
# 标准模型 141MB:
curl -L -o models/people2014corpus_chars.klm \
  https://github.com/shibing624/pycorrector/releases/download/1.0.0/people2014corpus_chars.klm

# 大模型 2.95GB:
curl -L -o models/zh_giga.no_cna_cmn.prune01244.klm \
  https://deepspeech.bj.bcebos.com/zh_lm/zh_giga.no_cna_cmn.prune01244.klm

# 启动
python -m docproof
```

---

## 模型选择

| 模型 | 文件 | 大小 | 质量 |
|------|------|------|------|
| kenlm-base (推荐) | people2014corpus_chars.klm | 141MB | 好 |
| kenlm-large | zh_giga.no_cna_cmn.prune01244.klm | 2.95GB | 最好 |

启动后在 **帮助 → 管理语言模型** 中可以随时切换。
