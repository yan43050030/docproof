# DocProof - 中文文档离线校对工具

一款基于 AI 的中文文档校对桌面软件，支持 Word (.docx) 和 WPS 文档，可完全离线使用。

## 目标

- 拖入文档，自动扫描错别字、语法错误
- 以"修订模式"显示修改建议（类似 Word 修订）
- 支持逐条接受/忽略/加入白名单
- 完全离线运行，数据不出本机
- 跨平台（macOS / Windows / Linux）

## 参考项目

| 项目 | 说明 | 许可证 | 集成方式 |
|------|------|--------|----------|
| [pycorrector](https://github.com/shibing624/pycorrector) | 中文文本纠错引擎，提供 Kenlm/MacBERT/T5/Qwen 多级模型 | Apache 2.0 | 源码直接集成于 `third_party/pycorrector/`，可直接修改 |
| [LanguageTool](https://github.com/languagetool-org/languagetool) | 多语言校对引擎，拥有成熟的文档插件架构 | LGPL 2.1 | 架构参考，源码位于本地 `references/`（未上传） |

## 技术栈

- **校对引擎**: pycorrector（Kenlm 统计模型 + MacBERT 深度学习模型）
- **GUI 框架**: PyQt6
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
