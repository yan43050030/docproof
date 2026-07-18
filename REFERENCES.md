# 参考项目开发指南

开发 DocProof 时需要重点参考的两个项目。本文档记录具体参考什么、在哪里找。

---

## 一、pycorrector — 中文校对引擎

**仓库**: shibing624/pycorrector | **许可证**: Apache 2.0 | **已集成**: `third_party/pycorrector/`

### 参考要点

| 开发任务 | 参考文件 | 参考内容 |
|----------|----------|----------|
| 校对引擎 API 设计 | `pycorrector/corrector.py` | `correct()` 返回格式 `{source, target, errors}` |
| 错误检测管线 | `pycorrector/detector.py` | 混淆集→专名→词错误→字错误 四级检测 |
| 候选词生成 | `pycorrector/corrector.py:169` | `generate_items()` 同音字+形似字候选集 |
| 语言模型评分 | `pycorrector/detector.py:254-270` | `ngram_score()`, `ppl_score()` |
| 自定义混淆集 | `pycorrector/detector.py:180-205` | 用户自定义错词→正词映射 |
| 用户词典扩展 | `pycorrector/detector.py:225-236` | `set_custom_word_freq()` |
| 简繁转换 | `pycorrector/utils/zh_wiki.py` | `traditional2simplified()` |
| 文本切句 | `pycorrector/utils/tokenizer.py` | `split_text_into_sentences_by_symbol()` |
| 同音字数据 | `pycorrector/data/same_pinyin.txt` | 拼音相似字符集 |
| 形似字数据 | `pycorrector/data/same_stroke.txt` | 字形相似字符集 |
| 专用名词库 | `pycorrector/data/proper_name.txt` | 成语、俗语等 |
| Kenlm 使用示例 | `examples/kenlm/demo.py` | 基本调用方式 |
| 自定义混淆集示例 | `examples/kenlm/use_custom_confusion.py` | 用户词典集成 |
| MacBERT 使用示例 | `examples/macbert/demo.py` | 深度学习模型调用 |

---

## 二、LanguageTool — Office 插件架构

**仓库**: languagetool-org/languagetool | **许可证**: LGPL 2.1 | **位置**: 本地 `references/languagetool/`

### 核心架构参考

```
Main.java (XProofreader 入口)
  └── MultiDocumentsHandler (多文档管理)
        └── SingleDocument (单文档校对管线)
              ├── DocumentCursorTools (文档导航：正文/表格/页眉/脚注/形状)
              ├── FlatParagraphTools (文本提取 + 修订回写)
              ├── DocumentCache (段落缓存 + 位置映射)
              ├── SingleCheck (执行 LanguageTool 规则)
              └── SpellAndGrammarCheckDialog (交互式校对 UI)
```

### 文件 → 我们的对应模块

| LanguageTool 文件 | 行数 | DocProof 对应模块 | 参考要点 |
|-------------------|------|-------------------|----------|
| `Main.java` | 275 | `docproof/ui/main_window.py` | 插件入口，`XProofreader.doProofreading()` 接口 |
| `MultiDocumentsHandler.java` | — | `docproof/app.py` | 多文档管理、引擎生命周期 |
| `SingleDocument.java` | 1912 | `docproof/document/docx_handler.py` | **核心管线**：提取→校对→缓存→合并→回写 |
| `DocumentCache.java` | 2628 | `docproof/document/position_mapper.py` | **位置映射**：flatParaIndex ↔ TextParagraph(type+num) |
| `FlatParagraphTools.java` | 1006 | `docproof/document/docx_handler.py` | 文本提取 `getAllFlatParagraphs()` + 替换 `changeTextOfParagraph()` |
| `DocumentCursorTools.java` | 1515 | `docproof/document/docx_handler.py` | 表格/页眉/页脚/脚注/文本框 遍历 |
| `SpellAndGrammarCheckDialog.java` | 3407 | `docproof/ui/correction_view.py` | **修订 UI**：修改/忽略/全部修改/撤销/加入词典 |
| `SingleCheck.java` | — | `docproof/engine/kenlm_engine.py` | 规则执行、结果转换 |
| `IgnoredMatches.java` | — | `docproof/engine/user_dict.py` | 忽略列表、白名单管理 |

### 关键设计模式（直接借鉴）

**1. 二层位置映射**
```
DocumentCache 维护:
  toTextMapping:  flatParagraphIndex → TextParagraph(type, number)
  toParaMapping:  [type][textParagraphIndex] → flatParagraphIndex

这样校对引擎只需知道 flatParagraphIndex，就能通过 toTextMapping
追溯到具体是正文/表格/页脚的第几个段落。
```
**对应到我们**：`PositionMapper` 需要维护 `charPos → (paragraphIndex, runIndex, offsetInRun)` 映射，校对后可按原路径写回。

**2. 多级结果缓存 + 合并**
```
SingleDocument 用 ResultCache[] 按规则类别分别缓存结果，
最后 mergeErrors() 合并、排序、去重、过滤忽略项。
```
**对应到我们**：校对结果按段落缓存，用户滚动查看时直接从缓存读取，避免重复校对。

**3. 分段批量检查**
```
numParasToCheck 控制检查范围：
  0  = 只检查当前段落
  N  = 检查前后 N 段
  -1 = 检查整个文档
```
**对应到我们**：长文档支持"先检查可见区域"模式，后台逐步检查全文。

**4. 交互式校对 UI 状态机**
```
按钮状态: [修改][全部修改][自动更正] | [忽略一次][永久忽略][忽略规则][停用规则]
导航: gotoNextError() → 定位段落 → 高亮错误 → 显示建议列表
撤销: UndoContainer 记录最近 50 步操作
```
**对应到我们**：`correction_view.py` 的按钮布局和操作流程直接参考。

**5. 文本修改的 diff 策略**
```
SpellAndGrammarCheckDialog 不使用简单的 match-and-replace，
而是计算原始文本和用户编辑后文本的 diff，找到真正的变更范围。
```
**对应到我们**：用户可能手动编辑文本而非选择建议，需要支持。

### UNO API 概念 → Python 等效

| LanguageTool (Java/UNO) | DocProof (Python) |
|--------------------------|-------------------|
| `XFlatParagraphIterator` | `python-docx` `Document.paragraphs` 遍历 |
| `XFlatParagraph.getText()` | `paragraph.text` |
| `XFlatParagraph.changeText(start, len, newText)` | `run.text = run.text[:pos] + new + run.text[pos+len:]` |
| `commitStringMarkup(PROOFREADING, ...)` | `run.font.color.rgb` 设置红色 + `run.font.strike` |
| `XTextTable` / `getCellNames()` | `document.tables` → `table.rows` → `cell.paragraphs` |
| `XFootnotesSupplier` | `document.part.element` 中 `w:footnoteReference` 元素 |
| `XPageStyle` → Header/Footer | `document.sections` → `section.header` / `section.footer` |

---

## 三、开发时的使用方式

在每个开发阶段，先查阅本文档找到对应的参考文件，理解成熟方案后再动手写：

1. **写校对引擎集成时** → 看 pycorrector `corrector.py` + `detector.py`
2. **写文档位置映射时** → 看 LanguageTool `DocumentCache.java` + `FlatParagraphTools.java`
3. **写修订模式 UI 时** → 看 LanguageTool `SpellAndGrammarCheckDialog.java`
4. **写文档遍历（表格等）时** → 看 LanguageTool `DocumentCursorTools.java`
