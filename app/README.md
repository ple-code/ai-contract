# app/ — 明衡前后端代码

承载「明衡 · 合同审核 AI」的工程实现。

| 看什么 | 去哪 |
|---|---|
| 需求 | `docs/01-需求文档/PRD-v1.md` |
| 架构 / 技术选型 / API 契约 | `docs/02-技术方案/技术方案-v1.md` |
| UI 基准 | `docs/02-技术方案/UI风格参考.md`、`prototype/明衡-合同审阅工作台.html` |
| 部署 | `docs/05-部署/部署手册.md` |

## 目录结构

```
app/
├── web/   # 前端：React 18 + TypeScript + Vite（合同审阅工作台 SPA）
└── api/   # 后端：Python 3.11 + FastAPI（REST + SSE 流式初审）
```

> 后端通过 OpenAI 协议接入 LiteLLM 模型网关（本地 DeepSeek 默认 / 多模型可配），见技术方案「模型策略」一节。

## 约定

- 前后端**各自独立**的依赖管理：`web/package.json`、`api/pyproject.toml`
- API 契约以技术方案文档为准；接口变更**同步更新文档**
- 密钥 / `.env` / 大文件不入库（见根 `.gitignore`）
- 改前查 `git status`，遵循项目「git 兜底」约定
