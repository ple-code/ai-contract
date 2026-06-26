# AI-Contract 项目说明

## 项目简介

这是一个用 AI 辅助**合同 + 招投标**场景的调研与工具探索项目。当前阶段的核心工作是：把与业务方的调研录音/面谈转写成文字、做说话人分离、产出结构化需求摘要，供后续产品设计参考。

## 目录结构

```
ai-contract/
├── README.md             # 项目说明（本文件）
├── FILES.md              # 逐项文件/目录用途说明
├── .gitignore            # 忽略音频/虚拟环境/缓存等
├── .git/                 # 版本控制（所有文本改动都有历史可查）
├── raw/                  # 原始资料（录音、笔记）
│   ├── *.m4a             # 调研录音（不入 git，太大）
│   └── *.md              # 业务方提供的文字补充
├── analysis/             # Claude 产出（转写 + 摘要，全部平铺）
│   ├── README.md         # 该目录约定（git 兜底）
│   ├── *_说话人分离.{md,txt}
│   ├── *_raw.json
│   └── *_需求摘要.md
├── tmp/                  # 中间产物（已 .gitignore）
└── .venv/                # Python 虚拟环境（FunASR 等，已 .gitignore）
```

> 详细的逐文件说明见 [FILES.md](./FILES.md)。

## 工作流

1. **录音入库**：业务方/你把调研录音（`.m4a`）放进 `raw/`，命名为 `YYYYMMDD-人名-场景.m4a`。
2. **转写 + 说话人分离**：用 FunASR（paraformer-large-vad-punc + fsmn-vad + CAM++）跑出 `*_说话人分离.{md,txt}` + `*_raw.json`，落在 `analysis/`。
3. **摘要**：Claude 基于转写产出 `*_需求摘要.md`。
4. **你直接改**：所有产出文件你想改哪个直接改，**git 兜底**。

## git 安全网

项目已 `git init`。Claude 重新生成任何文件前会先 `git status` 检查：

- 你**没有未提交改动** → 直接覆盖 + 新 commit
- 你**有未提交改动** → 停下来问你"先帮你 commit 当前版本，还是直接覆盖？"
- 万一覆盖了 → `git checkout HEAD~1 -- <file>` 一秒找回

音频文件（`raw/*.m4a`）已 `.gitignore`，不入库。

## 命名规范

### `raw/` 录音
- 格式：`YYYYMMDD-人名-场景.m4a`（日期 + 人名 + 场景描述）
- 示例：`20260626-沈泰-电话.m4a`、`20260626-李颖莹-面聊.m4a`

### `analysis/` 产出（同名前缀对应同一次调研）
- `*_说话人分离.md` / `*_说话人分离.txt` —— 带说话人标签的转写
- `*_raw.json` —— FunASR 原始输出
- `*_需求摘要.md` —— 结构化需求摘要
