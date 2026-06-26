# analysis/ 目录说明

只分两层：**机器产出的转写**（别改）+ **你直接改的摘要**（git 兜底）。

```
analysis/
├── transcripts/       # AI 转写原始数据（机器产出，可重生成，请勿改）
└── summaries/         # 需求摘要（我起草 + 你直接在上面改，git 兜底）
```

## 约定

### `transcripts/`
- 我跑 FunASR 产出的转写（`*_说话人分离.{md,txt}` + `*_raw.json`）。
- **请勿手动改**；要重转直接让我重跑，会覆盖。

### `summaries/`
- 我起草的需求摘要（`*_需求摘要.md`）。
- **你直接在这上面改，不用复制出去**——保留这一份正确可用的就行。
- 安全网是 **git**：
  - 我每次写完会 `git commit`；
  - 你改完建议也 commit（或者交给 Claude Code 帮你 commit）；
  - 我重新生成前会先 `git status` 看一眼，**如果你有未提交的改动，我会先问你**再覆盖；
  - 万一覆盖了，`git diff HEAD~1` / `git checkout HEAD~1 -- <file>` 都能找回。

## 我的规矩（Claude 写摘要时遵守）

1. 写完 → `git add` + `git commit`。
2. 重新生成前 → 先 `git status`；若目标文件有未提交修改，**停下来问你**"要我覆盖吗 / 要我先帮你 commit 当前版本吗"。
3. 永远不主动删 `summaries/` 里你没让删的文件。
