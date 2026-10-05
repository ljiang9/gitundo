#!/usr/bin/env python3
"""gitundo - 安全地撤销常见的 git 误操作。

git 本身没有后悔药；gitundo 是这些"希望 git 有"命令的薄安全封装：
每次都先展示会发生什么，危险操作需要 --yes 或交互确认。
它不是魔法：只是把 git reset / restore 等命令包了一层护栏。

用法：
    gitundo uncommit              # 撤销最近一次提交，改动保留在暂存区
    gitundo unstage [文件]        # 取消暂存（全部或单个文件）
    gitundo discard [文件]        # 丢弃工作区改动（危险，需确认）
    gitundo unpush                 # 撤销已推送的提交（重写公共历史，极危险）
    任意子命令加 --dry-run 只打印将要执行的 git 命令，不执行。
"""

import argparse
import subprocess
import sys

VERSION = "0.1.0"


def run_git(args, capture=True):
    """运行 git 命令。返回 (returncode, stdout, stderr)。"""
    p = subprocess.run(
        ["git"] + args,
        capture_output=capture,
        text=True,
    )
    return p.returncode, p.stdout, p.stderr


def die(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def ensure_repo():
    code, _, _ = run_git(["rev-parse", "--git-dir"])
    if code != 0:
        die("当前目录不是 git 仓库（git rev-parse 失败）。", code=1)


def confirm_interactive(prompt):
    """非交互终端直接返回 False；交互终端问 y/N。"""
    if not sys.stdin.isatty():
        return False
    ans = input(f"{prompt} [y/N] ").strip().lower()
    return ans in ("y", "yes")


def show_what(cmd_args, description):
    print(f"将要执行：git {' '.join(cmd_args)}")
    print(f"说明：{description}")


def maybe_run(cmd_args, description, yes, dry_run):
    show_what(cmd_args, description)
    if dry_run:
        print("（dry-run：未执行）")
        return 0
    if yes or confirm_interactive("确认执行？"):
        code, out, err = run_git(cmd_args)
        if out:
            print(out, end="")
        if code != 0:
            die(err.strip() or f"git 返回退出码 {code}", code=code)
        print("完成。")
        return 0
    print("已取消，未做任何改动。")
    return 2


def head_summary():
    code, out, _ = run_git(["log", "-1", "--format=%h %s"])
    return out.strip() if code == 0 and out.strip() else "(无法读取)"


def cmd_uncommit(args):
    """撤销最近一次提交，改动保留在暂存区。"""
    ensure_repo()
    code, out, _ = run_git(["rev-parse", "--verify", "HEAD"])
    if code != 0:
        die("仓库还没有任何提交，无可撤销。")
    print(f"最近一次提交：{head_summary()}")
    # 只有一个提交时 HEAD~1 不存在：用 update-ref -d HEAD 删除分支引用，
    # 暂存区原样保留，效果等同于"撤销这次提交"。
    code, _, _ = run_git(["rev-parse", "--verify", "HEAD~1"])
    if code == 0:
        reset_args = ["reset", "--soft", "HEAD~1"]
        desc = "撤销这次提交；文件改动保留在暂存区（相当于回到 commit 之前、add 之后的状态）。"
    else:
        reset_args = ["update-ref", "-d", "HEAD"]
        desc = "撤销初始提交；文件改动保留在暂存区，分支回到无提交状态。"
    return maybe_run(reset_args, desc, args.yes, args.dry_run)


def cmd_unstage(args):
    """取消暂存全部或单个文件。"""
    ensure_repo()
    target = [args.file] if args.file else []
    code, out, _ = run_git(["diff", "--cached", "--name-only"] + target)
    staged = [l for l in out.splitlines() if l.strip()]
    if not staged:
        label = f"文件 {args.file}" if args.file else "暂存区"
        print(f"{label}没有已暂存的改动，无需操作。")
        return 0
    print("将取消暂存以下文件：")
    for f in staged:
        print(f"  {f}")
    return maybe_run(
        ["restore", "--staged"] + (target or ["."]),
        "把改动从暂存区拿回工作区；文件内容不受影响。",
        args.yes,
        args.dry_run,
    )


def cmd_discard(args):
    """丢弃工作区改动（危险）。"""
    ensure_repo()
    if args.file:
        code, out, _ = run_git(["ls-files", "--error-unmatch", args.file])
        if code != 0:
            die(f"文件 {args.file} 未被 git 跟踪（untracked 文件不允许 discard，请手动删除）。")
        pathspec = [args.file]
    else:
        pathspec = []
    code, out, _ = run_git(["diff", "--stat", "--"] + pathspec)
    if not out.strip():
        print("工作区没有可丢弃的改动，无需操作。")
        return 0
    print("⚠️  以下改动将被永久丢弃（无法恢复）：")
    print(out, end="")
    return maybe_run(
        ["restore", "--"] + (pathspec or ["."]),
        "用 HEAD 的版本覆盖工作区文件；未提交的改动会丢失。",
        args.yes,
        args.dry_run,
    )


def cmd_unpush(args):
    """撤销已推送的提交（重写公共历史，极危险）。"""
    ensure_repo()
    code, out, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    branch = out.strip() if code == 0 else ""
    if not branch or branch == "HEAD":
        die("无法确定当前分支（detached HEAD），拒绝操作。")
    code, _, _ = run_git(["rev-parse", "--verify", "@{u}"])
    if code != 0:
        die(f"分支 {branch} 没有上游分支；用 uncommit 即可，无需 unpush。")
    code, out, _ = run_git(["rev-list", "--count", "@{u}..HEAD"])
    ahead = out.strip() if code == 0 else "?"
    print("⚠️  危险操作：这将重写已推送到远端的公共历史。")
    print(f"分支：{branch}（领先上游 {ahead} 个提交）")
    print(f"将被撤销的提交：{head_summary()}")
    print("其他已拉取该分支的人下次 pull 会冲突；只有在你确定没人基于它工作时才继续。")
    if args.dry_run:
        print(f"将要执行：git reset --soft HEAD~1 && git push --force-with-lease origin {branch}")
        print("（dry-run：未执行）")
        return 0
    if sys.stdin.isatty() and not args.yes:
        typed = input(f"请输入分支名 [{branch}] 以确认：").strip()
        if typed != branch:
            print("输入不匹配，已取消，未做任何改动。")
            return 2
    elif not args.yes:
        die("非交互终端下 unpush 必须加 --yes（你得想清楚）。", code=2)
    code, out, err = run_git(["reset", "--soft", "HEAD~1"])
    if code != 0:
        die(err.strip() or "git reset 失败", code=code)
    code, out, err = run_git(["push", "--force-with-lease", "origin", branch])
    if code != 0:
        die(f"git push 失败（本地提交已撤销，远端未动）：{err.strip()}", code=code)
    print("完成：本地提交已撤销并强制更新了远端。")
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="gitundo",
        description="安全地撤销常见的 git 误操作（先展示、再确认、后执行）。",
    )
    p.add_argument("--version", action="version", version=f"gitundo {VERSION}")
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp):
        sp.add_argument("--yes", action="store_true", help="跳过交互确认（危险操作请三思）")
        sp.add_argument("--dry-run", action="store_true", help="只打印将要执行的 git 命令，不执行")

    s = sub.add_parser("uncommit", help="撤销最近一次提交，改动保留在暂存区")
    add_common(s)
    s.set_defaults(func=cmd_uncommit)

    s = sub.add_parser("unstage", help="取消暂存（全部或单个文件）")
    s.add_argument("file", nargs="?", help="只取消暂存该文件（缺省为全部）")
    add_common(s)
    s.set_defaults(func=cmd_unstage)

    s = sub.add_parser("discard", help="丢弃工作区改动（危险，需确认）")
    s.add_argument("file", nargs="?", help="只丢弃该文件的改动（缺省为全部已跟踪文件）")
    add_common(s)
    s.set_defaults(func=cmd_discard)

    s = sub.add_parser("unpush", help="撤销已推送的提交（重写公共历史，极危险）")
    add_common(s)
    s.set_defaults(func=cmd_unpush)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
