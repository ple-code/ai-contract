# analysis/ 目录说明

本目录存放所有 AI 产出。**按"谁有权写"分成三层**，避免我重新生成时盖掉你改过的内容。

## 目录结构

```
analysis/
├── README.md          # 本文件（约定）
├── transcripts/       # AI 转写原始数据（机器产出）
├── summaries/         # AI 摘要草稿（Claude 起草）
└── notes/             # 你的工作区（你改完的最终版）
```

## 三层写入权限约定

| 目录 | 谁写 | 会被覆盖吗 | 说明 |
|---|---|---|---|
| `transcripts/` | 仅 Claude（跑 FunASR） | ✅ 重新转写会覆盖 | 机器原始输出，**请勿手动编辑**；要重转直接让我重跑 |
| `summaries/` | 仅 Claude（起草） | ✅ 重新生成会覆盖 | Claude 的草稿区，**当作参考**，不要在这里直接改 |
| `notes/` | 仅你（用户） | ❌ Claude 永远不写 | 你的最终版/二次加工区，Claude 只读不写 |

## 工作流

1. Claude 在 `transcripts/` 产出转写 → 在 `summaries/` 起草摘要
2. 你看了草稿觉得 OK → **复制到 `notes/`** 再改
3. 你下次让 Claude 重新生成 → `summaries/` 被覆盖，但 `notes/` 里的版本完好
4. 万一手滑覆盖了什么 → `git diff` / `git log` 找回

## 文件命名

- 转写：`{日期}-{人名}-{场景}_说话人分离.{md,txt}` + `_raw.json`
- 摘要草稿：`{日期}-{人名}-{场景}_需求摘要.md`
- 你的最终版：`notes/` 下同名即可，或加 `_v2` / `_最终` 后缀

## 保险

项目根目录已 `git init`。音频文件 (`raw/*.m4a`) 已 `.gitignore`，不会被提交。所有文本/Markdown/JSON 都进版本库，任何改动都有历史可查。
