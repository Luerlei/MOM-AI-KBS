# MOM 系统 AI 知识库平台 — 设计书

> **版本**：v0.8 | **更新日期**：2026-07-14 | **状态**：活跃维护中

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
- [10. 协变量系统（v0.6 新增）](#10-协变量系统v06-新增)
- [11. 知识状态生命周期（v0.6 新增）](#11-知识状态生命周期v06-新增)
- [12. 安全设计](#12-安全设计)
- [13. 配置与部署](#13-配置与部署)
- [14. 版本演进](#14-版本演进)
- [15. 用户文档与演示数据（v0.7 新增）](#15-用户文档与演示数据v07-新增)
- [16. OCR/VLM 深度文档解析（v0.8 新增）](#16-ocrvlm-深度文档解析v08-新增)
- [17. 性能优化（v0.8 新增）](#17-性能优化v08-新增)

---

## 1. 项目概述

### 1.1 定位

面向制造企业（MOM, Manufacturing Operations Management）的 AI 知识库平台，整合知识管理、智能问答、时序预测分析三大能力，为企业运营提供智能化决策支持。

### 1.2 核心能力

| 能力域 | 说明 |
|--------|------|
| 知识管理 | 多格式文件上传解析（PDF/DOCX/XLSX/MD）、Markdown 编辑、分类标签体系、向量索引、**状态生命周期管理（v0.6）** |
| 智能问答 | Skill 路由三级匹配 + 自实现轻量 RAG + SSE 流式输出 + 问答缓存 |
| 语义搜索 | 向量检索 + BM25 关键词检索 + RRF 融合排序 |
| 时序预测 | Chronos-2 / TimesFM 深度学习模型 + ARIMA/ETS/Theta/Prophet 统计模型 + **协变量外生变量支持（v0.6）** + STL 分解 + 交叉验证 |
| 模型管理 | LLM / Embedding / Forecast / Rerank / **OCR / VLM 六类模型配置（v0.8）**、运行时热更新、调用日志全量收集 |
| 认证授权 | JWT 可选认证、开发环境关闭、生产环境强制开启 |
| 用户文档 | **完整使用说明书 + 演示实例数据 + 实例问题对照表（v0.7 新增）** |
| 深度文档解析 | **DeepSeek-OCR / VLM 视觉解析 + PyPDF2 兜底（v0.8 新增）** |
| 引用溯源 | **检索结果携带 chunk_id + page_number，前端展示来源页码（v0.8 新增）** |

### 1.3 设计原则

- **模型无关**：统一 `LLMClient` 抽象层，支持任意 OpenAI 兼容 API
- **自实现轻量 RAG**：不依赖 LangChain / LlamaIndex，直接使用 ChromaDB SDK + httpx
- **优雅降级**：无 Embedding 时 RAG 降级为直接对话；无 LLM 时预测分析回退为模板化摘要
- **运行时热更新**：模型配置存储于数据库，Web 界面修改后立即生效
- **安全第一**：API Key 加密存储、文件名防路径穿越、HTML 内容 DOMPurify 净化
- **审计可追溯**：知识状态变更全量记录审计日志（v0.6）

---

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    前端 (Vue 3 + Vite)                       │
│  Ant Design Vue 4.x  |  Pinia  |  Vue Router  |  ECharts    │
│  17 个页面  |  7 个组件  |  14 个 API 模块  |  SSE 流式       │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP / SSE  (Vite proxy → :8000)
┌─────────────────────────┴───────────────────────────────────┐
│                  后端 (FastAPI + Python 3.9)                │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────────┐ │
│  │ 14 路由  │→ │ 21 服务  │→ │   数据访问层 (SQLAlchemy)   │ │
│  │ /api/*   │  │ 业务逻辑 │  │  SQLite + ChromaDB        │ │
│  └──────────┘  └────┬─────┘  └───────────────────────────┘ │
│                       │                                     │
│  ┌────────────────────┴───────────────────────────────────┐ │
│  │              模型抽象层 (LLMClient)                      │ │
│  │  OpenAICompatibleClient  |  ForecastClient               │ │
│  │  RerankClient  |  OCRClient ★v0.8                         │ │
│  └───────┬───────────────────────────┬─────────────────────┘ │
│          │ httpx                     │ httpx                  │
│  ┌───────┴────────────┐     ┌────────┴────────────────────┐  │
│  │ 外部 LLM / Embedding│     │ Forecast 推理服务           │  │
│  │ (OpenAI/MiMo/Qwen) │     │ (Chronos :8501/8503)       │  │
│  └────────────────────┘     │ (TimesFM  :8502)           │  │
│                              │ (Prophet 内置 statsmodels) │  │
│                              └────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  OCR/VLM 解析后端 ★v0.8                                  │  │
│  │  DeepSeek-OCR (PDF 直输入)  |  VLM (PyMuPDF 按页转图)   │  │
│  │  PyPDF2 兜底                                              │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 分层架构

```
表现层    │ Vue 3 页面 + 组件 + 路由
         │ 统一 API 封装（axios + 拦截器 + SSE）
──────────┼────────────────────────────────
接口层    │ FastAPI 路由（14 个模块）
         │ JWT 认证依赖 + 统一响应格式 + 全局异常处理
──────────┼────────────────────────────────
业务层    │ 21 个 Service
         │ RAG / Skill路由 / 缓存 / 向量存储 / 预测 / 文件解析
         │ 协变量管理 / 知识状态审计（v0.6）/ BM25 索引 / PDF 解析后端（v0.8）
──────────┼────────────────────────────────
数据层    │ SQLAlchemy ORM（15 模型）+ ChromaDB（向量）
         │ SQLite 持久化 + 自动迁移 + BM25 内存倒排索引（v0.8）
──────────┼────────────────────────────────
抽象层    │ LLMClient / OpenAICompatibleClient / ForecastClient
         │ RerankClient / OCRClient（v0.8 新增）
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
| statsmodels | — | ARIMA / ETS / Theta / STL |
| prophet | — | Prophet 时序预测（v0.6 接入协变量） |
| numpy | — | 协变量矩阵运算（v0.6） |
| PyMuPDF | — | VLM 后端按页转图（v0.8 新增，可选） |
| jieba | — | BM25 中文分词（v0.8 新增） |
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
| Prophet | 内置 | 可加季节性 + 协变量（v0.6） |

### 3.4 OCR/VLM 解析服务（v0.8 新增，外部 API）

| 后端 | 模型示例 | 说明 |
|------|---------|------|
| DeepSeek-OCR | `deepseek-ai/DeepSeek-OCR` | PDF 原生 base64 输入，返回结构化 Markdown |
| VLM | `Qwen/Qwen3-VL-32B-Instruct` / `gpt-4o` | PyMuPDF 按页转图后调用 vision API |
| PyPDF2 | — | 兜底，零依赖文本层抽取 |

---

## 4. 目录结构

```
LLM Wiki/
├── backend/                          # 后端服务
│   ├── app/
│   │   ├── main.py                   # FastAPI 入口（14 个路由注册）
│   │   ├── config.py                 # 配置管理（环境变量 + 安全校验）
│   │   ├── database.py               # 数据库初始化 + 自动迁移
│   │   ├── data/                     # ★ v0.6 新增：静态数据
│   │   │   └── china_holidays.json   #   中国节假日数据集（2024-2026）
│   │   ├── models/                   # 15 个数据模型
│   │   │   ├── __init__.py
│   │   │   ├── category.py           # 分类（树形）
│   │   │   ├── tag.py                # 标签
│   │   │   ├── knowledge.py          # 知识 + status 字段 ★
│   │   │   ├── knowledge_status_log.py # ★ v0.6 新增：状态审计日志
│   │   │   ├── document.py           # 上传文档
│   │   │   ├── skill.py              # Skill 路由配置
│   │   │   ├── skill_option.py       # Skill 分类/功能选项
│   │   │   ├── model_config.py       # 模型配置
│   │   │   ├── qa_history.py         # 问答历史
│   │   │   ├── token_usage.py        # Token 消耗记录
│   │   │   ├── search_history.py     # 搜索历史
│   │   │   ├── dataset.py            # 时序数据集
│   │   │   ├── forecast_task.py      # 预测任务 + 结果
│   │   │   └── covariate.py          # ★ v0.6 新增：协变量
│   │   ├── routers/                  # 14 个 API 路由模块
│   │   │   ├── auth.py               # 认证
│   │   │   ├── knowledge.py          # 知识管理（含状态审计端点）★
│   │   │   ├── category.py           # 分类管理
│   │   │   ├── tag.py                # 标签管理
│   │   │   ├── skill.py              # Skill 管理
│   │   │   ├── skill_option.py       # Skill 选项
│   │   │   ├── model_config.py       # 模型配置
│   │   │   ├── search.py             # 搜索
│   │   │   ├── qa.py                 # 智能问答（SSE）
│   │   │   ├── dashboard.py          # 仪表盘
│   │   │   ├── token_stats.py        # Token 统计
│   │   │   ├── dataset.py            # 数据集管理
│   │   │   ├── forecast.py           # 时序预测（含协变量支持）★
│   │   │   └── covariate.py          # ★ v0.6 新增：协变量管理
│   │   ├── schemas/                  # Pydantic 验证模型
│   │   ├── services/                 # 21 个业务服务
│   │   │   ├── llm_client.py         # LLM 客户端抽象层（含 OCRClient ★v0.8）
│   │   │   ├── rag_service.py        # RAG 检索增强（真 BM25 ★v0.8）
│   │   │   ├── qa_service.py         # 问答服务（含缓存）★
│   │   │   ├── skill_router.py       # Skill 三级路由 ★
│   │   │   ├── cache_service.py      # 向量相似度缓存
│   │   │   ├── vector_store.py       # ChromaDB 封装 ★
│   │   │   ├── embedding_service.py  # Embedding 服务
│   │   │   ├── forecast_service.py   # 时序预测（含协变量接入）★
│   │   │   ├── covariate_service.py  # ★ v0.6 新增：协变量管理
│   │   │   ├── dataset_service.py    # 数据集管理
│   │   │   ├── knowledge_service.py  # 知识管理 + 状态审计 + 索引同步（含 chunk_id/page_number ★v0.8）
│   │   │   ├── search_service.py     # 语义 + 关键词搜索
│   │   │   ├── prompt_assembler.py   # Prompt 组装
│   │   │   ├── file_parser.py        # 文件解析（含 PDF 后端选择 ★v0.8）
│   │   │   ├── pdf_parser_backend.py # ★ v0.8 新增：PDF 解析后端抽象（PyPDF2/DeepSeek-OCR/VLM）
│   │   │   ├── bm25_service.py       # ★ v0.8 新增：Okapi BM25 内存索引
│   │   │   ├── text_chunker.py       # 段落感知+句子边界+滑动窗口分块（★v0.8 升级）
│   │   │   ├── model_service.py      # 模型配置管理（含 OCR/VLM 测试 ★v0.8）
│   │   │   ├── skill_service.py      # Skill 管理
│   │   │   ├── skill_option_service  # Skill 选项管理
│   │   │   └── seed_service.py       # 预制数据初始化（含辅助模型 ★v0.8）
│   │   └── utils/                    # 工具层
│   │       ├── auth.py               # JWT 认证
│   │       ├── crypto.py             # API Key 加密
│   │       ├── excel_parser.py        # Excel/CSV 解析
│   │       └── response.py           # 统一响应格式
│   ├── scripts/                      # Forecast 推理服务 + 演示数据脚本
│   │   ├── chronos_server.py         # Chronos HTTP 服务
│   │   ├── timesfm_server.py         # TimesFM HTTP 服务
│   │   └── seed_demo_data.py         # ★ v0.7 新增：演示数据注入脚本
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
│   │   ├── router/index.ts           # 路由配置（18 条路由）★
│   │   ├── stores/app.ts             # Pinia 状态管理
│   │   ├── api/                      # 14 个 API 模块
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
│   │   │   ├── forecast.ts           # 时序预测
│   │   │   └── covariate.ts         # ★ v0.6 新增：协变量 API
│   │   ├── types/index.ts            # TypeScript 类型定义（含 v0.6 新增类型）★
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
│   │   └── views/                    # 17 个页面
│   │       ├── Login.vue             # 登录
│   │       ├── Dashboard.vue         # 仪表盘
│   │       ├── ModelConfig.vue       # 模型配置
│   │       ├── Search.vue            # 搜索
│   │       ├── QA.vue                # 智能问答
│   │       ├── QAHistory.vue         # 问答历史
│   │       ├── TokenStats.vue        # Token 统计
│   │       ├── CallLogs.vue          # 调用日志
│   │       ├── Trends.vue            # 趋势分析 ★
│   │       ├── knowledge/{List,Detail,Edit,Upload}.vue  # 含状态管理 ★
│   │       ├── skill/{List,Edit}.vue
│   │       └── dataset/
│   │           ├── List.vue          # 数据集列表
│   │           └── Covariates.vue    # ★ v0.6 新增：协变量管理
│   ├── tests/                        # 单元测试
│   └── package.json
├── docs/                             # 文档目录
│   ├── DESIGN.md                     # 本设计书
│   ├── USER_GUIDE.md                 # ★ v0.7 新增：用户使用说明书
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
            ┌───────────┼───────────┐
            │1          │1          │
   ┌────────*─────┐  ┌──*──────────┐
   │ Document     │  │KnowledgeStatusLog│ ★ v0.6
   │ (上传文档)    │  │ (状态审计日志)    │
   └─────────────┘  └─────────────────┘

┌───────────┐     ┌──────────────┐     ┌───────────┐
│ Skill       │1---*│ QAHistory     │1---*│ TokenUsage  │
│ (技能路由)  │     │ (问答历史)    │     │ (Token消耗) │
└─────┬─────┘     └──────────────┘     └───────────┘
      │1
┌─────*──────┐
│SkillOption  │
│(分类/功能)   │
└────────────┘

┌───────────┐     ┌──────────────┐     ┌──────────────┐
│ModelConfig  │     │  Dataset      │1---*│ ForecastTask │
│(模型配置)   │     │ (时序数据集)  │     │ (预测任务)    │
└─────┬─────┘     └──────┬───────┘     └──────┬──────┘
      │                  │1                    │1
      │          ┌───────*────────┐     ┌────*──────┐
      └──────────┤ DatasetCovariate│     │ForecastResult│
                 │ (协变量) ★ v0.6 │     │ (预测结果)    │
                 └────────────────┘     └─────────────┘

┌──────────────┐
│SearchHistory  │  (独立表)
│(搜索历史)      │
└──────────────┘
```

### 5.2 模型清单（15 个，v0.6 新增 2 个）

| # | 模型 | 表名 | 说明 | 版本 |
|---|------|------|------|------|
| 1 | Category | categories | 分类，自引用树形结构 | |
| 2 | Tag | tags | 标签，含颜色 | |
| 3 | Knowledge | knowledge | 知识条目，**含 status 字段** | v0.6 增强 |
| 4 | KnowledgeTag | knowledge_tag_relation | 知识-标签多对多关联 | |
| 5 | KnowledgeStatusLog | knowledge_status_log | **知识状态变更审计日志** | ★ v0.6 新增 |
| 6 | Document | documents | 上传文件记录 | |
| 7 | Skill | skills | Skill 路由配置 | |
| 8 | SkillOption | skill_options | Skill 分类/功能选项 | |
| 9 | ModelConfig | model_configs | 模型配置（LLM/Embedding/Forecast） | |
| 10 | QAHistory | qa_history | 问答历史 | |
| 11 | TokenUsage | token_usage | Token 消耗记录 | |
| 12 | SearchHistory | search_history | 搜索历史 | |
| 13 | Dataset | datasets | 时序数据集 | |
| 14 | ForecastTask + ForecastResult | forecast_tasks / forecast_results | 预测任务和结果 | |
| 15 | DatasetCovariate | dataset_covariates | **数据集协变量（外生变量）** | ★ v0.6 新增 |

### 5.3 关键字段说明

#### Knowledge（v0.6 增强状态字段）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 主键 |
| title | String(200) | 标题 |
| content | Text | 内容（Markdown） |
| content_type | String(50) | 内容格式 |
| category_id | Integer FK | 分类 |
| source_type | String(20) | 来源 |
| **status** | String(20) | **状态：draft/published/archived（v0.6 新增，默认 published）** |
| created_at / updated_at | String | 时间戳 |

#### DatasetCovariate（★ v0.6 新增）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 主键 |
| dataset_id | Integer FK | 关联数据集 |
| name | String(100) | 协变量名称（如"节假日"） |
| code | String(50) | 英文标识（如 `is_holiday`），用作 exog 列名 |
| type | String(20) | 类型：continuous / binary / categorical |
| source_type | String(20) | 来源：manual / auto / template |
| values_json | Text | JSON 格式值 `[{"time":"2024-01","value":1}]` |
| description | String(500) | 备注说明 |
| created_at / updated_at | String | 时间戳 |

#### KnowledgeStatusLog（★ v0.6 新增）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 主键 |
| knowledge_id | Integer FK | 知识 ID |
| knowledge_title | String(500) | 标题快照 |
| old_status | String(20) | 旧状态 |
| new_status | String(20) | 新状态 |
| operator | String(100) | 操作人（默认 system） |
| reason | Text | 变更原因（可选） |
| created_at | String | 变更时间 |

#### ModelConfig（模型配置）

| 字段 | 类型 | 说明 |
|------|------|------|
| type | String(20) | 模型类型：LLM / Embedding / Forecast / Rerank / **OCR / VLM（v0.8 新增）** |
| api_url | String(500) | API 地址 |
| api_key | String(500) | API Key（Fernet 加密存储） |
| is_active | Boolean | 是否启用（同类型仅一个） |
| input_price / output_price | Float | Token 单价（元/千 token） |

#### Skill（技能路由）

| 字段 | 类型 | 说明 |
|------|------|------|
| trigger_keywords | Text (JSON) | 触发关键词列表 |
| trigger_patterns | Text (JSON) | 触发正则表达式列表 |
| prompt_template | Text | Prompt 模板（含 {context} {question}） |
| knowledge_scope | Text (JSON) | 知识范围 `{"category_ids":[],"tag_ids":[]}` |
| is_default | Boolean | 是否默认兜底 Skill |

---

## 6. 后端设计

### 6.1 API 路由总览（14 个模块，75+ 端点）

| 模块 | 前缀 | 核心端点 | 版本变化 |
|------|------|---------|---------|
| 认证 | /api/auth | login / me / status | |
| 知识管理 | /api/knowledge | CRUD + upload + batch + rebuild-indexes + download + **status-logs** | ★ v0.6 新增 status-logs |
| 分类管理 | /api/categories | 树形 CRUD | |
| 标签管理 | /api/tags | CRUD | |
| Skill 管理 | /api/skills | CRUD + templates + test-route | |
| Skill 选项 | /api/skill-options | CRUD | |
| 模型配置 | /api/models | CRUD + activate + test + status（含 OCR/VLM ★v0.8） | ★ v0.8 status 返回 ocr/vlm |
| 搜索 | /api/search | semantic + keyword + history | |
| 智能问答 | /api/qa | ask(SSE) + feedback + suggestions + history | |
| 仪表盘 | /api/dashboard | stats + recent-qa | |
| Token 统计 | /api/token-stats | summary + call-logs + model-call-logs | |
| 数据集 | /api/datasets | CRUD + import + export + preview + template | |
| 时序预测 | /api/forecast | predict + tasks + results + cross-validation + compare-models + **statistical-forecast（含协变量）** + decomposition + export | ★ v0.6 协变量支持 |
| **协变量管理** | /api/datasets/{id}/covariates + /api/covariates/{id} | list + create + update + delete + **auto-generate** + preview + future-times | ★ v0.6 新增 |

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

OCRClient ★ v0.8 新增
├── __init__(config)              # 自动选择后端：VLM 类型→VLMBackend；model_name 含 deepseek-ocr→DeepSeekOCRBackend；
│                                 # model_name 含 vl/vision/vlm→VLMBackend；默认→DeepSeekOCRBackend
├── backend: PDFParserBackend     # 持有的具体后端实例
└── parse(file_path) → ParseResult  # 解析 PDF 返回结构化结果

ModelManager (单例)
├── _cache: {type: client}        # 内存缓存
├── get_active_llm()              # 获取启用的 LLM
├── get_active_embedding()        # 获取启用的 Embedding（未配置抛错让调用方降级）
├── get_active_forecast()         # 获取启用的 Forecast
├── get_active_rerank()           # 获取启用的 Rerank（未配置返回 None 跳过 rerank）
├── get_active_ocr() ★v0.8        # 获取启用的 OCR/VLM 客户端（OCR 优先，回退 VLM，未配置返回 None）
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
  ├─ BM25 检索：_bm25_search(db, question, scope)  # 真 Okapi BM25（v0.8 升级）
  │   ├─ ensure_bm25_index(db)  # 按需构建（首次查询触发）
  │   ├─ 通过 SQL 取 allowed_doc_ids（status=published + scope 过滤）
  │   └─ bm25_index.search(question, top_k, allowed_doc_ids)
  │
  ├─ 合并：knowledge_id → best chunk
  │
  └─ RRF 融合：score(d) = Σ 1/(k + rank_i(d))   # k=60
```

**降级策略**：无 Embedding 模型时 `degraded=True`，仅走 BM25 关键词检索。

**v0.6 优化**：RAG 检索仅匹配 `status=published` 的知识（非 published 状态的知识不参与检索）。

**v0.8 优化**：BM25 由原 SQLite LIKE 简单打分升级为真 Okapi BM25 算法（IDF 加权 + 词频饱和 k1=1.5 + 文档长度归一化 b=0.75），内存倒排索引 + 增量更新；检索结果 metadata 增加 `chunk_id` 和 `page_number` 用于引用溯源。

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

#### 6.2.5 文件解析与文本分块

- **支持格式**：PDF / DOCX / XLSX / MD / TXT / HTML
- **多编码兼容**：utf-8 / utf-8-sig / gbk / gb18030 / latin-1
- **安全措施**：文件名清理防路径穿越、流式分片写入（1MB chunk）防 OOM、大小限制 50MB
- **PDF 解析后端（v0.8 新增）**：`pdf_parser_backend.get_pdf_backend()` 按 `PDF_PARSER_BACKEND` 配置选择后端
  - 优先级：环境变量 > 数据库 OCR 模型配置（auto 模式）> PyPDF2 兜底
  - DeepSeek-OCR：PDF 原生 base64 输入，返回结构化 Markdown
  - VLM：PyMuPDF 按页转图后调用 vision API，输出带 `<!-- page N -->` 页码标记
  - 失败/空内容自动回退 PyPDF2
- **文本分块（v0.8 升级）**：段落感知（按空行分段）+ 滑动窗口 overlap + 句子边界优先切分（。！？.!?）+ 页码标记保护 + 标题路径前缀，默认 `chunk_size=500, overlap=50`（参数安全限制：chunk_size ∈ [100, 2000]，overlap ≤ chunk_size/2）

---

## 7. 前端设计

### 7.1 路由配置（18 条路由，v0.6 新增协变量管理）

| 路径 | 页面 | 说明 | 版本 |
|------|------|------|------|
| /login | Login | 登录页 | |
| /dashboard | Dashboard | 仪表盘 | |
| /knowledge | KnowledgeList | 知识列表（含状态筛选） | v0.6 |
| /knowledge/upload | KnowledgeUpload | 批量上传 | |
| /knowledge/edit/:id? | KnowledgeEdit | 编辑知识（含状态选择） | v0.6 |
| /knowledge/detail/:id | KnowledgeDetail | 知识详情 | |
| /search | Search | 搜索 | |
| /qa | QA | 智能问答（SSE 流式） | |
| /qa/history | QAHistory | 问答历史 | |
| /skills | SkillList | Skill 管理 | |
| /skills/edit/:id? | SkillEdit | 编辑 Skill | |
| /models | ModelConfig | 模型配置 | |
| /token-stats | TokenStats | Token 统计 | |
| /call-logs | CallLogs | 调用日志 | |
| /datasets | DatasetList | 数据集管理 | |
| /datasets/:id/covariates | Covariates | **协变量管理** | ★ v0.6 新增 |
| /trends | Trends | 趋势分析 | |

**认证守卫**：首次访问动态探测后端是否启用认证，启用时无 token 重定向到 `/login?redirect=原路径`。

### 7.2 通用组件

| 组件 | 功能 |
|------|------|
| AiChatButton | 右下角浮动智能问答，流式接收、Markdown 渲染、可中断 |
| CategoryTree | 分类树展示，节点显示知识数量徽标，支持 CRUD |
| FileUpload | 拖拽上传，文件队列表格，大小格式化 |
| MarkdownEditor | 分屏编辑器（编辑 + 预览），工具栏 |
| MarkdownView | Markdown 只读渲染 |
| SkillOptionManager | Skill 分类/功能选项管理弹窗 |
| TagSelect | 标签多选 + 搜索 + 新建（带颜色面板） |

### 7.3 请求封装（request.ts）

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
  │    ├─ 4a. 混合检索（仅 status=published 的知识）★ v0.6
  │    │    _hybrid_search(q_vec, question, skill, db)
  │    │    ├─ 向量检索：ChromaDB 余弦检索 top_k=5
  │    │    ├─ BM25 检索：真 Okapi BM25（v0.8 升级，内存倒排索引）
  │    │    └─ RRF 融合：score = Σ 1/(60 + rank)
  │    │    返回结果 metadata 含 chunk_id + page_number（v0.8 引用溯源）
  │    │
  │    ├─ 4b. Prompt 组装（Token 预算控制 MAX_CONTEXT_TOKENS=4000）
  │    │
  │    └─ 4c. LLM 生成 → {content, tokens, model}
  │
  ├─ 5. 保存历史 + 记录 TokenUsage + 写入缓存
```

### 8.2 知识状态变更流程（★ v0.6 新增）

```
用户将知识从 published 改为 archived
  │
  ▼
knowledge_service.update(db, id, data={status: "archived"})
  │
  ├─ 1. 读取旧状态 old_status = knowledge.status  # "published"
  ├─ 2. 更新 status = "archived"
  ├─ 3. 记录审计日志
  │    _log_status_change(db, knowledge, "published", "archived", operator, reason)
  │    → KnowledgeStatusLog(knowledge_id, title, old, new, operator, reason)
  ├─ 4. 向量索引联动
  │    published→archived: remove_vector_index(knowledge_id)  # 同时移除 BM25 索引（v0.8）
  │    其他→published: sync_vector_index(db, knowledge_id)    # 同时添加/更新 BM25 索引（v0.8）
  └─ 5. 清除答案缓存
       answer_cache.clear()
```

### 8.3 状态与索引联动规则

| 状态转换 | 向量索引动作 | 说明 |
|---------|------------|------|
| → published | 创建/重建索引 | 知识可被 RAG 检索 |
| published → draft | 移除索引 | 知识不再被检索 |
| published → archived | 移除索引 | 归档知识不再被检索 |
| draft → archived | 无动作 | 本来就没有索引 |
| draft → published | 创建索引 | 发布草稿 |
| archived → published | 创建索引 | 重新发布归档知识 |

---

## 9. 时序预测模块

### 9.1 架构

```
┌──────────────────────────────────────────────────────────┐
│                forecast_service.py                        │
│                                                            │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐  │
│  │ 数据预处理 │  │ 预测执行  │  │ 评估与分析              │  │
│  │ 缺失值插值 │  │          │  │ 回测误差 MAE/MAPE      │  │
│  │ IQR异常截断│  │ Chronos  │  │ 扩展指标 MASE         │  │
│  │          │  │ TimesFM  │  │ LLM 分析报告           │  │
│  │          │  │ ARIMA★   │  │ STL 季节性分解         │  │
│  │          │  │ ETS      │  │ 交叉验证               │  │
│  │          │  │ Theta    │  │ 多模型对比             │  │
│  │          │  │ Prophet★ │  │                        │  │
│  └──────────┘  └──────────┘  └────────────────────────┘  │
│                                                            │
│  ★ = v0.6 支持协变量（exog）                                │
└──────────────────────────────────────────────────────────┘
```

### 9.2 预测模式

| 模式 | 说明 |
|------|------|
| 预测未来 | 从历史末尾预测未来 horizon 步 |
| 回测对照 | 从 start_index 拆分，训练集预测，与 actuals 对比计算误差 |
| 滑动窗口 | 仅使用最后 train_window 个点训练 |
| 交叉验证 | expanding / sliding 策略多次回测取平均 |
| 多模型对比 | 临时切换激活模型执行回测，按 MAE 最低找出最优 |

### 9.3 模型类型与协变量支持（★ v0.6）

| 类型 | 模型 | 协变量支持 | 说明 |
|------|------|-----------|------|
| 深度学习 | Chronos-2 / TimesFM 2.5 | ❌（接口已预留） | 调用 Forecast 推理服务 HTTP /predict |
| 统计模型 | ARIMA | ✅ | exog_train + exog_future 参数 |
| 统计模型 | Prophet | ✅ | add_regressor + 中国节假日 |
| 统计模型 | ETS | ❌ | 不支持 exog |
| 统计模型 | Theta | ❌ | 不支持 exog |

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

---

## 10. 协变量系统（v0.6 新增）

### 10.1 概述

协变量（Covariate / Exogenous Variable）是时序预测中的外生变量，用于增强统计模型（ARIMA / Prophet）的预测能力。例如：节假日、工作日、温度、促销活动等。

### 10.2 协变量类型

| 类型 | 说明 | 示例 |
|------|------|------|
| continuous | 连续型 | 温度、价格、湿度 |
| binary | 二元型 | 是否节假日、是否促销 |
| categorical | 分类型 | 季节（需用户编码为数值） |

### 10.3 自动生成协变量

系统根据数据集频率自动生成常用协变量：

| 频率 | 自动生成的协变量 |
|------|-----------------|
| 所有频率 | `trend`（线性趋势 t=1,2,3...） |
| daily/weekly/monthly | `is_holiday`（中国法定节假日，1=节假日） |
| daily/hourly | `is_weekend`（周六/周日 = 1） |
| monthly | `month_sin` + `month_cos`（周期编码 2π·month/12） |
| daily | `dow_sin` + `dow_cos`（周期编码 2π·weekday/7） |
| quarterly | `quarter_sin` + `quarter_cos`（周期编码 2π·quarter/4） |

**节假日数据**：内置 [china_holidays.json](file:///d:/AI/Trae/LLM%20Wiki/backend/app/data/china_holidays.json)，覆盖 2024-2026 年中国法定节假日。

### 10.4 协变量接入预测管道

```
run_statistical_forecast(db, dataset_id, horizon, model_type, use_covariates=True)
  │
  ├─ use_covariates=True && model_type in ("arima", "prophet")
  │
  ├─ build_exog_matrix(db, dataset_id, train_times, future_times)
  │   │
  │   ├─ 查询数据集所有协变量（按 id 升序）
  │   ├─ 提取 code 作为 feature_names
  │   ├─ 对每个协变量调用 align_covariate(main_times, cov_values)
  │   │   │
  │   │   ├─ 精确匹配：time 字段完全相等
  │   │   ├─ 日期前缀匹配：YYYY-MM 前缀（用于 monthly→daily 对齐）
  │   │   └─ 缺失填 0.0
  │   │
  │   └─ 返回 (X_train, X_future, feature_names)
  │
  ├─ ARIMA：ARIMA(train, order, exog=X_train).forecast(horizon, exog=X_future)
  │
  └─ Prophet：m.add_regressor("reg_" + name) × N → 预测
```

### 10.5 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/datasets/{id}/covariates | 列出协变量 |
| POST | /api/datasets/{id}/covariates | 新增协变量 |
| PUT | /api/covariates/{id} | 修改协变量 |
| DELETE | /api/covariates/{id} | 删除协变量 |
| POST | /api/datasets/{id}/covariates/auto-generate | 自动生成协变量 |
| GET | /api/datasets/{id}/covariates/preview | 预览对齐矩阵 |
| GET | /api/datasets/{id}/covariates/future-times | 生成未来时间标签 |

---

## 11. 知识状态生命周期（v0.6 新增）

### 11.1 三种状态

| 状态 | 说明 | 向量索引 | RAG 检索 |
|------|------|---------|---------|
| draft | 草稿 | 无索引 | 不可检索 |
| published | 发布 | 有索引 | ✅ 可检索 |
| archived | 归档 | 无索引 | 不可检索 |

### 11.2 状态转换图

```
        create()
           │
           ▼
      ┌─────────┐  update(status="draft")    ┌─────────┐
      │published │ ───────────────────────→  │  draft  │
      │ (默认)   │ ←───────────────────────  │ (草稿)  │
      └────┬────┘  update(status="published") └─────────┘
           │
           │ update(status="archived")
           ▼
      ┌─────────┐  update(status="published") ┌─────────┐
      │archived │ ←─────────────────────────  │published│
      │ (归档)  │ ───────────────────────→    │ (重新发布)│
      └─────────┘                              └─────────┘
```

### 11.3 审计日志

每次状态变更自动记录 `KnowledgeStatusLog`：
- 记录 `old_status` → `new_status`
- 快照知识标题（防止后续修改导致追溯困难）
- 记录操作人（`operator`）和变更原因（`reason`）
- 失败不阻断主流程（try/except 包裹）

查询端点：`GET /api/knowledge/{id}/status-logs?page=1&page_size=20`

### 11.4 索引联动规则

| 操作 | 索引动作 | 缓存动作 |
|------|---------|---------|
| 创建 published 知识 | 创建索引 | — |
| 创建 draft/archived 知识 | 无索引 | — |
| published → draft/archived | 移除索引 | 清除答案缓存 |
| draft/archived → published | 创建索引 | 清除答案缓存 |
| 更新 published 知识内容 | 重建索引 | 清除答案缓存 |
| 删除知识 | 移除索引 | 清除答案缓存 |
| 批量状态变更 | 逐条联动 | 清除答案缓存 |

---

## 12. 安全设计

### 12.1 认证与授权

| 机制 | 说明 |
|------|------|
| JWT 认证 | HS256 算法，`JWT_EXPIRE_HOURS` 控制（默认 24h） |
| 可选认证 | `AUTH_ENABLED` 环境变量控制，开发环境默认关闭 |
| 生产强制 | `DEBUG=false` 时强制校验 AUTH_ENABLED=true |
| 路由保护 | 所有业务路由 `Depends(require_auth)` |

### 12.2 数据安全

| 机制 | 说明 |
|------|------|
| API Key 加密 | Fernet 对称加密（PBKDF2HMAC 派生密钥，100000 次迭代） |
| API Key 脱敏 | 输出时 `前4+***+后4` |
| 文件名清理 | 去除路径分隔符、Windows 保留字符、控制字符 |
| HTML 净化 | DOMPurify 白名单（仅允许安全标签和属性） |
| Markdown 安全 | `html: false` 禁止原生 HTML 渲染 |

### 12.3 生产环境安全校验

启动时 `validate_security_config()` 在 `DEBUG=false` 时强制检查：

- `SECRET_KEY` 不能为默认值
- `ADMIN_PASSWORD` 不能为 `changeme`
- `CORS_ORIGINS` 不能为 `*`
- `AUTH_ENABLED` 必须为 `true`

---

## 13. 配置与部署

### 13.1 环境变量

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
| PDF_PARSER_BACKEND | auto | PDF 解析后端：pypdf2/deepseek-ocr/vlm/auto ★v0.8 |
| DEEPSEEK_OCR_API_KEY | （空） | DeepSeek-OCR API Key ★v0.8 |
| DEEPSEEK_OCR_BASE_URL | https://api.siliconflow.cn/v1 | DeepSeek-OCR 地址 ★v0.8 |
| DEEPSEEK_OCR_MODEL | deepseek-ai/DeepSeek-OCR | DeepSeek-OCR 模型名 ★v0.8 |
| VLM_API_KEY | （空） | VLM 视觉解析 API Key ★v0.8 |
| VLM_BASE_URL | https://api.siliconflow.cn/v1 | VLM 地址 ★v0.8 |
| VLM_MODEL | Qwen/Qwen3-VL-32B-Instruct | VLM 模型名 ★v0.8 |

### 13.2 自动迁移机制

`_auto_migrate()` 基于 SQLite `ALTER TABLE ADD COLUMN`：
- 查询现有列（`PRAGMA table_info`）
- 仅添加不存在的列
- v0.6 新增迁移：`knowledge.status VARCHAR(20) DEFAULT 'published'`
- 全新表（dataset_covariates、knowledge_status_log）由 `create_all` 直接创建

### 13.3 预制数据

系统首次启动自动创建：
- 4 个分类（制造运营/仓储物流/质量管理/设备管理）
- 6 个标签（故障代码/保养/工艺/质量标准/仓储管理/操作经验）
- 5 个预制 Skill（故障诊断/保养维护/工艺指导/质量检验/通用问答[默认]）
- 10 个 Skill 分类/功能选项
- 2 个 Forecast 模型配置（Chronos-2 / TimesFM 2.5）
- **3 个辅助模型配置（v0.8 新增）**：bge-reranker-v2-m3（Rerank）、DeepSeek-OCR（OCR）、Qwen3-VL-32B（VLM），用户填 API Key 即可激活
- 2 个示例时序数据集
- **5 个示例知识条目（v0.7 新增）**：分别匹配各 Skill 的 `knowledge_scope`，用于演示 Skill 路由三级匹配与 RAG 检索范围限定

**示例知识条目与 Skill 对应关系（v0.7）**：

| 知识标题 | 分类 | 标签 | 命中 Skill |
|---------|------|------|-----------|
| CNC加工中心E01报警故障诊断与处理指南 | 设备管理 | 故障代码 | 故障诊断 |
| 设备定期保养维护规程与周期表 | 设备管理 | 保养 | 保养维护 |
| 数控加工工艺参数规范与操作要点 | 制造运营 | 工艺 | 工艺指导 |
| 产品质量检验标准与不合格品判定规则 | 质量管理 | 质量标准 | 质量检验 |
| MOM系统操作常见问题FAQ | （无分类） | 操作经验 | 通用问答 |

**重复执行保护**：`seed_service.seed_initial_data()` 通过 `exists()` 检查避免重复创建；`seed_demo_data.py` 通过 `title` 去重，可重复执行注入。

### 13.4 启动

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

# 演示数据注入（v0.7 新增，可选，可重复执行）
cd backend
python scripts/seed_demo_data.py   # 注入 5 条匹配各 Skill 的示例知识
```

> 首次启动后端时已通过 `seed_service.seed_initial_data()` 自动注入全部预制数据（含 5 条示例知识），`seed_demo_data.py` 仅在老库升级或需补齐示例知识时使用。

---

## 14. 版本演进

| 版本 | 日期 | 核心内容 |
|------|------|---------|
| v0.1 | 2026-07-07 | 初始版本：知识库 + 智能问答 + Skill 路由 + RAG + 模型配置 + Token 统计 |
| v0.2 | 2026-07-08 | 新增 Forecast 时序预测模型支持（Chronos-2 / TimesFM） |
| v0.3 | 2026-07-09 | 新增 TimesFM 推理服务及 Chronos-Large 部署文档 |
| v0.4 | 2026-07-10 | 增加时序分析功能（数据集管理 + 预测任务 + 趋势可视化） |
| v0.5 | 2026-07-12 | 优化一系列问题，增强一系列功能（认证系统、混合检索 RRF、多模型对比、交叉验证、STL 分解、调用日志等） |
| **v0.6** | 2026-07-12 | **强化 AI 知识库功能，强化趋势预测：新增协变量系统（外生变量）、知识状态生命周期管理（draft/published/archived + 审计日志）、ARIMA/Prophet 协变量接入、中国节假日数据集** |
| **v0.7** | 2026-07-13 | **小批量修复：新增用户使用说明书（USER_GUIDE.md）、演示数据注入脚本（seed_demo_data.py）、seed_service 预制 5 条示例知识、Trends/Covariates/dataset/List/CategoryTree 页面 bug 修复、设计书同步更新至 v0.7** |
| **v0.8** | 2026-07-14 | **增加 OCR/VLM 模型支持 + 性能优化：新增 PDF 解析后端抽象层（PyPDF2/DeepSeek-OCR/VLM 三后端 + 兜底降级）、OCRClient 客户端与 get_active_ocr、真 Okapi BM25 算法（bm25_service 内存倒排索引）、text_chunker 段落感知+句子边界+滑动窗口升级、引用溯源（chunk_id + page_number 写入向量库 metadata，前端展示页码徽章）、预制 3 个辅助模型配置（Rerank/OCR/VLM）、OCR/VLM 连通测试（2xx 和 400/422 均算成功）** |

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
| 协变量未来值缺失 | align_covariate 填 0.0 |
| 无 OCR/VLM 模型 | PDF 解析回退 PyPDF2 文本层抽取（v0.8） |
| OCR/VLM 解析失败或返回空 | 自动回退 PyPDF2 兜底（v0.8） |
| PyMuPDF 未安装 | VLM 后端回退 PyPDF2（v0.8） |

### D. v0.6 新增功能汇总

| 功能 | 说明 |
|------|------|
| 协变量管理 | 完整 CRUD + 自动生成 + 对齐矩阵预览 + 未来时间标签生成 |
| 协变量类型 | continuous / binary / categorical 三种类型 |
| 自动生成协变量 | trend / is_holiday / is_weekend / 月份周期 / 周期编码 |
| 中国节假日 | 2024-2026 年法定节假日数据集 |
| ARIMA 协变量 | exog_train + exog_future 参数支持 |
| Prophet 协变量 | add_regressor + 内置中国节假日 |
| 知识状态 | draft / published / archived 三态生命周期 |
| 状态审计日志 | KnowledgeStatusLog 记录每次状态变更 |
| 索引联动 | 状态变更自动同步/移除向量索引 |
| 缓存联动 | 状态变更自动清除答案缓存 |
| RAG 过滤 | 仅检索 published 状态的知识 |

---

## 15. 用户文档与演示数据（v0.7 新增）

### 15.1 概述

v0.7 围绕「**让最终用户开箱即用**」目标，新增完整用户使用说明书、可重复执行的演示数据注入脚本，并将 seed_service 升级为自动注入 5 条匹配各 Skill `knowledge_scope` 的示例知识条目，使「Skill 路由 + RAG 检索范围限定」机制可在首次启动后立即被验证。

### 15.2 文档体系

| 文档 | 路径 | 受众 | 用途 |
|------|------|------|------|
| 设计书 | [docs/DESIGN.md](file:///d:/AI/Trae/LLM%20Wiki/docs/DESIGN.md) | 开发者/架构师 | 架构、数据模型、流程、API 设计 |
| 使用说明书 | [docs/USER_GUIDE.md](file:///d:/AI/Trae/LLM%20Wiki/docs/USER_GUIDE.md) | 最终用户 | 10 大功能模块逐一操作指南 + 实例问题对照 |
| Chronos 部署 | docs/chronos-deploy.md | 运维 | Chronos-T5-Small 推理服务部署 |
| Chronos-Large 部署 | docs/chronos-large-deploy.md | 运维 | 高精度预测服务部署 |
| TimesFM 部署 | docs/timesfm-deploy.md | 运维 | TimesFM 2.5 推理服务部署 |

### 15.3 USER_GUIDE.md 结构（10 章）

| 章 | 标题 | 内容 |
|----|------|------|
| 1 | 系统概览与快速开始 | 四大能力 + 启动流程 |
| 2 | 实例数据索引（开箱即用） | 数据集/协变量/知识/Skill/模型配置清单 |
| 3 | 仪表盘 | 卡片与图表说明 |
| 4 | 数据集管理 | 数据集 CRUD + 协变量管理（重点） |
| 5 | 趋势分析（每个按钮的使用） | 7 类预测按钮 + 5 个高级分析抽屉 + STL 分解 |
| 6 | 智能问答与 Skill 路由（重点） | 三级匹配机制 + knowledge_scope + 实例问题对照 |
| 7 | 知识管理 | 列表/创建/状态生命周期/文件上传 |
| 8 | Skill 管理 | 关键字段 + Prompt 模板 + knowledge_scope 配置 + 测试路由 |
| 9 | 模型配置 | LLM/Embedding/Forecast 配置流程 |
| 10 | 其他功能 | 问答历史、Token 统计、调用日志 |

**关键设计**：第 6 章提供了「实例问题对照表」，5 条示例问题可直接复制到智能问答页测试，验证 Skill 路由命中类型与检索到的知识。

### 15.4 seed_demo_data.py 设计

**职责**：向**运行中**的系统注入 5 条示例知识（不重建数据库），用于老库升级或补齐示例数据。

**实现要点**：

| 设计点 | 实现 |
|--------|------|
| 通信方式 | `urllib.request` 直连 HTTP API（不依赖 requests、不依赖 app 模块） |
| 默认目标 | `http://localhost:8001/api`（与后端默认端口一致） |
| 去重策略 | 查询已有知识 `title`，命中则 skip |
| 知识状态 | 注入时 `status="published"`，立即可被 RAG 检索 |
| 重复执行 | 幂等：相同 title 不会重复创建 |
| 内容格式 | `content_type="markdown"`，匹配 USER_GUIDE 第 6 章对照表 |

**与 seed_service.seed_initial_data() 的关系**：

| 维度 | seed_service | seed_demo_data.py |
|------|--------------|-------------------|
| 调用时机 | 后端启动自动调用 | 用户手动执行 |
| 范围 | 全部预制数据（分类/标签/Skill/模型/数据集/知识） | 仅 5 条示例知识 |
| 依赖 | app 模块、SQLAlchemy | 仅 HTTP API |
| 幂等 | `exists()` 检查 | `title` 去重 |
| 适用场景 | 全新部署 | 老库升级 / 演示补齐 |

### 15.5 v0.7 页面 Bug 修复清单

| 文件 | 修复内容 |
|------|---------|
| frontend/src/components/CategoryTree.vue | 分类树节点交互异常修复 |
| frontend/src/views/Trends.vue | 趋势分析图表渲染 / 预测结果展示修复 |
| frontend/src/views/dataset/Covariates.vue | 协变量值编辑器 / 对齐矩阵预览修复 |
| frontend/src/views/dataset/List.vue | 数据集列表显示修复 |

### 15.6 版本配套更新约定

自 v0.7 起，每次发版配套更新以下文件：

| 文件 | 更新内容 |
|------|---------|
| README.md | 版本徽章、版本历史表、技术栈统计、功能模块表 |
| docs/DESIGN.md | 版本演进表、新增功能章节、目录结构、预制数据 |
| docs/USER_GUIDE.md | 新增功能操作说明（如涉及用户操作） |
| 其他必要文件 | 根据发版内容同步（如新增部署文档、新增脚本说明） |

---

## 16. OCR/VLM 深度文档解析（v0.8 新增）

### 16.1 设计动机

PyPDF2 仅能抽取 PDF 文本层，对扫描件、图片型 PDF、含复杂表格/公式的文档无能为力，导致 RAG 检索质量受限。v0.8 参照 RAGFlow DeepDOC 能力，以零部署成本补齐 PDF 解析短板：通过外部 OCR/VLM API 实现深度文档理解，PyPDF2 作为兜底。

### 16.2 后端抽象层（pdf_parser_backend.py）

```
PDFParserBackend (ABC)
├── parse(file_path) → ParseResult   # 统一接口
│
├── PyPDF2Backend            # 兜底：PyPDF2 文本层抽取，零依赖
│
├── DeepSeekOCRBackend ★v0.8 # 硅基流动 DeepSeek-OCR
│   ├── PDF 原生 base64 输入（无需先转图片）
│   ├── 返回结构化 Markdown（含表格、标题层级）
│   ├── 输出空时回退 PyPDF2
│   └── 20MB 安全上限警告
│
└── VLMBackend ★v0.8         # 多模态 LLM 视觉解析
    ├── PyMuPDF (fitz) 按页转 PNG（默认 dpi=150）
    ├── 每页调用 vision API（OpenAI 兼容 chat/completions）
    ├── 输出带 <!-- page N --> 页码标记（供引用溯源）
    ├── max_pages=30 限制
    └── 单页失败用 PyPDF2 兜底该页
```

**ParseResult 数据结构**：`text`（Markdown）、`pages`、`tables`、`images`、`backend`（后端名）、`page_count`。

### 16.3 后端选择策略（get_pdf_backend）

优先级：
1. 环境变量 `PDF_PARSER_BACKEND` 指定（`pypdf2`/`deepseek-ocr`/`vlm`）
2. `auto` 模式：查数据库 `ModelManager.get_active_ocr()`（OCR 类型优先，回退 VLM 类型）
3. 默认 PyPDF2

### 16.4 OCRClient 客户端（llm_client.py）

```
OCRClient(config)
├── 解析 config.api_url：自动剥离 /chat/completions 等后缀
├── 解密 api_key
└── 后端选择：
    ├─ config.type == "VLM" → VLMBackend
    ├─ model_name 含 "deepseek-ocr" → DeepSeekOCRBackend
    ├─ model_name 含 "vl"/"vision"/"vlm"/"gpt-4o" → VLMBackend
    └─ 默认 → DeepSeekOCRBackend
```

### 16.5 连通测试（model_service.test_connection）

OCR/VLM 是 vision 模型，纯文本 ping 通常返回 400/422（要求 image_url 输入）。测试逻辑：
- **2xx**：API 可达且认证通过 → 成功
- **400/422**：API 可达，输入格式不对（vision 模型需要图片/PDF）→ 算成功（提示「需 PDF/图片输入」）
- **401/403**：认证失败 → 失败
- **404**：端点错误 → 失败
- **5xx**：服务异常 → 失败

### 16.6 解析流程与索引联动

```
知识上传 PDF
  │
  ▼
file_parser._parse_pdf(file_path)
  │
  ├─ get_pdf_backend() 选择后端
  ├─ backend.parse(file_path) → ParseResult
  ├─ 空内容或异常 → 回退 PyPDF2Backend
  └─ 返回 Markdown 文本
  │
  ▼
text_chunker.chunk(text)  # 段落感知 + 句子边界 + 滑动窗口
  │   # VLM 输出的 <!-- page N --> 标记保留在 chunk 开头
  ▼
sync_vector_index(db, knowledge_id)
  ├─ 向量化 chunks
  ├─ metadata 增加 chunk_id="{kid}_{i}" 和 page_number（从 <!-- page N --> 提取）★v0.8
  ├─ 写入 ChromaDB
  └─ bm25_index.add_document(kid, title, content)  # 同步 BM25 索引 ★v0.8
```

### 16.7 引用溯源

| 层 | 实现 |
|----|------|
| 向量库 metadata | `chunk_id`（如 "12_3"）、`page_number`（从 VLM 页码标记提取） |
| RAG sources | `rag_service` 组装 sources 时透传 `chunk_id` + `page_number` |
| 前端展示 | `QA.vue` 来源卡片显示紫色「📄 第 N 页」徽章（page_number > 0 时） |

---

## 17. 性能优化（v0.8 新增）

### 17.1 真 Okapi BM25 算法（bm25_service.py）

**算法**：`score(D, Q) = Σ IDF(qi) × (f(qi, D) × (k1 + 1)) / (f(qi, D) + k1 × (1 - b + b × |D| / avgdl))`

| 参数 | 值 | 说明 |
|------|-----|------|
| k1 | 1.5 | 词频饱和参数 |
| b | 0.75 | 文档长度归一化参数 |
| IDF | `ln(1 + (N - n + 0.5) / (n + 0.5))` | 逆文档频率 |

**索引结构**（内存 + 线程安全 RLock）：
- `inverted_index: {token: {doc_id: term_frequency}}`
- `doc_lengths: {doc_id: document_length}`
- `doc_freq: {token: number_of_docs_containing_token}`
- `avgdl`：平均文档长度

**特性**：
- 标题权重 ×2（标题 token 重复两次，与原 LIKE 打分逻辑一致）
- jieba 中文分词 + 标点过滤
- 增量更新：知识增删改时通过 `add_document` / `remove_document` 同步
- 按需构建：首次查询时 `ensure_bm25_index(db)` 从数据库全量加载 published 知识
- 全局单例 `bm25_index`
- `rebuild_bm25_index(db)` 全量重建（切换 Embedding 模型时调用）

### 17.2 text_chunker 分块升级

| 维度 | 旧（v0.7 及之前） | 新（v0.8） |
|------|------------------|-----------|
| 段落感知 | 按单行 `\n` | 按空行 `\n\s*\n` 分段，保持语义完整 |
| 硬切策略 | 按固定步长 `chunk_size - overlap` | 优先在句子边界（。！？.!?）切分，找不到则找空格/逗号，最后才硬切 |
| overlap | 仅在累积超长时保留前块末尾 | 标题切换 + 段落累积 + 硬切均保留 overlap 上下文（滑动窗口） |
| 页码标记 | 无 | 保护 VLM 输出的 `<!-- page N -->` 标记在 chunk 开头 |
| 参数安全 | 无限制 | `chunk_size ∈ [100, 2000]`，`overlap ≤ chunk_size/2` |

### 17.3 索引联动优化

知识 `sync_vector_index` / `remove_vector_index` 现同时维护 ChromaDB 向量索引和 BM25 内存索引，保证两路检索数据一致。

### 17.4 前端引用溯源展示

`QA.vue` 来源卡片在 `page_number > 0` 时显示紫色徽章「📄 第 N 页」，帮助用户快速定位原文位置。

---

*本文档基于 v0.8 代码库实际架构生成。*
