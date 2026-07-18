# DocProof - 中文文档离线校对工具

一款基于 AI 的中文文档校对桌面软件，支持 Word (.docx) 和 WPS 文档，可完全离线使用。

## 目标

- 拖入文档，自动扫描错别字、语法错误
- 以"修订模式"显示修改建议（类似 Word 修订）
- 支持逐条接受/忽略/加入白名单
- 完全离线运行，数据不出本机
- 跨平台（macOS / Windows / Linux）

## 参考项目

本项目借鉴以下两个优秀开源项目：

| 项目 | 说明 | 许可证 |
|------|------|--------|
| [pycorrector](https://github.com/shibing624/pycorrector) | 中文文本纠错引擎，提供 Kenlm/MacBERT/T5/Qwen 多级模型 | Apache 2.0 |
| [LanguageTool](https://github.com/languagetool-org/languagetool) | 多语言校对引擎，拥有成熟的文档插件架构 | LGPL 2.1 |

参考源码已克隆到 `references/` 目录。

## 技术栈

- **校对引擎**: pycorrector（Kenlm 统计模型 + MacBERT 深度学习模型）
- **GUI 框架**: PyQt6
- **文档处理**: python-docx
- **打包分发**: PyInstaller

## 开发计划

详见 [PLAN.md](PLAN.md)

## 许可证

Apache License 2.0
