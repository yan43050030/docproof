"""Generate a proofreading report (HTML or plain text) from a list of errors."""

from __future__ import annotations

import datetime
import html
import os
from collections import Counter

from docproof.engine.base_engine import CATEGORY_LABELS


def _category_counts(errors: list) -> Counter:
    c: Counter = Counter()
    for e in errors:
        c[getattr(e, "category", "spelling")] += 1
    return c


def build_text_report(source_name: str, errors: list) -> str:
    """Build a plain-text proofreading report."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "DocProof 校对报告",
        "=" * 32,
        f"文档: {source_name}",
        f"生成时间: {now}",
        f"疑似问题总数: {len(errors)}",
    ]
    counts = _category_counts(errors)
    if counts:
        summary = "、".join(
            f"{CATEGORY_LABELS.get(k, k)} {v}" for k, v in counts.items()
        )
        lines.append(f"分类统计: {summary}")
    lines.append("")
    lines.append("序号  类型      原文 → 建议")
    lines.append("-" * 32)
    for i, e in enumerate(errors, 1):
        label = CATEGORY_LABELS.get(getattr(e, "category", "spelling"), "错别字")
        correct = e.correct if e.correct != "" else "（删除）"
        lines.append(f"{i:>3}   {label:<6}  {e.error} → {correct}")
    if not errors:
        lines.append("未发现问题，文档很干净。")
    return "\n".join(lines) + "\n"


def build_html_report(source_name: str, errors: list) -> str:
    """Build a standalone HTML proofreading report."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    counts = _category_counts(errors)
    chips = "".join(
        f'<span class="chip">{html.escape(CATEGORY_LABELS.get(k, k))}: {v}</span>'
        for k, v in counts.items()
    )
    rows = []
    for i, e in enumerate(errors, 1):
        label = CATEGORY_LABELS.get(getattr(e, "category", "spelling"), "错别字")
        correct = html.escape(e.correct) if e.correct != "" else "<i>（删除）</i>"
        rows.append(
            f"<tr><td>{i}</td><td>{html.escape(label)}</td>"
            f'<td class="err">{html.escape(e.error)}</td>'
            f'<td class="fix">{correct}</td></tr>'
        )
    body_rows = "".join(rows) or (
        '<tr><td colspan="4" style="text-align:center;color:#16A34A;">'
        "未发现问题，文档很干净 ✓</td></tr>"
    )
    return f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<title>DocProof 校对报告 - {html.escape(source_name)}</title>
<style>
  body {{ font-family: "PingFang SC","Microsoft YaHei",sans-serif; margin: 32px;
         color: #1a1a1a; }}
  h1 {{ font-size: 20px; }}
  .meta {{ color: #666; margin-bottom: 12px; }}
  .chip {{ display:inline-block; background:#EFF6FF; color:#2563EB;
           border-radius: 12px; padding: 2px 10px; margin-right: 8px;
           font-size: 13px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
  th, td {{ border: 1px solid #E5E7EB; padding: 6px 10px; text-align: left;
            font-size: 14px; }}
  th {{ background: #F8F9FA; }}
  .err {{ color: #DC2626; text-decoration: line-through; }}
  .fix {{ color: #2563EB; font-weight: bold; }}
</style></head><body>
<h1>DocProof 校对报告</h1>
<div class="meta">文档：{html.escape(source_name)}<br>生成时间：{now}<br>
疑似问题总数：{len(errors)}</div>
<div>{chips}</div>
<table><thead><tr><th>#</th><th>类型</th><th>原文</th><th>建议</th></tr></thead>
<tbody>{body_rows}</tbody></table>
</body></html>
"""


def save_report(path: str, source_name: str, errors: list) -> None:
    """Write a report to ``path``; format is chosen by extension (.html/.txt)."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".html", ".htm"):
        content = build_html_report(source_name, errors)
    else:
        content = build_text_report(source_name, errors)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
