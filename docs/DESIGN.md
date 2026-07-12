# MOM 系统 AI 知识库平台 — 设计书

> **版本**：v0.5 | **更新日期**：2026-07-12 | **状态**：活跃维护中

---

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 系统架构](#2-系统架构)
- [3. 技术栈](#3-技术栈)
- [4. 目录结构](#4-目录结构)
- [5. 数据模型设计](#5-数据模型设计)
- [6. 后端设计](#6-后端设计)
- [7. 前端设计](#7-前端设计)
- [8. 核心业务流程](#8-核心业务流程)
- [9. 时序预测模块](#9-时序预测模块)
- [10. 安全设计](#10-安全设计)
- [11. 配置与部署](#11-配置与部署)
- [12. 版本演进](#12-版本演进)

---

## 1. 项目概述

### 1.1 定位

面向制造企业（MOM, Manufacturing Operations Management）的 AI 知识库平台，整合知识管理、智能问答、时序预测分析三大能力，为企业运营提供智能化决策支持。

### 1.2 核心能力

| 能力域 | 说明 |
|--------|------|
| 知识管理 | 多格式文件上传解析（PDF/DOCX/XLSX/MD）、Markdown 编辑、分类标签体系、向量索引 |
| 智能问答 | Skill 路由三级匹配 + 自实现轻量 RAG + SSE 流式输出 + 问答缓存 |
| 语义搜索 | 向量检索 + BM25 关键词检索 + RRF 融合排序 |
| 时序预测 | Chronos-2 / TimesFM 深度学习模型 + ARIMA/ETS/Theta 统计模型 + STL 分解 + 交叉验证 |
| 模型管理 | LLM / Embedding / Forecast 三类模型配置、运行时热更新、调用日志全量收集 |
| 认证授权 | JWT 可选认证、开发环境关闭、生产环境强制开启 |

### 1.3 设计原则

- **模型无关**：统一 `LLMClient` 抽象层，支持任意 OpenAI 兼容 API
- **自实现轻量 RAG**：不依赖 LangChain / LlamaIndex，直接使用 ChromaDB SDK + httpx
- **优雅降级**：无 Embedding 时 RAG 降级为直接对话；无 LLM 时预测分析回退为模板化摘要
- **运行时热更新**：模型配置存储于数据库，Web 界面修改后立即生效
- **安全第一**：API Key 加密存储、文件名防路径穿越、HTML 内容 DOMPurify 净化

---

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端 (Vue 3 + Vite)                     │
│  Ant Design Vue 4.x  |  Pinia  |  Vue Router  |  ECharts  │
│  16 个页面  |  7 个组件  |  13 个 API 模块  |  SSE 流式     │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / SSE  (Vite proxy → :8000)
┌────────────────────────┴────────────────────────────────┐
│                  后端 (FastAPI + Python 3.9)              │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐ │
│  │ 13 路由  │→ │ 18 服务  │→ │   数据访问层 (SQLAlchemy) │ │
│  │ /api/*   │  │ 业务逻辑 │  │  SQLite + ChromaDB     │ │
│  └──────────┘  └────┬─────┘  └────────────────────────┘ │
│                       │                                   │
│  ┌────────────────────┴────────────────────────────────┐ │
│  │              模型抽象层 (LLMClient)                  │ │
│  │  OpenAICompatibleClient  |  ForecastClient           │ │
│  └───────┬───────────────────────────┬────────────────┘ │
│          │ httpx                     │ httpx             │
│  ┌───────┴───────────┐     ┌────────┴─────────────────┐  │
│  │ 外部 LLM / Embedding│     │ Forecast 推理服务        │  │
│  │ (OpenAI/MiMo/Qwen) │     │ (Chronos :8501/8503)    │  │
│  └────────────────────┘     │ (TimesFM  :8502)        │  │
│                              └──────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 2.2 分层架构

```
表现层    │ Vue 3 页面 + 组件 + 路由
         │ 统一 API 封装（axios + 拦截器 + SSE）
──────────┼────────────────────────────────
接口层    │ FastAPI 路由（13 个模块）
         │ JWT 认证依赖 + 统一响应格式 + 全局异常处理
──────────┼────────────────────────────────
业务层    │ 18 个 Service
         │ RAG / Skill路由 / 缓存 / 向量存储 / 预测 / 文件解析
──────────┼────────────────────────────────
数据层    │ SQLAlchemy ORM（13 模型）+ ChromaDB（向量）
         │ SQLite 持久化 + 自动迁移
──────────┼────────────────────────────────
抽象层    │ LLMClient / OpenAICompatibleClient / ForecastClient
         │ ModelManager（内存缓存 + 热更新失效）
```

---

## 3. 技术栈

### 3.1 后端

| 组件 | 版本 | 用途 |
|------|------|------|
| Python | 3.9 | 运行环境 |
| FastAPI | 0.115.6 | Web 框架 |
| uvicorn | 0.34.0 | ASGI 服务器 |
| SQLAlchemy | 2.0.36 | ORM |
| ChromaDB | 0.5.23 | 向量数据库 |
| httpx | 0.28.1 | 异步 HTTP 客户端 |
| PyJWT | 2.10.1 | JWT 认证 |
| cryptography | 44.0.0 | API Key 加密 |
| PyPDF2 | 3.0.1 | PDF 解析 |
| python-docx | 1.1.2 | DOCX 解析 |
| openpyxl | 3.1.5 | Excel 解析 |
| statsmodels | — | ARIMA / ETS / STL |
| pydantic | 2.10.4 | 数据校验 |

### 3.2 前端

| 组件 | 版本 | 用途 |
|------|------|------|
| Vue | 3.4.27 | 前端框架 |
| TypeScript | 5.4.5 | 类型安全 |
| Vite | 5.2.11 | 构建工具 |
| Ant Design Vue | 4.2.3 | UI 组件库 |
| Pinia | 2.1.7 | 状态管理 |
| Vue Router | 4.3.2 | 路由管理 |
| ECharts | 5.5.0 | 数据可视化 |
| axios | 1.7.2 | HTTP 请求 |
| markdown-it | 14.1.0 | Markdown 渲染 |
| DOMPurify | 3.4.12 | HTML 净化 |
| Vitest | 4.1.9 | 单元测试 |

### 3.3 Forecast 推理服务（独立进程，Python 3.11）

| 组件 | 端口 | 说明 |
|------|------|------|
| Chronos-T5-Small | 8501 | 轻量预测 |
| TimesFM-2.5 | 8502 | Google 时序模型 |
| Chronos-T5-Large | 8503 | 高精度预测 |

---

## 4. 目录结构

```
LLM Wiki/
├── backend/                          # 后端服务
│   ├── app/
│   │   ├── main.py                   # FastAPI 入口（路由注册/中间件/生命周期）
│   │   ├── config.py                 # 配置管理（环境变量 + 安全校验）
│   │   ├── database.py               # 数据库初始化 + 自动迁移
│   │   ├── models/                   # 13 个数据模型
│   │   │   ├── __init__.py           # 模型导出
│   │   │   ├── category.py           # 分类（树形）
│   │   │   ├── tag.py                # 标签
│   │   │   ├── knowledge.py          # 知识 + KnowledgeTag 关联
│   │   │   ├── document.py           # 上传文档
│   │   │   ├── skill.py              # Skill 路由配置
│   │   │   ├── skill_option.py       # Skill 分类/功能选项
│   │   │   ├── model_config.py       # 模型配置
│   │   │   ├── qa_history.py         # 问答历史
│   │   │   ├── token_usage.py        # Token 消耗记录
│   │   │   ├── search_history.py     # 搜索历史
│   │   │   ├── dataset.py            # 时序数据集
│   │   │   └── forecast_task.py      # 预测任务 + 结果
│   │   ├── routers/                  # 13 个 API 路由模块
│   │   │   ├── auth.py               # 认证
│   │   │   ├── knowledge.py          # 知识管理
│   │   │   ├── category.py           # 分类管理
│   │   │   ├── tag.py                 # 标签管理
│   │   │   ├── skill.py              # Skill 管理
│   │   │   ├── skill_option.py       # Skill 选项
│   │   │   ├── model_config.py       # 模型配置
│   │   │   ├── search.py             # 搜索
│   │   │   ├── qa.py                 # 智能问答（SSE）
│   │   │   ├── dashboard.py          # 仪表盘
│   │   │   ├── token_stats.py        # Token 统计
│   │   │   ├── dataset.py            # 数据集管理
│   │   │   └── forecast.py           # 时序预测
│   │   ├── schemas/                  # Pydantic 验证模型
│   │   ├── services/                 # 18 个业务服务
│   │   │   ├── llm_client.py         # LLM 客户端抽象层 ★
│   │   │   ├── rag_service.py        # RAG 检索增强 ★
│   │   │   ├── qa_service.py         # 问答服务（含缓存）★
│   │   │   ├── skill_router.py       # Skill 三级路由 ★
│   │   │   ├── cache_service.py      # 向量相似度缓存
│   │   │   ├── vector_store.py       # ChromaDB 封装 ★
│   │   │   ├── embedding_service.py  # Embedding 服务
│   │   │   ├── forecast_service.py   # 时序预测（1850 行）★
│   │   │   ├── dataset_service.py    # 数据集管理
│   │   │   ├── knowledge_service.py  # 知识管理 + 索引同步
│   │   │   ├── search_service.py     # 语义 + 关键词搜索
│   │   │   ├── prompt_assembler.py   # Prompt 组装
│   │   │   ├── file_parser.py        # 文件解析
│   │   │   ├── text_chunker.py       # Markdown 感知分块
│   │   │   ├── model_service.py      # 模型配置管理
│   │   │   ├── skill_service.py      # Skill 管理
│   │   │   ├── skill_option_service  # Skill 选项管理
│   │   │   └── seed_service.py       # 预制数据初始化
│   │   └── utils/                    # 工具层
│   │       ├── auth.py               # JWT 认证
│   │       ├── crypto.py             # API Key 加密
│   │       ├── excel_parser.py        # Excel/CSV 解析
│   │       └── response.py           # 统一响应格式
│   ├── scripts/                      # Forecast 推理服务
│   │   ├── chronos_server.py         # Chronos HTTP 服务
│   │   └── timesfm_server.py         # TimesFM HTTP 服务
│   ├── data/                         # 数据目录（gitignore）
│   │   ├── knowledge.db              # SQLite
│   │   ├── vectors/                  # ChromaDB
│   │   └── uploads/                  # 上传文件
│   ├── run.py                        # 启动脚本
│   ├── requirements.txt
│   └── .env.example
├── frontend/                         # 前端应用
│   ├── src/
│   │   ├── main.ts                   # 入口
│   │   ├── App.vue                   # 根组件
│   │   ├── router/index.ts           # 路由配置（17 条路由）
│   │   ├── stores/app.ts             # Pinia 状态管理
│   │   ├── api/                      # 13 个 API 模块
│   │   │   ├── request.ts            # axios 封装（拦截器/401处理）
│   │   │   ├── auth.ts              # 认证
│   │   │   ├── knowledge.ts          # 知识
│   │   │   ├── category.ts          # 分类标签
│   │   │   ├── skill.ts             # Skill
│   │   │   ├── skillOption.ts       # Skill 选项
│   │   │   ├── model.ts             # 模型配置
│   │   │   ├── search.ts            # 搜索
│   │   │   ├── qa.ts                # 问答（含 SSE 流式）
│   │   │   ├── dashboard.ts         # 仪表盘统计
│   │   │   ├── dataset.ts           # 数据集
│   │   │   └── forecast.ts           # 时序预测
│   │   ├── types/index.ts            # TypeScript 类型定义
│   │   ├── layouts/
│   │   │   └── MainLayout.vue        # 主布局（侧边栏/顶栏/面包屑）
│   │   ├── components/               # 7 个通用组件
│   │   │   ├── AiChatButton.vue      # 浮动智能问答
│   │   │   ├── CategoryTree.vue      # 分类树
│   │   │   ├── FileUpload.vue       # 文件拖拽上传
│   │   │   ├── MarkdownEditor.vue   # Markdown 编辑器
│   │   │   ├── MarkdownView.vue      # Markdown 渲染
│   │   │   ├── SkillOptionManager.vue # Skill 选项管理
│   │   │   └── TagSelect.vue         # 标签选择器
│   │   └── views/                    # 16 个页面
│   │       ├── Login.vue             # 登录
│   │       ├── Dashboard.vue         # 仪表盘
│   │       ├── ModelConfig.vue       # 模型配置
│   │       ├── Search.vue            # 搜索
│   │       ├── QA.vue                # 智能问答
│   │       ├── QAHistory.vue         # 问答历史
│   │       ├── TokenStats.vue        # Token 统计
│   │       ├── CallLogs.vue          # 调用日志
│   │       ├── Trends.vue            # 趋势分析 ★
│   │       ├── knowledge/{List,Detail,Edit,Upload}.vue
│   │       ├── skill/{List,Edit}.vue
│   │       └── dataset/List.vue
│   ├── tests/                        # 51 个测试用例
│   └── package.json
├── docs/                             # 文档目录
│   ├── DESIGN.md                     # 本设计书
│   ├── chronos-deploy.md             # Chronos 部署指南
│   ├── chronos-large-deploy.md       # Chronos-Large 部署
│   └── timesfm-deploy.md             # TimesFM 部署
├── README.md
├── LICENSE                           # MIT
└── .gitignore
```

---

## 5. 数据模型设计

### 5.1 ER 概览

```
┌───────────┐     ┌───────────┐     ┌──────────────┐
│ Category   │1---*│ Knowledge │*---*│    Tag        │
│ (分类树)    │     │ (知识)    │     │   (标签)      │
└───────────┘     └─────┬─────┘     └──────────────┘
                        │1
                        │
                  ┌─────*─────┐
                  │ Document   │
                  │ (上传文档)  │
                  └───────────┘

┌───────────┐     ┌──────────────┐     ┌───────────┐
│ Skill       │1---*│ QAHistory     │1---*│ TokenUsage  │
│ (技能路由)  │     │ (问答历史)    │     │ (Token消耗) │
└─────┬─────┘     └──────────────┘     └───────────┘
      │
      │1
┌─────*──────┐
│SkillOption  │
│(分类/功能)   │
└────────────┘

┌───────────┐     ┌──────────────┐     ┌──────────────┐
│ModelConfig  │     │  Dataset      │1---*│ ForecastTask │
│(模型配置)   │     │ (时序数据集)  │     │ (预测任务)    │
└─────┬─────┘     └──────────────┘     └──────┬──────┘
      │                                        │1
      │                                        │
      └──────────────────────────────────┌────*──────┐
                                          │ForecastResult│
                                          │ (预测结果)    │
                                          └─────────────┘

┌──────────────┐
│SearchHistory  │  (独立表)
│(搜索历史)      │
└──────────────┘
```

### 5.2 模型清单（13 个）

| # | 模型 | 表名 | 说明 |
|---|------|------|------|
| 1 | Category | categories | 分类，自引用树形结构 |
| 2 | Tag | tags | 标签，含颜色 |
| 3 | Knowledge | knowledge | 知识条目，含 Markdown 内容 |
| 4 | KnowledgeTag | knowledge_tag_relation | 知识-标签多对多关联 |
| 5 | Document | documents | 上传文件记录 |
| 6 | Skill | skills | Skill 路由配置 |
| 7 | SkillOption | skill_options | Skill 分类/功能选项 |
| 8 | ModelConfig | model_configs | 模型配置（LLM/Embedding/Forecast） |
| 9 | QAHistory | qa_history | 问答历史 |
| 10 | TokenUsage | token_usage | Token 消耗记录 |
| 11 | SearchHistory | search_history | 搜索历史 |
| 12 | Dataset | datasets | 时序数据集 |
| 13 | ForecastTask + ForecastResult | forecast_tasks / forecast_results | 预测任务和结果 |

### 5.3 关键字段说明

#### ModelConfig（模型配置）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 主键 |
| name | String(100) | 配置名称 |
| type | String(20) | 模型类型：LLM / Embedding / Forecast |
| api_url | String(500) | API 地址（base URL） |
| api_key | String(500) | API Key（Fernet 加密存储） |
| model_name | String(100) | 模型名称 |
| is_active | Boolean | 是否启用（同类型仅一个） |
| input_price | Float | 输入 token 单价（元/千 token） |
| output_price | Float | 输出 token 单价（元/千 token） |

#### TokenUsage（Token 消耗记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| call_type | String(30) | 调用类型：chat / embedding / test / forecast / trend_analysis |
| model_name | String(100) | 模型名称 |
| input_tokens | Integer | 输入 token |
| output_tokens | Integer | 输出 token |
| duration_ms | Integer | 耗时毫秒 |
| source | String(50) | 发起来源：qa / qa_cache / search / sync_index / skill_router / test_model |
| skill_id | Integer FK | 关联 Skill |
| qa_history_id | Integer FK | 关联问答历史 |

#### Skill（技能路由）

| 字段 | 类型 | 说明 |
|------|------|------|
| name | String(100) | Skill 名称 |
| category | String(50) | 模块维度（制造运营/仓储物流/...） |
| function | String(50) | 功能维度（故障诊断/保养维护/...） |
| trigger_keywords | Text (JSON) | 触发关键词列表 |
| trigger_patterns | Text (JSON) | 触发正则表达式列表 |
| prompt_template | Text | Prompt 模板（含 {context} {question} 变量） |
| knowledge_scope | Text (JSON) | 知识范围 `{"category_ids":[],"tag_ids":[]}` |
| is_default | Boolean | 是否默认兜底 Skill |

---

## 6. 后端设计

### 6.1 API 路由总览（13 个模块，70+ 端点）

| 模块 | 前缀 | 核心端点 |
|------|------|---------|
| 认证 | /api/auth | login / me / status |
| 知识管理 | /api/knowledge | CRUD + upload + batch + rebuild-indexes + download |
| 分类管理 | /api/categories | 树形 CRUD |
| 标签管理 | /api/tags | CRUD |
| Skill 管理 | /api/skills | CRUD + templates + test-route |
| Skill 选项 | /api/skill-options | CRUD |
| 模型配置 | /api/models | CRUD + activate + test + status |
| 搜索 | /api/search | semantic + keyword + history |
| 智能问答 | /api/qa | ask(SSE) + feedback + suggestions + history |
| 仪表盘 | /api/dashboard | stats + recent-qa |
| Token 统计 | /api/token-stats | summary + call-logs + model-call-logs |
| 数据集 | /api/datasets | CRUD + import + export + preview + template |
| 时序预测 | /api/forecast | predict + tasks + results + cross-validation + compare-models + statistical-forecast + decomposition + export |

### 6.2 服务层核心设计

#### 6.2.1 LLM 客户端抽象层（llm_client.py）

```
LLMClient (ABC)
├── chat(messages) → dict          # 非流式对话
├── chat_stream(messages) → gen    # 流式对话（SSE）
└── embedding(texts) → list       # 向量化

OpenAICompatibleClient(LLMClient)
├── __init__(config)              # 自动剥离 /embeddings、/chat/completions 后缀
├── chat()                        # 返回 {content, input_tokens, output_tokens, model, duration_ms}
├── chat_stream()                 # 强制 stream_options.include_usage=True
├── embedding()                   # 按 index 排序保证顺序
└── last_usage                    # 供调用方读取 token 数

ForecastClient
└── predict(series, horizon, quantiles) → dict   # 调用 /predict 端点

ModelManager (单例)
├── _cache: {type: client}        # 内存缓存
├── get_active_llm()              # 获取启用的 LLM
├── get_active_embedding()        # 获取启用的 Embedding（未配置抛错让调用方降级）
├── get_active_forecast()         # 获取启用的 Forecast
└── invalidate_cache(type)        # 配置变更时失效缓存
```

**缓存机制**：`ModelManager` 维护类级缓存 `_cache`，命中时通过轻量 DB 查询确认配置 ID 未变更，否则用 `client_factory` 构造新客户端。

#### 6.2.2 RAG 服务（rag_service.py）

**混合检索 + RRF 融合**：

```
_hybrid_search(question, skill, db)
  │
  ├─ 向量检索：vector_store.search(q_vec, where=scope, top_k=N)
  │
  ├─ BM25 检索：_bm25_search(db, question, scope)  # SQLite LIKE + jieba 分词
  │
  ├─ 合并：knowledge_id → best chunk
  │
  └─ RRF 融合：score(d) = Σ 1/(k + rank_i(d))   # k=60
```

**降级策略**：无 Embedding 模型时 `degraded=True`，仅走 BM25 关键词检索。

#### 6.2.3 Skill 路由（skill_router.py）

**三级匹配**：

```
route(question, db)
  │
  ├─ 1. 关键词/正则匹配（优先级最高）
  │     遍历所有启用 Skill，统计 trigger_keywords + trigger_patterns 命中数
  │     返回命中数最多的 Skill → match_type="keyword"
  │
  ├─ 2. 语义匹配（阈值 > 0.7）
  │     问题 Embedding vs Skill description Embedding 余弦相似度
  │     Skill description 走内存缓存（md5 为 key）
  │     返回最相似且 > 0.7 的 Skill → match_type="semantic"
  │
  └─ 3. 默认兜底
        返回 is_default=True 的 Skill → match_type="default"
```

#### 6.2.4 向量存储（vector_store.py）

| 特性 | 说明 |
|------|------|
| 持久化 | ChromaDB PersistentClient |
| 距离度量 | 余弦距离 `cosine` |
| 两个 collection | `knowledge`（知识向量）、`answer_cache`（答案缓存） |
| 维度自适应 | 捕获维度不匹配异常自动重建 collection |
| 距离转相似度 | `score = 1.0 - distance` |

#### 6.2.5 问答缓存（cache_service.py）

- **机制**：基于 ChromaDB `answer_cache` collection，向量相似度检索最相似的问题
- **阈值**：`CACHE_SIMILARITY_THRESHOLD = 0.90`
- **失效**：知识更新/删除时主动调用 `answer_cache.clear()` 清空全部缓存
- **命中标记**：`QAHistory.is_cache_hit = 1`，`token_input/output = 0`

#### 6.2.6 文件解析（file_parser.py）

| 格式 | 解析器 | 特性 |
|------|--------|------|
| PDF | PyPDF2 | 逐页提取 |
| DOCX | python-docx | 段落 + 表格 |
| XLSX | openpyxl | 多 sheet |
| MD | 原生 | UTF-8 |
| TXT | 多编码 | utf-8/gbk/gb18030/latin-1 自动尝试 |
| HTML | BeautifulSoup | 移除 script/style，正则兜底 |

**安全措施**：文件名清理防路径穿越、流式分片写入（1MB chunk）防 OOM、大小限制 50MB。

#### 6.2.7 文本分块（text_chunker.py）

- **Markdown 标题层级感知**：保留标题路径前缀（如 `# 第一章 > 1.1 概述`）
- **参数**：`chunk_size=500, overlap=50`
- **策略**：有 Markdown 标题按标题分块，否则按段落 + 长度分块

---

## 7. 前端设计

### 7.1 路由配置（17 条路由）

| 路径 | 页面 | 认证 | 说明 |
|------|------|------|------|
| /login | Login | 公开 | 登录页 |
| /dashboard | Dashboard | 需认证 | 仪表盘 |
| /knowledge | KnowledgeList | 需认证 | 知识列表 |
| /knowledge/upload | KnowledgeUpload | 需认证 | 批量上传 |
| /knowledge/edit/:id? | KnowledgeEdit | 需认证 | 编辑知识 |
| /knowledge/detail/:id | KnowledgeDetail | 需认证 | 知识详情 |
| /search | Search | 需认证 | 搜索 |
| /qa | QA | 需认证 | 智能问答（SSE 流式） |
| /qa/history | QAHistory | 需认证 | 问答历史 |
| /skills | SkillList | 需认证 | Skill 管理 |
| /skills/edit/:id? | SkillEdit | 需认证 | 编辑 Skill |
| /models | ModelConfig | 需认证 | 模型配置 |
| /token-stats | TokenStats | 需认证 | Token 统计 |
| /call-logs | CallLogs | 需认证 | 调用日志 |
| /datasets | DatasetList | 需认证 | 数据集管理 |
| /trends | Trends | 需认证 | 趋势分析 |

**认证守卫**：首次访问动态探测后端是否启用认证，启用时无 token 重定向到 `/login?redirect=原路径`。

### 7.2 状态管理（Pinia）

#### useAppStore（全局应用状态）

| State | 说明 |
|-------|------|
| modelStatus | 当前 LLM / Embedding / Forecast 启用状态 |
| needsGuide | 是否需要首次引导 |
| collapsed | 侧边栏折叠状态 |

| Getter | 说明 |
|--------|------|
| hasActiveLLM | 是否有启用的 LLM |
| isConfigured | 是否完成首次配置（仅判断 hasActiveLLM） |

### 7.3 通用组件

| 组件 | 功能 |
|------|------|
| AiChatButton | 右下角浮动智能问答，流式接收、Markdown 渲染、可中断 |
| CategoryTree | 分类树展示，节点显示知识数量徽标，支持 CRUD |
| FileUpload | 拖拽上传，文件队列表格，大小格式化 |
| MarkdownEditor | 分屏编辑器（编辑 + 预览），工具栏（标题/粗体/列表/代码/链接/引用） |
| MarkdownView | Markdown 只读渲染 |
| SkillOptionManager | Skill 分类/功能选项管理弹窗 |
| TagSelect | 标签多选 + 搜索 + 新建（带颜色面板） |

### 7.4 请求封装（request.ts）

```
axios 实例（baseURL: /api, timeout: 30s）
  │
  ├─ 请求拦截器：注入 Authorization: Bearer <token>
  │
  └─ 响应拦截器：
       ├─ code !== 0 → message.error + reject
       ├─ 401 → 清 token + 重定向登录
       ├─ 403 → "禁止访问"
       ├─ 404 → "请求的资源不存在"
       └─ 500+ → "服务器错误"
```

**SSE 流式**：`askQuestionStream()` 直接用 `fetch + ReadableStream + TextDecoder` 解析 SSE，兼容多种事件字段，支持 `AbortSignal` 中断。

---

## 8. 核心业务流程

### 8.1 智能问答完整流程

```
用户提问 "设备异常怎么处理？"
  │
  ▼
qa_service.ask(db, question, use_cache=True)
  │
  ├─ 1. Skill 路由
  │    skill_router.route(question, db)
  │    → 关键词 "设备异常" 命中 "故障诊断" Skill
  │    → match_type="keyword"
  │
  ├─ 2. 计算查询向量（复用优化）
  │    q_embedding = embedding_service.embed([question], source="qa_cache")
  │
  ├─ 3. 检查缓存
  │    answer_cache.get(q_embedding)
  │    ├─ 命中（相似度 > 0.90）→ 返回缓存答案，is_cache_hit=1
  │    └─ 未命中 ↓
  │
  ├─ 4. RAG 检索增强
  │    rag_service.answer(question, skill, db, q_embedding=q_embedding)
  │    │
  │    ├─ 4a. 混合检索
  │    │    _hybrid_search(q_vec, question, skill, db)
  │    │    ├─ 向量检索：ChromaDB 余弦检索 top_k=5
  │    │    ├─ BM25 检索：SQLite LIKE + jieba 分词
  │    │    └─ RRF 融合：score = Σ 1/(60 + rank)
  │    │
  │    ├─ 4b. Prompt 组装
  │    │    prompt_assembler.assemble(skill, question, context_chunks)
  │    │    → Token 预算控制（MAX_CONTEXT_TOKENS=4000）
  │    │
  │    └─ 4c. LLM 生成
  │         llm.chat(messages) → {content, tokens, model}
  │
  ├─ 5. 保存历史
  │    QAHistory(question, answer, sources, skill_id, tokens)
  │
  ├─ 6. 记录 TokenUsage
  │    TokenUsage(call_type="chat", source="qa", model_name, tokens)
  │
  └─ 7. 写入缓存
       answer_cache.put(question, answer, q_embedding)
```

### 8.2 SSE 流式问答

```
POST /api/qa/ask  (Accept: text/event-stream)
  │
  ├─ event: skill      → {"skill_name": "故障诊断", "match_type": "keyword"}
  ├─ event: sources    → {"sources": [...], "degraded": false}
  ├─ event: chunk      → {"content": "根据"} (逐步 yield)
  ├─ event: chunk      → {"content": "设备手册"}
  ├─ ...
  └─ event: done       → {"history_id": 42, "tokens": {...}}
```

**取消处理**：捕获 `asyncio.CancelledError`，保存已生成的部分答案到 `QAHistory`。

### 8.3 搜索流程

```
GET /api/search/semantic?q=设备保养&category_id=1&tag_ids=2,3
  │
  ├─ 向量化查询
  ├─ ChromaDB 检索（top_k = page * page_size * 2）
  ├─ 批量查询 Knowledge（joinedload 避免 N+1）
  ├─ 应用层过滤：tag_ids + 时间范围
  ├─ 去重（每个 knowledge_id 取第一个 chunk）
  └─ 分页返回
```

**降级**：语义搜索失败时前端自动切换为关键词搜索。

---

## 9. 时序预测模块

### 9.1 架构

```
┌─────────────────────────────────────────────────────┐
│                   forecast_service.py (1850 行)      │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐  │
│  │ 数据预处理 │  │ 预测执行  │  │ 评估与分析          │  │
│  │ 缺失值插值 │  │          │  │ 回测误差 MAE/MAPE  │  │
│  │ IQR异常截断│  │ Chronos  │  │ 扩展指标 MASE     │  │
│  │          │  │ TimesFM  │  │ LLM 分析报告       │  │
│  └──────────┘  │ ARIMA    │  │ STL 季节性分解     │  │
│                │ ETS/Theta │  │ 交叉验证           │  │
│  ┌──────────┐  └──────────┘  │ 多模型对比          │  │
│  │ 时间标签   │              └────────────────────┘  │
│  │ 自动生成   │                                       │
│  └──────────┘                                       │
└─────────────────────────────────────────────────────┘
```

### 9.2 预测模式

| 模式 | 说明 |
|------|------|
| 预测未来 | 从历史末尾预测未来 horizon 步 |
| 回测对照 | 从 start_index 拆分，训练集预测，与 actuals 对比计算误差 |
| 滑动窗口 | 仅使用最后 train_window 个点训练（N6 优化） |

### 9.3 模型类型

| 类型 | 模型 | 说明 |
|------|------|------|
| 深度学习 | Chronos-2 / TimesFM 2.5 | 调用 Forecast 推理服务 HTTP /predict |
| 统计模型 | ARIMA | 自动 AIC 搜索阶数（p,d,q 网格搜索） |
| 统计模型 | ETS | 指数平滑，置信区间随 horizon 增长 |
| 统计模型 | Theta | θ=0 + θ=2 取平均 |

### 9.4 评估指标

| 指标 | 说明 |
|------|------|
| MAE | 平均绝对误差 |
| MAPE | 平均绝对百分比误差 |
| RMSE | 均方根误差 |
| MASE | 平均绝对缩放误差（扩展） |
| sMAPE | 对称平均绝对百分比误差（扩展） |
| Pinball Loss | 概率预测损失（分位数） |
| Coverage | 置信区间覆盖率 |
| rMAE | 相对 MAE（模型 / Naive 基线） |

### 9.5 高级功能

- **交叉验证**：支持 expanding / sliding 策略，多次回测取平均和标准差
- **多模型对比**：临时切换激活模型执行回测，按 MAE 最低找出最优模型
- **STL 季节性分解**：基于 statsmodels，返回趋势/季节/残差分量 + 季节性强度
- **LLM 分析报告**：调用 LLM 生成自然语言趋势分析（含历史采样优化避免 token 过多）
- **统计基线**：Naive / SeasonalNaive 作为对照基准

---

## 10. 安全设计

### 10.1 认证与授权

| 机制 | 说明 |
|------|------|
| JWT 认证 | HS256 算法，`JWT_EXPIRE_HOURS` 控制（默认 24h） |
| 可选认证 | `AUTH_ENABLED` 环境变量控制，开发环境默认关闭 |
| 生产强制 | `DEBUG=false` 时强制校验 AUTH_ENABLED=true |
| 路由保护 | 所有业务路由 `Depends(require_auth)` |

### 10.2 数据安全

| 机制 | 说明 |
|------|------|
| API Key 加密 | Fernet 对称加密（PBKDF2HMAC 派生密钥，100000 次迭代） |
| API Key 脱敏 | 输出时 `前4+***+后4` |
| 文件名清理 | 去除路径分隔符、Windows 保留字符、控制字符 |
| HTML 净化 | DOMPurify 白名单（仅允许安全标签和属性） |
| Markdown 安全 | `html: false` 禁止原生 HTML 渲染 |

### 10.3 生产环境安全校验

启动时 `validate_security_config()` 在 `DEBUG=false` 时强制检查：

- `SECRET_KEY` 不能为默认值
- `ADMIN_PASSWORD` 不能为 `changeme`
- `CORS_ORIGINS` 不能为 `*`
- `AUTH_ENABLED` 必须为 `true`

---

## 11. 配置与部署

### 11.1 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| DATABASE_URL | sqlite:///data/knowledge.db | 数据库 |
| VECTOR_DB_PATH | data/vectors | 向量库路径 |
| UPLOAD_PATH | data/uploads | 上传路径 |
| SECRET_KEY | dev-secret-key-change-in-production | JWT + 加密密钥 |
| AUTH_ENABLED | false | 认证开关 |
| ADMIN_USERNAME | admin | 管理员用户名 |
| ADMIN_PASSWORD | changeme | 管理员密码 |
| JWT_EXPIRE_HOURS | 24 | Token 过期时间 |
| HOST / PORT | 0.0.0.0 / 8000 | 监听地址 |
| DEBUG | false | 调试模式 |
| CORS_ORIGINS | * | CORS 来源 |
| CACHE_SIMILARITY_THRESHOLD | 0.90 | 缓存阈值 |

### 11.2 自动迁移机制

`_auto_migrate()` 基于 SQLite `ALTER TABLE ADD COLUMN`：
- 查询现有列（`PRAGMA table_info`）
- 仅添加不存在的列
- 失败不阻塞启动（记录日志）

### 11.3 预制数据

系统首次启动自动创建：
- 4 个分类（制造运营/仓储物流/质量管理/设备管理）
- 6 个标签（故障代码/保养/工艺/质量标准/仓储管理/操作经验）
- 5 个预制 Skill（故障诊断/保养维护/工艺指导/质量检验/通用问答[默认]）
- 10 个 Skill 分类/功能选项
- 2 个 Forecast 模型配置（Chronos-2 / TimesFM 2.5）
- 2 个示例时序数据集

### 11.4 启动

```bash
# 后端
cd backend
python run.py    # http://localhost:8000

# 前端
cd frontend
npm run dev      # http://localhost:5173

# Forecast 推理服务（可选，独立进程）
cd backend/scripts
python chronos_server.py   # :8501
python timesfm_server.py  # :8502
```

---

## 12. 版本演进

| 版本 | 日期 | 核心内容 |
|------|------|---------|
| v0.1 | 2026-07-07 | 初始版本：知识库 + 智能问答 + Skill 路由 + RAG + 模型配置 + Token 统计 |
| v0.2 | 2026-07-08 | 新增 Forecast 时序预测模型支持（Chronos-2 / TimesFM） |
| v0.3 | 2026-07-09 | 新增 TimesFM 推理服务及 Chronos-Large 部署文档 |
| v0.4 | 2026-07-10 | 增加时序分析功能（数据集管理 + 预测任务 + 趋势可视化） |
| v0.5 | 2026-07-12 | 优化一系列问题，增强一系列功能（认证系统、混合检索 RRF、多模型对比、交叉验证、STL 分解、调用日志等） |

---

## 附录

### A. 统一响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

### B. API Key 加密流程

```
用户输入 API Key
  ↓
crypto.encrypt(plaintext)
  ↓ Fernet(PBKDF2HMAC(SHA256, SECRET_KEY, salt, 100000))
加密密文存入 ModelConfig.api_key
  ↓
读取时 crypto.decrypt(ciphertext) → 原文
输出时 crypto.mask(key) → "sk-k***mnaf"
```

### C. 降级策略汇总

| 场景 | 降级方式 |
|------|---------|
| 无 Embedding 模型 | RAG 仅走 BM25 关键词检索，`degraded=True` |
| 无 LLM 模型 | 预测分析回退为模板化摘要 |
| LLM 流式超时 | thinking 模型用流式调用避免 >120s 超时 |
| 向量维度不匹配 | 自动重建 ChromaDB collection |
| 缓存写入失败 | 不影响主流程，仅记录日志 |
| 语义搜索失败 | 前端自动切换为关键词搜索 |
| jieba 不可用 | 回退到正则切分分词 |
| BeautifulSoup 未安装 | HTML 解析回退到正则去标签 |

---

*本文档由项目设计书自动生成，基于 v0.5 代码库实际架构。*
