# MOM 系统 AI 知识库平台

> Skill 路由 + 自实现轻量 RAG 架构的制造企业知识库平台

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3-42b883.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)

基于 FastAPI + Vue3 + ChromaDB 构建，平台模型无关（统一接口抽象层），支持 LLM 智能问答、语义/关键词搜索、Skill 路由分发、Token 统计优化等完整功能。

---

## 目录

- [核心特性](#核心特性)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [核心流程](#核心流程)
- [功能模块](#功能模块)
- [API 接口](#api-接口)
- [测试](#测试)
- [预制数据](#预制数据)
- [数据源扩展](#数据源扩展)
- [常见问题](#常见问题)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

---

## 核心特性

- **Skill 路由引擎**：根据用户问题关键词/正则/语义三级匹配对应 Skill，使用专属 Prompt 模板和知识范围
- **自实现轻量 RAG**：不依赖 LangChain/LlamaIndex，直接使用 ChromaDB SDK + httpx 调用模型 API，减少约 25% 开发成本
- **模型无关架构**：统一 `LLMClient` 抽象层，支持任意 OpenAI 兼容模型（MiMo / 通义千问 / OpenAI / Ollama 等）
- **优雅降级**：仅有 LLM 时 RAG 自动降级为直接对话；语义搜索失败时自动切换为关键词搜索
- **运行时热更新**：模型配置存储于数据库，通过 Web 界面修改后立即生效，无需重启服务
- **Token 优化**：问答缓存 + 缓存命中率统计 + Skill 路由限定检索范围
- **全量调用日志**：记录所有模型调用（chat / embedding / test），含发起人、延迟、token 消耗
- **完整测试覆盖**：前端 51 用例 + 后端 21 接口测试 + 构建验证全部通过
- **文件上传解析**：支持 PDF / DOCX / XLSX / Markdown 自动解析分块入库
- **向量维度自适应**：切换不同维度 Embedding 模型时自动重建 ChromaDB collection

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI 0.115 | 异步 API，自动生成 Swagger 文档 |
| 数据库 | SQLAlchemy + SQLite | 关系型数据（MVP） |
| 向量数据库 | ChromaDB 0.5 | 嵌入式，无需独立服务 |
| 前端框架 | Vue 3 + TypeScript | Composition API |
| UI 组件 | Ant Design Vue 4.x | 企业级中后台 |
| 状态管理 | Pinia | 轻量响应式 |
| 构建工具 | Vite 5 | 极速 HMR |
| 图表 | ECharts | 仪表盘 + Token 趋势 |
| 测试 | Vitest + @vue/test-utils | 前端 UI 自动化测试 |
| HTTP 客户端 | httpx | 异步调用 LLM API |
| 加密 | cryptography | 加密存储 API Key |

## 项目结构

```
LLM Wiki/
├── backend/                         # 后端服务
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── config.py                # 配置管理
│   │   ├── database.py              # 数据库初始化与自动迁移
│   │   ├── models/                  # 9 个数据模型
│   │   │   ├── knowledge.py
│   │   │   ├── category.py
│   │   │   ├── tag.py
│   │   │   ├── document.py
│   │   │   ├── skill.py
│   │   │   ├── skill_option.py
│   │   │   ├── model_config.py
│   │   │   ├── qa_history.py
│   │   │   ├── token_usage.py
│   │   │   └── search_history.py
│   │   ├── routers/                 # 10 个 API 路由模块
│   │   │   ├── knowledge.py         # 知识 CRUD + 重建索引
│   │   │   ├── category.py          # 分类树
│   │   │   ├── tag.py
│   │   │   ├── skill.py             # Skill CRUD + 测试路由
│   │   │   ├── skill_option.py      # 分类/功能自定义选项
│   │   │   ├── model_config.py      # 模型配置 + 状态 + 测试
│   │   │   ├── search.py            # 语义+关键词搜索
│   │   │   ├── qa.py                # SSE 流式问答
│   │   │   ├── dashboard.py         # 仪表盘
│   │   │   └── token_stats.py       # Token 统计 + 调用日志
│   │   ├── schemas/                 # Pydantic 验证模型
│   │   ├── services/                # 15 个业务服务
│   │   │   ├── llm_client.py        # LLM 客户端抽象层
│   │   │   ├── embedding_service.py # Embedding 服务（含日志）
│   │   │   ├── rag_service.py       # RAG 检索增强生成
│   │   │   ├── qa_service.py       # 问答服务（含缓存）
│   │   │   ├── cache_service.py    # 问答缓存（向量相似度）
│   │   │   ├── skill_router.py     # Skill 路由引擎
│   │   │   ├── skill_service.py
│   │   │   ├── vector_store.py     # ChromaDB 封装（维度自适应）
│   │   │   ├── knowledge_service.py
│   │   │   ├── model_service.py
│   │   │   ├── search_service.py
│   │   │   ├── prompt_assembler.py
│   │   │   ├── text_chunker.py
│   │   │   ├── file_parser.py      # PDF/DOCX/XLSX/MD 解析
│   │   │   ├── data_adapter.py     # 数据源扩展接口
│   │   │   └── seed_service.py     # 预制数据初始化
│   │   └── utils/
│   │       ├── crypto.py            # API Key 加密/脱敏
│   │       └── response.py          # 统一响应格式
│   ├── data/                        # 数据目录（不提交，gitignore）
│   │   ├── knowledge.db             # SQLite 数据库
│   │   ├── vectors/                 # ChromaDB 持久化
│   │   └── uploads/                 # 上传文件
│   ├── run.py                       # 启动脚本
│   ├── requirements.txt
│   ├── api_test.py                  # 后端 API 测试脚本
│   └── .env.example
├── frontend/                        # 前端应用
│   ├── src/
│   │   ├── views/                   # 13 个页面
│   │   │   ├── Dashboard.vue
│   │   │   ├── ModelConfig.vue
│   │   │   ├── QA.vue               # SSE 流式问答
│   │   │   ├── QAHistory.vue
│   │   │   ├── Search.vue
│   │   │   ├── CallLogs.vue         # 模型调用日志
│   │   │   ├── TokenStats.vue
│   │   │   ├── knowledge/{List,Detail,Edit,Upload}.vue
│   │   │   └── skill/{List,Edit}.vue
│   │   ├── components/              # 5 个通用组件
│   │   ├── api/                     # 9 个 API 模块
│   │   ├── stores/                  # Pinia 状态
│   │   ├── layouts/                 # 主布局
│   │   ├── router/
│   │   └── types/
│   ├── tests/                      # 10 个测试文件，51 个用例
│   ├── package.json
│   └── vite.config.ts
├── README.md
├── LICENSE
└── .gitignore
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- npm 9+

### 后端启动

```bash
cd backend

# 创建虚拟环境（推荐）
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows PowerShell
# source venv/bin/activate    # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（可选，使用默认值即可启动）
copy .env.example .env

# 启动后端
python run.py
```

后端默认运行在 http://localhost:8000
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端默认运行在 http://localhost:5173，已配置 `/api` 代理到后端 8000 端口。

### 生产构建

```bash
cd frontend
npm run build   # 输出到 frontend/dist
```

## 配置说明

### 模型配置

模型配置通过 Web 界面管理（[模型配置页](http://localhost:5173/models)），存储在数据库中，支持运行时热更新。

| 模型类型 | 必需 | 说明 |
|---------|------|------|
| LLM | 必需 | 大语言模型，用于智能问答生成答案 |
| Embedding | 可选 | 向量化模型，用于语义搜索和 RAG 检索；未配置时 RAG 降级为直接对话 |

**支持的 LLM 提供商**（OpenAI 兼容格式）：
- MiMo（小米）：`https://api.xiaomimimo.com/v1`
- 通义千问：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- OpenAI：`https://api.openai.com/v1`
- DeepSeek：`https://api.siliconflow.cn/v1`
- 本地部署：`http://localhost:11434/v1`（Ollama）等

**支持的 Embedding 提供商**（OpenAI 兼容格式，通过模型配置页添加）：
- SiliconFlow：`https://api.siliconflow.cn/v1`（如 BAAI/bge-m3）
- 通义千问、OpenAI 等兼容服务商

> API URL 填写 base URL 即可（如 `https://api.siliconflow.cn/v1`），系统会自动拼接 `/embeddings` 或 `/chat/completions` 后缀；若误填带后缀也会自动剥离。

### 环境变量

后端配置通过 `.env` 文件或环境变量设置，参考 `.env.example`：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| DATABASE_URL | sqlite:///data/knowledge.db | SQLite 数据库路径 |
| VECTOR_DB_PATH | data/vectors | ChromaDB 持久化目录 |
| UPLOAD_PATH | data/uploads | 文件上传目录 |
| HOST | 0.0.0.0 | 服务监听地址 |
| PORT | 8000 | 服务端口 |
| DEBUG | true | 调试模式（自动重载） |
| CACHE_SIMILARITY_THRESHOLD | 0.90 | 问答缓存命中阈值 |
| SECRET_KEY | dev-secret-key-change-in-production | API Key 加密密钥（生产环境务必修改） |

## 核心流程

### 智能问答流程

```
用户提问
  │
  ▼
[Skill 路由引擎] 关键词/正则/语义匹配 → 命中 Skill
  │
  ▼
[Embedding 向量化] 将问题转为向量
  │
  ▼
[ChromaDB 检索] 在 Skill 知识范围内找 Top-5 相关片段
  │
  ▼
[Prompt 组装] Skill 模板 + 检索片段 + 用户问题
  │
  ▼
[LLM 流式生成] SSE 逐步返回答案
  │
  ▼
[Token 记录] 保存输入/输出 token 消耗
```

**降级策略**：
- 无 Embedding 模型：跳过检索，直接 LLM 对话
- 无匹配 Skill：使用默认 Skill 在全量知识库检索
- 语义搜索失败：前端自动切换为关键词搜索
- 向量维度不匹配：自动重建 ChromaDB collection

### Skill 路由三级匹配

1. **关键词/正则匹配**：命中数最多的 Skill 优先
2. **语义匹配**：问题向量与 Skill description 向量余弦相似度 > 0.7
3. **默认兜底**：使用 `is_default=true` 的 Skill，或第一个 Skill

## 功能模块

| 模块 | 路径 | 说明 |
|------|------|------|
| 首页仪表盘 | /dashboard | 统计卡片、最近问答、知识/Skill/Token 概览 |
| 知识管理 | /knowledge | 列表/详情/编辑/上传，支持批量操作（删除/打标签/设分类） |
| 智能搜索 | /search | 语义+关键词搜索，二次筛选（分类/标签/时间） |
| 智能问答 | /qa | SSE 流式问答，来源标注、反馈、追问推荐 |
| 问答历史 | /qa/history | 历史记录、搜索、删除 |
| Skill 管理 | /skills | CRUD、分类自定义、模板创建、启用切换、路由测试 |
| 模型配置 | /models | LLM/Embedding 配置、连通测试、热更新 |
| Token 统计 | /token-stats | 趋势图、维度统计、缓存命中率 |
| 调用日志 | /call-logs | 所有模型调用日志（chat/embedding/test），含发起人 |

## API 接口

完整 Swagger 文档：http://localhost:8000/docs

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 健康 | GET | /health | 健康检查 |
| 模型 | GET | /api/models | 模型列表 |
| 模型 | GET | /api/models/status | 当前激活的 LLM/Embedding |
| 模型 | POST | /api/models | 新增模型配置 |
| 模型 | PUT | /api/models/{id} | 更新模型配置 |
| 模型 | DELETE | /api/models/{id} | 删除模型配置 |
| 模型 | PUT | /api/models/{id}/activate | 启用模型 |
| 模型 | POST | /api/models/{id}/test | 测试连通性 |
| 知识 | GET | /api/knowledge | 知识列表（分页、按分类/标签筛选） |
| 知识 | POST | /api/knowledge | 新增知识 |
| 知识 | GET | /api/knowledge/{id} | 知识详情 |
| 知识 | PUT | /api/knowledge/{id} | 更新知识 |
| 知识 | DELETE | /api/knowledge/{id} | 删除知识 |
| 知识 | POST | /api/knowledge/batch | 批量操作 |
| 知识 | POST | /api/knowledge/upload | 上传文件 |
| 知识 | GET | /api/knowledge/{id}/download | 下载文件 |
| 知识 | POST | /api/knowledge/rebuild-indexes | 重建所有索引 |
| Skill | GET | /api/skills | Skill 列表 |
| Skill | POST | /api/skills | 新增 Skill |
| Skill | POST | /api/skills/test-route | 测试路由匹配 |
| 搜索 | POST | /api/search | 语义/关键词搜索 |
| 问答 | POST | /api/qa/ask | 普通问答 |
| 问答 | POST | /api/qa/ask/stream | SSE 流式问答 |
| 问答 | GET | /api/qa/history | 问答历史 |
| 问答 | POST | /api/qa/feedback | 反馈有用/无用 |
| 仪表盘 | GET | /api/dashboard/stats | 统计数据 |
| 统计 | GET | /api/token-stats/summary | Token 汇总 |
| 统计 | GET | /api/token-stats/model-call-logs | 模型调用日志 |

## 测试

### 后端 API 测试

```bash
cd backend
python api_test.py
```

覆盖 21 个核心接口：健康检查、模型管理、知识 CRUD、分类标签、Skill、搜索（含语义/关键词）、问答（含 SSE 流式）、仪表盘、Token 统计。

### 前端 UI 自动化测试

```bash
cd frontend
npm test                # 单次运行
npm run test:watch      # 监听模式
npm run test:coverage   # 覆盖率报告
```

覆盖 10 个测试文件 51 个用例：Dashboard、MainLayout、ModelConfig、TokenStats、SkillList/Edit、QA、QAHistory、Search、SkillOptionManager。

### 构建验证

```bash
cd frontend
npm run build   # TypeScript 类型检查 + Vite 打包
```

## 预制数据

系统首次启动自动创建：
- 4 个分类：制造运营、仓储物流、质量管理、设备管理
- 6 个标签：故障代码、保养、工艺、质量标准、仓储管理、操作经验
- 5 个预制 Skill：故障诊断、保养维护、工艺指导、质量检验、通用问答
- 10 个 Skill 分类/功能选项（可自定义扩展）

## 数据源扩展

预留 `DataAdapter` 接口（[data_adapter.py](backend/app/services/data_adapter.py)），支持后续从外部数据库或 API 接入数据。MVP 阶段不实现具体适配器。

## 常见问题

**Q: 启动后端报 `ModuleNotFoundError: No module named 'uvicorn'`？**
A: 确认已激活虚拟环境并安装依赖 `pip install -r requirements.txt`。若本机多版本 Python 共存，明确指定解释器，如 `C:\Path\To\Python39\python.exe run.py`。

**Q: 模型测试报 404？**
A: 检查 API URL 是否填写了 base URL（如 `https://api.siliconflow.cn/v1`），系统会自动拼接 `/embeddings` 或 `/chat/completions`。若误填带后缀也会自动剥离。

**Q: 切换 Embedding 模型后检索失败？**
A: 切换不同维度的 Embedding 模型（如 384 维 → 1024 维）时，系统会自动捕获维度不匹配异常并重建 ChromaDB collection。也可手动调用 `POST /api/knowledge/rebuild-indexes` 重建所有索引。

**Q: 流式问答 token 显示为 0？**
A: 部分国产 LLM API（如小米 MiMo 非 stream 模式）不返回 usage 字段，导致 token 统计为 0。系统已对 stream 模式启用 `stream_options.include_usage` 以尽量获取准确 token 数。

**Q: 如何避免 API Key 泄露？**
A: API Key 使用 `cryptography` 库加密存储于数据库，前端展示脱敏（如 `sk-k***mnaf`）。`.env` 文件已加入 `.gitignore`，不会提交到仓库。

## 贡献指南

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m "feat: 添加某某功能"`
4. 推送分支：`git push origin feature/your-feature`
5. 提交 Pull Request

**提交规范**：
- `feat:` 新功能
- `fix:` 修复 bug
- `docs:` 文档更新
- `refactor:` 重构
- `test:` 测试相关
- `chore:` 构建/工具变动

## 许可证

本项目基于 [MIT License](LICENSE) 开源，可自由使用、修改、分发。

Copyright (c) 2026 Luerlei
