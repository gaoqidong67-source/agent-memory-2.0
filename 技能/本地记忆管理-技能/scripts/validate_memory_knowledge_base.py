#!/usr/bin/env python3
"""Read-only validation for an Agent Memory 2.0 knowledge base."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote


REQUIRED_FILES = {
    "README.md",
    "AGENTS.md",
    ".gitignore",
    ".gitattributes",
    "Inbox/README.md",
    "Inbox/临时文件/README.md",
    "重要记忆/README.md",
    "重要记忆/00_AI阅读入口.md",
    "重要记忆/01_用户核心画像.md",
    "重要记忆/02_经验教训和知识点索引.md",
    "重要记忆/03_工具链总览.md",
    "重要记忆/04_角色工作模式.md",
    "重要记忆/05_判断力.md",
    "日常记忆/README.md",
    "日常记忆/笔记框架.md",
    "project/README.md",
    "project/任务路由.md",
    "project/项目模板.md",
    "project/变更记录.md",
    "project/已完结项目/README.md",
    "工具/README.md",
    "工具/任务路由.md",
    "技能/README.md",
    "技能/任务路由.md",
    "技能/本地记忆管理-技能/SKILL.md",
    "技能/本地记忆管理-技能/references/memory-schema.md",
    "技能/本地记忆管理-技能/references/templates.md",
    "技能/本地记忆管理-技能/references/validation.md",
    "技能/本地记忆管理-技能/scripts/validate_memory_knowledge_base.py",
    "提示词/README.md",
    "提示词/任务路由.md",
    "经验教训/README.md",
    "经验教训/任务路由.md",
    "经验教训/变更记录.md",
    "知识点/README.md",
    "知识点/任务路由.md",
    "判断力/README.md",
    "判断力/任务路由.md",
}

REQUIRED_DIRS = {
    "Inbox/未处理文件/日常记忆",
    "Inbox/未处理文件/知识点",
    "Inbox/未处理文件/提示词",
    "Inbox/未处理文件/工具",
    "Inbox/未处理文件/技能",
    "Inbox/未处理文件/其他待判断",
    "Inbox/已处理文件",
    "Inbox/已入库文件",
    "Inbox/临时文件",
    "project/已完结项目",
}

PORTABLE_OPTIONAL_FILES = {
    "Inbox/临时文件/README.md",
}

PORTABLE_OPTIONAL_DIRS = set(REQUIRED_DIRS)
PORTABLE_OPTIONAL_LINK_ROOTS = {"董事会"}

ALLOWED_ROOT_FILES = {"README.md", "AGENTS.md", ".gitignore", ".gitattributes"}
ALLOWED_ROOT_DIRS = {
    ".github",
    "Inbox",
    "重要记忆",
    "日常记忆",
    "project",
    "工具",
    "技能",
    "提示词",
    "经验教训",
    "知识点",
    "判断力",
}

PRUNED_DIR_NAMES = {
    ".agents",
    ".codex",
    ".git",
    ".obsidian",
    ".playwright-cli",
    ".uploads",
    ".npm-cache-update-check",
    ".venv",
    "node_modules",
    "site-packages",
    "vendor",
    "third_party",
    "third-party",
    "原包",
    "npm-package",
    "packages",
    "runtimes",
    "models",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "archives",
    "output",
    "outputs",
    "已入库文件",
    "临时文件",
    "董事会",
}

SENSITIVE_FILE_NAMES = {
    "账号密码.md",
    "agent memory只读授权提示词.md",
}

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
WINDOWS_ABSOLUTE_RE = re.compile(r"(?i)(?:^|[\s'\"])[a-z]:\\(?:users|agent memory|workspace)\\")
OLD_WORKSPACE_RE = re.compile(r"(?i)(?:^|[\s'\"])" + "/" + "workspace/")
FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):", re.MULTILINE)


def configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def normalize_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def should_prune(path: Path, root: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    lowered = {part.lower() for part in relative_parts}
    if lowered.intersection({name.lower() for name in PRUNED_DIR_NAMES}):
        return True
    return any(
        part.lower().startswith(("opencli-", "douyin-home-profile"))
        or part.lower() == "user data"
        for part in relative_parts
    )


def iter_files_pruned(root: Path, errors: list[str], skipped: set[str]):
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError as exc:
            errors.append(f"无法读取目录 {normalize_relative(current, root) or '.'}: {exc}")
            continue
        for entry in entries:
            path = Path(entry.path)
            if entry.is_dir(follow_symlinks=False):
                if should_prune(path, root):
                    skipped.add(normalize_relative(path, root))
                    continue
                stack.append(path)
            elif entry.is_file(follow_symlinks=False):
                if path.name.lower() in SENSITIVE_FILE_NAMES:
                    skipped.add(normalize_relative(path, root))
                    continue
                yield path


def read_utf8(path: Path, root: Path, errors: list[str]) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"UTF-8 读取失败 {normalize_relative(path, root)}: {exc}")
        return None
    if "\ufffd" in text:
        errors.append(f"包含 Unicode 替换字符: {normalize_relative(path, root)}")
    return text


def check_markdown_table(relative: str, text: str, errors: list[str]) -> None:
    expected: int | None = None
    in_fence = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            expected = None
            continue
        is_row = not in_fence and stripped.startswith("|") and stripped.endswith("|")
        if not is_row:
            expected = None
            continue
        columns = len(stripped.split("|")) - 2
        if expected is None:
            expected = columns
        elif columns != expected:
            errors.append(
                f"Markdown 表格列数不一致 {relative}:{line_number} "
                f"(expected {expected}, got {columns})"
            )


def check_markdown_links(
    path: Path,
    root: Path,
    text: str,
    errors: list[str],
    *,
    portable: bool = False,
) -> None:
    without_fences = FENCE_RE.sub("", text)
    for raw_target in MARKDOWN_LINK_RE.findall(without_fences):
        target = raw_target.strip().strip("<>")
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        target = unquote(target.split("#", 1)[0])
        if not target or any(token in target for token in ("{{", "}}", "待填写")):
            continue
        resolved = (path.parent / target).resolve()
        try:
            relative_target = resolved.relative_to(root)
        except ValueError:
            errors.append(
                f"相对链接越出库根 {normalize_relative(path, root)} -> {raw_target}"
            )
            continue
        if (
            portable
            and relative_target.parts
            and relative_target.parts[0] in PORTABLE_OPTIONAL_LINK_ROOTS
        ):
            continue
        if not resolved.exists():
            errors.append(f"断链 {normalize_relative(path, root)} -> {raw_target}")


def check_skill_frontmatter(path: Path, root: Path, text: str, errors: list[str]) -> None:
    if not text.startswith("---\n"):
        errors.append(f"Skill 缺少 frontmatter: {normalize_relative(path, root)}")
        return
    closing = text.find("\n---\n", 4)
    if closing < 0:
        errors.append(f"Skill frontmatter 未闭合: {normalize_relative(path, root)}")
        return
    keys = FRONTMATTER_KEY_RE.findall(text[4:closing])
    if keys != ["name", "description"]:
        errors.append(
            f"Skill frontmatter 字段应仅为 name/description: "
            f"{normalize_relative(path, root)} ({keys})"
        )


def check_project_readmes(root: Path, errors: list[str]) -> None:
    project_root = root / "project"
    if not project_root.is_dir():
        return
    required_fields = ("当前状态", "最后更新", "关键产物", "下一步", "事实来源")
    for child in project_root.iterdir():
        if not child.is_dir() or child.name == "已完结项目":
            continue
        if should_prune(child, root):
            continue
        readme = child / "README.md"
        if not readme.is_file():
            errors.append(f"活跃项目缺少 README.md: project/{child.name}")
            continue
        try:
            text = readme.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"项目 README 读取失败 project/{child.name}/README.md: {exc}")
            continue
        for field in required_fields:
            if f"- {field}：" not in text:
                errors.append(f"项目状态块缺少“{field}”: project/{child.name}/README.md")


def validate_memory_root(
    root: Path,
    *,
    strict: bool = False,
    portable: bool = False,
) -> dict[str, object]:
    root = root.expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    skipped: set[str] = set()
    scanned_files = 0
    markdown_files = 0

    if not root.is_dir():
        return {
            "ok": False,
            "root": str(root),
            "strict": strict,
            "portable": portable,
            "errors": [f"目标目录不存在: {root}"],
            "warnings": [],
            "counts": {"files": 0, "markdown": 0},
            "skipped_roots": [],
        }

    required_files = REQUIRED_FILES - PORTABLE_OPTIONAL_FILES if portable else REQUIRED_FILES
    required_dirs = REQUIRED_DIRS - PORTABLE_OPTIONAL_DIRS if portable else REQUIRED_DIRS
    for relative in sorted(required_files):
        if not (root / relative).is_file():
            errors.append(f"缺少必需文件: {relative}")
    for relative in sorted(required_dirs):
        if not (root / relative).is_dir():
            errors.append(f"缺少必需目录: {relative}")

    from datetime import date

    today = date.today()
    current_quarter = f"{today.year}-{((today.month - 1) // 3) + 1}.0"
    if not portable and not (root / "日常记忆" / current_quarter).is_dir():
        errors.append(f"缺少当前季度目录: 日常记忆/{current_quarter}")

    for item in root.iterdir():
        if item.is_file() and item.name not in ALLOWED_ROOT_FILES:
            warnings.append(f"根目录存在未登记文件: {item.name}")
        elif item.is_dir() and item.name not in ALLOWED_ROOT_DIRS and item.name not in PRUNED_DIR_NAMES:
            warnings.append(f"根目录存在未登记目录: {item.name}")

    first_party_script_suffixes = {".py", ".ps1", ".cmd", ".bat"}
    for path in iter_files_pruned(root, errors, skipped):
        scanned_files += 1
        suffix = path.suffix.lower()
        if suffix not in {".md", ".py", ".ps1", ".cmd", ".bat", ".json", ".yaml", ".yml"}:
            continue
        text = read_utf8(path, root, errors)
        if text is None:
            continue
        relative = normalize_relative(path, root)
        if suffix == ".md":
            markdown_files += 1
            check_markdown_table(relative, text, errors)
            check_markdown_links(path, root, text, errors, portable=portable)
            if path.name == "SKILL.md":
                check_skill_frontmatter(path, root, text, errors)
        if suffix in first_party_script_suffixes:
            if WINDOWS_ABSOLUTE_RE.search(text) or OLD_WORKSPACE_RE.search(text):
                errors.append(f"第一方脚本包含固定工作区路径: {relative}")

    project_index = root / "project" / "README.md"
    if project_index.is_file():
        text = read_utf8(project_index, root, errors)
        if text is not None:
            if "显式“最后更新”" not in text:
                errors.append("project/README.md 未声明按显式“最后更新”排序")
            if "活跃项目按目录最近修改时间倒序" in text:
                errors.append("project/README.md 仍包含旧 mtime 排序规则")

    agents = root / "AGENTS.md"
    if agents.is_file():
        text = read_utf8(agents, root, errors)
        if text is not None and "枚举前" not in text:
            errors.append("AGENTS.md 缺少枚举前剪枝门禁")

    check_project_readmes(root, errors)

    ok = not errors and (not strict or not warnings)
    return {
        "ok": ok,
        "root": str(root),
        "strict": strict,
        "portable": portable,
        "errors": errors,
        "warnings": warnings,
        "counts": {"files": scanned_files, "markdown": markdown_files},
        "skipped_roots": sorted(skipped),
    }


def parse_args() -> argparse.Namespace:
    inferred_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Validate an Agent Memory 2.0 knowledge base.")
    parser.add_argument("--root", default=str(inferred_root), help="Agent Memory root.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failure.")
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Validate the Git-portable snapshot without local-only directories.",
    )
    return parser.parse_args()


def main() -> int:
    configure_utf8_output()
    args = parse_args()
    result = validate_memory_root(
        Path(args.root),
        strict=args.strict,
        portable=args.portable,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
