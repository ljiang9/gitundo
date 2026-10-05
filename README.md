# gitundo

你希望 git 拥有的那些"后悔"命令。纯标准库，零依赖。

`git reset`、`git restore` 的参数没人记得住，敲错一次就可能丢工作。
gitundo 把四个最常见的撤销场景包成带护栏的命令：**先展示会发生什么，
再要你确认，最后才执行**。

```bash
python3 -m gitundo uncommit          # 撤销最近一次提交，改动保留在暂存区
python3 -m gitundo unstage main.py   # 取消暂存某个文件
python3 -m gitundo discard           # 丢弃工作区全部改动（危险，需确认）
python3 -m gitundo unpush            # 撤销已推送的提交（极危险，要手输分支名）
python3 -m gitundo uncommit --dry-run  # 只看看会执行什么，不真跑
```

## 命令

| 命令 | 效果 | 危险度 |
|---|---|---|
| `uncommit` | `git reset --soft HEAD~1`（初始提交则删分支引用）：提交没了，改动还在暂存区 | 低 |
| `unstage [文件]` | 把文件拿出暂存区，内容不动 | 低 |
| `discard [文件]` | 用 HEAD 覆盖工作区，**未提交改动永久丢失** | 高 |
| `unpush` | 撤销已推送的提交并 `--force-with-lease` 推远端 | 极高 |

## 安全设计

- 每个命令执行前都打印**将要运行的完整 git 命令**和中文说明。
- `discard` / `unpush` 这类破坏性操作：交互终端下要求显式确认；
  非交互终端（管道/脚本）下**不带 `--yes` 直接拒绝**，不会悄悄执行。
- `discard` 先 `git diff --stat` 给你看要丢什么；untracked 文件拒绝 discard
  （误删了找不回来，请手动删除）。
- `unpush` 要求**手输当前分支名**才能继续，防止在错误的分支上重写历史；
  且用 `--force-with-lease` 而不是 `--force`，远端有别人新推的提交时会失败而不是覆盖。
- `--dry-run` 适用于所有子命令：只打印，不执行。

## 诚实说明

gitundo 不是魔法，只是一层薄薄的安全封装：它最终执行的仍然是
`git reset` / `git restore` / `git push` 这些原生命令，护栏也只防"手滑"，
防不住"你真的想错了"。`discard` 丢掉的东西 git 也找不回来，
重要工作请先 commit 或 stash。

## 局限

- 只处理最常见的四个场景；`revert` 合并提交、`reflog` 抢救等不在范围内。
- `unpush` 只处理"领先上游 1 个提交"的简单情况，更复杂的历史请手动处理。
- 需要 git 在 PATH 中且当前目录是 git 仓库。

## License

MIT
