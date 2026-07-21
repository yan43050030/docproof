"""Command-line interface for headless / batch proofreading.

Usage:
    python -m docproof --batch <dir> [--out <dir>] [--mode track|clean|report]
    python -m docproof --check <file> [--out <file>] [--mode ...]

Runs the same engine stack as the GUI without opening a window, so it fits into
scripts and automation.
"""

from __future__ import annotations

import argparse
import os
import sys

from docproof.config import init_config
from docproof.engine.engine_manager import EngineManager
from docproof.engine.user_dict import UserDict

_OPENABLE = (".docx", ".txt", ".md")


def _make_handler(path: str):
    from docproof.document.docx_handler import DocxHandler
    from docproof.document.text_handler import TextHandler
    if path.lower().endswith((".txt", ".md")):
        return TextHandler(path)
    return DocxHandler(path)


def _process_file(path: str, out_path: str, mode: str,
                  engine: EngineManager, user_dict: UserDict) -> int:
    """Proofread one file, write output, return the number of issues found."""
    from docproof import report
    handler = _make_handler(path)
    handler.load()
    errors = engine.proofread(handler.get_full_text())
    errors = user_dict.filter_errors(errors)

    if mode == "report":
        report.save_report(out_path, os.path.basename(path), errors)
        return len(errors)

    if errors:
        is_text = path.lower().endswith((".txt", ".md"))
        if mode == "track" and not is_text:
            handler.apply_corrections(errors, track_changes=True)
        else:  # clean, or text files (no revision format)
            handler.apply_corrections(errors, markup=False)
    handler.save(out_path)
    return len(errors)


def _out_name(src: str, out_dir: str, mode: str) -> str:
    base, ext = os.path.splitext(os.path.basename(src))
    if mode == "report":
        return os.path.join(out_dir, f"{base}-report.html")
    return os.path.join(out_dir, f"{base}-校对{ext}")


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="docproof", description="DocProof 中文文档校对（命令行）")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--batch", metavar="DIR", help="校对文件夹内所有文档")
    group.add_argument("--check", metavar="FILE", help="校对单个文档")
    parser.add_argument("--out", metavar="PATH",
                        help="输出文件或文件夹（默认在原名后加 -校对）")
    parser.add_argument("--mode", choices=["track", "clean", "report"],
                        default="track",
                        help="track=Word修订(默认) clean=直接改 report=只出报告")
    parser.add_argument("--model", help="指定模型 key（默认自动选择）")
    args = parser.parse_args(argv)

    init_config()
    engine = EngineManager()
    if args.model:
        ok, msg = engine.load(args.model)
    else:
        ok, msg = engine.auto_load()
    if not ok:
        print(f"引擎加载失败: {msg}", file=sys.stderr)
        return 2
    print(f"已加载引擎: {msg}")
    user_dict = UserDict()

    if args.check:
        src = args.check
        if not os.path.isfile(src):
            print(f"文件不存在: {src}", file=sys.stderr)
            return 2
        out = args.out or _out_name(src, os.path.dirname(src) or ".", args.mode)
        n = _process_file(src, out, args.mode, engine, user_dict)
        print(f"{os.path.basename(src)}: {n} 处 -> {out}")
        return 0

    # batch
    src_dir = args.batch
    if not os.path.isdir(src_dir):
        print(f"文件夹不存在: {src_dir}", file=sys.stderr)
        return 2
    out_dir = args.out or src_dir
    os.makedirs(out_dir, exist_ok=True)
    files = [f for f in sorted(os.listdir(src_dir))
             if f.lower().endswith(_OPENABLE) and not f.startswith("~$")]
    if not files:
        print("未找到可校对文件 (.docx/.txt/.md)。", file=sys.stderr)
        return 1

    total = 0
    ok_count = 0
    for f in files:
        src = os.path.join(src_dir, f)
        out = _out_name(src, out_dir, args.mode)
        try:
            n = _process_file(src, out, args.mode, engine, user_dict)
            total += n
            ok_count += 1
            print(f"  {f}: {n} 处 -> {os.path.basename(out)}")
        except Exception as e:  # keep going on a bad file
            print(f"  {f}: 失败 ({e})", file=sys.stderr)
    print(f"完成：{ok_count}/{len(files)} 个文件，共 {total} 处问题。输出目录: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
