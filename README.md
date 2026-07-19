# DocProof - 中文文档离线校对工具

一款基于 AI 的中文文档校对桌面软件，支持 Word (.docx)、纯文本 (.txt/.md)，模型下载后可完全离线使用。

## 功能

- 拖入文档，自动扫描错别字与标点/格式规范问题
- 校对范围覆盖正文、**表格单元格、页眉页脚**
- 三种导出：直接修改、**Word 原生修订（可在 Word/WPS 逐条接受/拒绝）**、彩色标记
- 支持逐条接受/忽略/加入白名单，可导出校对报告 (HTML/TXT)
- **批量校对整个文件夹**
- 可调 MacBERT 灵敏度，设置持久化
- 模型下载到本地后完全离线运行，数据不出本机
- 跨平台（macOS / Windows / Linux）

> **关于"离线"**：Kenlm 模型为本地 `.klm` 文件，放好即可离线。MacBERT 深度模型
> 首次使用需联网从 HuggingFace 下载约 400MB 权重到 `models/macbert_cache/`，
> 下载后即可离线运行。程序会优先选择本地已就绪的模型。

> **关于 WPS/.doc**：暂不支持 `.doc`、`.wps` 等旧二进制格式，请在 Word/WPS 中
> 「另存为」`.docx` 后再打开。

> **校对能力说明**：错别字纠错由统计/深度模型完成；"语法"层面目前提供高精度的
> **标点与格式规范检查**（半角标点、汉字间多余空格、重复标点），复杂句法语法
> 检查不在当前范围内。

## 参考项目

| 项目 | 说明 | 许可证 | 集成方式 |
|------|------|--------|----------|
| [pycorrector](https://github.com/shibing624/pycorrector) | 中文文本纠错引擎，提供 Kenlm/MacBERT/T5/Qwen 多级模型 | Apache 2.0 | 源码直接集成于 `third_party/pycorrector/`，可直接修改 |
| [LanguageTool](https://github.com/languagetool-org/languagetool) | 多语言校对引擎，拥有成熟的文档插件架构 | LGPL 2.1 | 架构参考，源码位于本地 `references/`（未上传） |

## 技术栈

- **校对引擎**: pycorrector（Kenlm 统计模型 + MacBERT 深度学习模型）+ 内置标点规范规则
- **GUI 框架**: PySide6 (Qt for Python, LGPL)
- **文档处理**: python-docx
- **打包分发**: PyInstaller

## 文档导航

| 文档 | 内容 |
|------|------|
| [PLAN.md](PLAN.md) | 架构设计、模块划分、实现阶段 |
| [REFERENCES.md](REFERENCES.md) | 参考项目开发指南（写代码时看哪个文件） |

## 运行原理

→ 见下方说明，或 [PLAN.md](PLAN.md) 中的"校对引擎层"章节

## 项目结构

```
docproof/                   # 本项目的应用包
third_party/pycorrector/    # 集成的 pycorrector 源码（可直接修改）
references/                 # 本地参考项目（不参与构建）
```

## 许可证

本项目: MIT License

`third_party/pycorrector/`: Apache License 2.0（原始许可证不变）
