# MOM 系统 AI 知识库平台

> Skill 路由 + 自实现轻量 RAG + 时序预测 架构的制造企业 AI 知识库平台

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/bue/Vue-3-42b883.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![Version](https://img.shields.io/badge/version-v0.8-brightgreen.svg)](https://github.com/Luerlei/MOM-AI-KBS/releases)

基于 FastAPI + Vue3 + ChromaDB 构建，平台模型无关（统一接口抽象层），整合 **AI 知识库 + 智能问答 + 时序预测分析** 三大能力，支持 LLM 智能问答、语义/关键词搜索、Skill 路由分发、协变量增强预测、OCR/VLM 深度文档解析、Token 统计优化等完整功能。

---

## 目录

- [核心特性](#核心特性)
- [版本历史](#版本历史)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [核心流程](#核心流程)
- [功能模块](#功能模块)
- [时序预测](#时序预测)
- [协变量系统](#协变量系统)
- [API 接口](#api-接口)
- [测试](#测试)
- [预制数据](#预制数据)
- [文档](#文档)
- [常见问题](#常见问题)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

---

## 核心特性

- **Skill 路由引擎**：关键词/正则/语义三级匹配，使用专属 Prompt 模板和知识范围
- **自实现轻量 RAG**：不依赖 LangChain/LlamaIndex，ChromaDB SDK + httpx，混合检索（向量 + 真 BM25）+ RRF 融合
- **模型无关架构**：统一 `LLMClient` 抽象层，支持 LLM / Embedding / Forecast / Rerank / OCR / VLM 六类模型
- **OCR/VLM 深度文档解析**：DeepSeek-OCR（PDF 直接输入）+ 多模态 VLM（按页转图），参照 RAGFlow DeepDOC 补齐 PDF 解析短板，PyPDF2 兜底
- **时序预测分析**：Chronos-2 / TimesFM 深度学习 + ARIMA/ETS/Theta/Prophet 统计模型 + STL 分解 + 交叉验证
- **协变量系统**：外生变量支持（节假日/工作日/趋势/周期编码），ARIMA/Prophet 接入
- **知识状态生命周期**：draft / published / archived 三态管理 + 审计日志 + 索引联动
- **引用溯源**：检索结果携带 `chunk_id` + `page_number`，前端展示来源页码徽章
- **优雅降级**：无 Embedding 时 RAG 降级为直接对话；OCR/VLM 失败自动回退 PyPDF2；语义搜索失败切换关键词搜索
- **运行时热更新**：模型配置存储于数据库，Web 界面修改后立即生效
- **Token 优化**：问答缓存 + 缓存命中率统计 + Skill 路由限定检索范围
- **全量调用日志**：记录所有模型调用（chat / embedding / test / forecast / ocr），含发起人、延迟、token 消耗
- **JWT 认证**：可选认证，开发环境关闭，生产环境强制开启
- **安全设计**：API Key Fernet 加密存储、文件名防路径穿越、HTML 内容 DOMPurify 净化

## 版本历史

| 版本 | 日期 | 核心内容 |
|------|------|---------|
| v0.1 | 2026-07-07 | 初始版本：知识库 + 智能问答 + Skill 路由 + RAG + 模型配置 + Token 统计 |
| v0.2 | 2026-07-08 | 新增 Forecast 时序预测模型支持（Chronos-2 / TimesFM） |
| v0.3 | 2026-07-09 | 新增 TimesFM 推理服务及 Chronos-Large 部署文档 |
| v0.4 | 2026-07-10 | 增加时序分析功能（数据集管理 + 预测任务 + 趋势可视化） |
| v0.5 | 2026-07-12 | 优化一系列问题，增强一系列功能（认证系统、混合检索 RRF、多模型对比、交叉验证、STL 分解、调用日志等） |
| v0.6 | 2026-07-12 | 强化 AI 知识库功能，强化趋势预测（协变量系统、知识状态生命周期、ARIMA/Prophet 协变量接入、中国节假日数据集） |
| **v0.7** | 2026-07-13 | **小批量修复（用户使用说明书、演示数据脚本、页面 bug 修复）** |
| **v0.8** | 2026-07-14 | **增加 OCR 模型支持（DeepSeek-OCR）、VLM 模型支持（多模态视觉解析）、优化性能（真 Okapi BM25、text_chunker 段落感知+句子边界+滑动窗口、引用溯源 chunk_id+page_number）** |

完整发布历史：https://github.com/Luerlei/MOM-AI-KBS/releases

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI 0.115 | 异步 API，自动生成 Swagger 文档 |
| 数据库 | SQLAlchemy 2.0 + SQLite | 关系型数据（15 个模型） |
| 向量数据库 | ChromaDB 0.5 | 嵌入式，无需独立服务 |
| 前端框架 | Vue 3 + TypeScript | Composition API |
| UI 组件 | Ant Design Vue 4.x | 企业级中后台 |
| 状态管理 | Pinia | 轻量响应式 |
| 构建工具 | Vite 5 | 极速 HMR |
| 图表 | ECharts 5 | 仪表盘 + 趋势分析 + STL 分解 |
| 测试 | Vitest + @vue/test-utils | 前端 UI 自动化测试 |
| HTTP 客户端 | httpx | 异步调用 LLM API |
| 加密 | cryptography + PyJWT | API Key 加密 + JWT 认证 |
| 时序统计 | statsmodels + prophet | ARIMA / ETS / Theta / STL / Prophet |
| 文件解析 | PyPDF2 / python-docx / openpyxl / PyMuPDF | PDF / DOCX / XLSX 解析（PyMuPDF 用于 VLM 按页转图） |
| BM25 检索 | 自实现 Okapi BM25 | IDF 加权 + 词频饱和 + 文档长度归一化（纯 Python 零依赖） |

## 项目结构

```
LLM Wiki/
├── backend/                          # 后端服务
│   ├── app/
│   │   ├── main.py                   # FastAPI 入口（14 个路由注册）
│   │   ├── config.py                 # 配置管理（环境变量 + 安全校验）
│   │   ├── database.py               # 数据库初始化 + 自动迁移
│   │   ├── data/                     # 静态数据
│   │   │   └── china_holidays.json   # 中国节假日数据集（2024-2026）
│   │   ├── models/                   # 15 个数据模型
│   │   ├── routers/                  # 14 个 API 路由模块
│   │   ├── schemas/                  # Pydantic 验证模型
│   │   ├── services/                 # 21 个业务服务（含 bm25_service / pdf_parser_backend ★v0.8）
│   │   └── utils/                    # 工具层（auth/crypto/excel_parser/response）
│   ├── scripts/                      # Forecast 推理服务 + 演示数据脚本
│   ├── data/                         # 数据目录（gitignore）
│   ├── run.py                        # 启动脚本
│   └── requirements.txt
├── frontend/                         # 前端应用
│   ├── src/
│   │   ├── views/                    # 17 个页面
│   │   ├── components/               # 7 个通用组件
│   │   ├── api/                      # 14 个 API 模块
│   │   ├── stores/                   # Pinia 状态
│   │   ├── layouts/                  # 主布局
│   │   ├── router/                   # 路由配置（18 条路由）
│   │   └── types/                   # TypeScript 类型定义
│   ├── tests/                        # 单元测试
│   └── package.json
├── docs/                             # 文档目录
│   ├── DESIGN.md                     # 设计书
│   ├── USER_GUIDE.md                 # 使用说明书
│   ├── chronos-deploy.md             # Chronos 部署指南
│   ├── chronos-large-deploy.md       # Chronos-Large 部署
│   └── timesfm-deploy.md             # TimesFM 部署
├── README.md
├── LICENSE                           # MIT
└── .gitignore
```

## 快速开始

### 环境要求

- Python 3.9+
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

### Forecast 推理服务（可选）

时序预测功能需要独立的 Forecast 推理服务（Python 3.11）：

```bash
cd backend/scripts
python chronos_server.py   # :8501
python timesfm_server.py  # :8502
```

详见 [docs/chronos-deploy.md](docs/chronos-deploy.md) 和 [docs/timesfm-deploy.md](docs/timesfm-deploy.md)。

### 演示数据注入（可选）

```bash
cd backend
python scripts/seed_demo_data.py   # 注入匹配各 Skill 的示例知识
```

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
| Forecast | 可选 | 时序预测模型，用于趋势分析；未配置时统计模型仍可用 |
| Rerank | 可选 | 重排序模型，对 RAG 检索结果二次排序提升相关性 |
| OCR | 可选 | 文档解析模型（DeepSeek-OCR），PDF 直接输入返回结构化 Markdown；未配置时回退 PyPDF2 |
| VLM | 可选 | 视觉解析模型（Qwen-VL/GPT-4o 等），按页转图后调用 vision API；未配置时回退 PyPDF2 |

**支持的 LLM 提供商**（OpenAI 兼容格式）：
- MiMo（小米）、通义千问、OpenAI、DeepSeek、Ollama 等

**支持的 Embedding 提供商**：
- SiliconFlow（如 BAAI/bge-m3）、通义千问、OpenAI 等

**支持的 Forecast 推理服务**：
- Chronos-2（本地 :8501/:8503）、TimesFM 2.5（本地 :8502）

**支持的 OCR/VLM 提供商**：
- SiliconFlow DeepSeek-OCR（`deepseek-ai/DeepSeek-OCR`，PDF 原生输入）
- SiliconFlow Qwen3-VL（`Qwen/Qwen3-VL-32B-Instruct`，按页转图）
- 任意 OpenAI 兼容 vision API（GPT-4o 等）

> API URL 填写 base URL 即可，系统会自动拼接 `/embeddings` 或 `/chat/completions` 后缀；若误填带后缀也会自动剥离。

### 环境变量

后端配置通过 `.env` 文件或环境变量设置，参考 `.env.example`：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| DATABASE_URL | sqlite:///data/knowledge.db | SQLite 数据库路径 |
| VECTOR_DB_PATH | data/vectors | ChromaDB 持久化目录 |
| UPLOAD_PATH | data/uploads | 文件上传目录 |
| HOST / PORT | 0.0.0.0 / 8000 | 服务监听地址 |
| DEBUG | true | 调试模式（自动重载） |
| CACHE_SIMILARITY_THRESHOLD | 0.90 | 问答缓存命中阈值 |
| SECRET_KEY | dev-secret-key-change-in-production | JWT + API Key 加密密钥（生产环境务必修改） |
| AUTH_ENABLED | false | 认证开关（生产环境必须 true） |
| ADMIN_USERNAME / ADMIN_PASSWORD | admin / changeme | 管理员账号（生产环境务必修改） |
| JWT_EXPIRE_HOURS | 24 | JWT 过期时间 |
| CORS_ORIGINS | * | CORS 允许来源（生产环境必须指定） |
| PDF_PARSER_BACKEND | auto | PDF 解析后端：pypdf2 / deepseek-ocr / vlm / auto（按数据库 OCR 模型配置） |
| DEEPSEEK_OCR_API_KEY | （空） | DeepSeek-OCR API Key（也可在模型配置页添加 type=OCR 模型） |
| DEEPSEEK_OCR_BASE_URL | https://api.siliconflow.cn/v1 | DeepSeek-OCR 服务地址 |
| DEEPSEEK_OCR_MODEL | deepseek-ai/DeepSeek-OCR | DeepSeek-OCR 模型名 |
| VLM_API_KEY | （空） | VLM 视觉解析 API Key（也可在模型配置页添加 type=VLM 模型） |
| VLM_BASE_URL | https://api.siliconflow.cn/v1 | VLM 服务地址 |
| VLM_MODEL | Qwen/Qwen3-VL-32B-Instruct | VLM 模型名 |

## 核心流程

### 智能问答流程

```
用户提问
  │
  ▼
[Skill 路由引擎] 关键词/正则/语义三级匹配 → 命中 Skill
  │
  ▼
[Embedding 向量化] 将问题转为向量（复用避免重复调用）
  │
  ▼
[问答缓存] 向量相似度 > 0.90 → 命中缓存直接返回
  │
  ▼
[混合检索] 向量检索 + 真 Okapi BM25 关键词检索 + RRF 融合（仅 published 知识）
  │
  ▼
[Prompt 组装] Skill 模板 + 检索片段 + 用户问题（Token 预算控制，来源含 chunk_id + page_number）
  │
  ▼
[LLM 流式生成] SSE 逐步返回答案
  │
  ▼
[记录] 保存历史 + TokenUsage + 写入缓存
```

**降级策略**：
- 无 Embedding 模型：RAG 仅走 BM25 关键词检索，`degraded=True`
- 无匹配 Skill：使用默认 Skill 在全量知识库检索
- 语义搜索失败：前端自动切换为关键词搜索
- 向量维度不匹配：自动重建 ChromaDB collection
- 无 OCR/VLM 模型：PDF 解析回退 PyPDF2 文本层抽取
- OCR/VLM 解析失败或返回空：自动回退 PyPDF2 兜底

### Skill 路由三级匹配

1. **关键词/正则匹配**：命中数最多的 Skill 优先
2. **语义匹配**：问题向量与 Skill description 向量余弦相似度 > 0.7
3. **默认兜底**：使用 `is_default=true` 的 Skill

### 知识状态生命周期

| 状态 | 说明 | 向量索引 | RAG 检索 |
|------|------|---------|---------|
| draft | 草稿 | 无索引 | 不可检索 |
| published | 发布 | 有索引 | ✅ 可检索 |
| archived | 归档 | 无索引 | 不可检索 |

状态变更自动记录审计日志（`KnowledgeStatusLog`），并联动向量索引和答案缓存。

## 功能模块

| 模块 | 路径 | 说明 |
|------|------|------|
| 首页仪表盘 | /dashboard | 统计卡片、最近问答、快捷操作 |
| 知识管理 | /knowledge | 列表/详情/编辑/上传，支持状态管理（draft/published/archived） |
| 智能搜索 | /search | 语义+关键词搜索，二次筛选（分类/标签/时间） |
| 智能问答 | /qa | SSE 流式问答，来源标注、反馈、追问推荐 |
| 问答历史 | /qa/history | 历史记录、搜索、删除 |
| Skill 管理 | /skills | CRUD、分类自定义、模板创建、路由测试 |
| 模型配置 | /models | LLM/Embedding/Forecast/Rerank/OCR/VLM 配置、连通测试、热更新 |
| 数据集管理 | /datasets | 时序数据集 CRUD、Excel/CSV 导入导出、预览 |
| 协变量管理 | /datasets/:id/covariates | 协变量 CRUD、自动生成、对齐矩阵预览 |
| 趋势分析 | /trends | 预测/回测、STL 分解、交叉验证、多模型对比 |
| Token 统计 | /token-stats | 趋势图、维度统计、缓存命中率、成本估算 |
| 调用日志 | /call-logs | 所有模型调用日志（chat/embedding/test/forecast） |

## 时序预测

### 预测模式

| 模式 | 说明 |
|------|------|
| 预测未来 | 从历史末尾预测未来 horizon 步 |
| 回测对照 | 从 start_index 拆分，训练集预测，与实际值对比计算误差 |
| 滑动窗口 | 仅使用最后 train_window 个点训练 |
| 交叉验证 | expanding / sliding 策略多次回测取平均 |
| 多模型对比 | 临时切换激活模型执行回测，按 MAE 最低找出最优 |

### 模型类型

| 类型 | 模型 | 协变量支持 |
|------|------|-----------|
| 深度学习 | Chronos-2 / TimesFM 2.5 | ❌（接口已预留） |
| 统计模型 | ARIMA | ✅ |
| 统计模型 | Prophet | ✅ |
| 统计模型 | ETS / Theta | ❌ |

### 评估指标

MAE / MAPE / RMSE / MASE / sMAPE / Pinball Loss / Coverage / rMAE（相对 Naive 基线）

## 协变量系统

协变量（外生变量）用于增强 ARIMA/Prophet 等统计模型的预测能力。

### 协变量类型

- **continuous**：连续型（温度、价格）
- **binary**：二元型（是否节假日、是否促销）
- **categorical**：分类型（需编码为数值）

### 自动生成

系统根据数据集频率自动生成常用协变量：

| 频率 | 自动生成的协变量 |
|------|-----------------|
| 所有频率 | `trend`（线性趋势） |
| daily/weekly/monthly | `is_holiday`（中国法定节假日） |
| daily/hourly | `is_weekend`（周末） |
| monthly | `month_sin` + `month_cos`（周期编码） |
| daily | `dow_sin` + `dow_cos`（周期编码） |
| quarterly | `quarter_sin` + `quarter_cos`（周期编码） |

内置 [china_holidays.json](backend/app/data/china_holidays.json) 覆盖 2024-2026 年中国法定节假日。

## API 接口

完整 Swagger 文档：http://localhost:8000/docs

### 核心 API 速查

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 认证 | POST | /api/auth/login | 登录获取 JWT |
| 认证 | GET | /api/auth/status | 认证开关状态 |
| 健康 | GET | /health | 健康检查 |
| 模型 | GET/POST | /api/models | 模型配置 CRUD |
| 模型 | PUT | /api/models/{id}/activate | 启用模型 |
| 模型 | POST | /api/models/{id}/test | 测试连通性 |
| 模型 | GET | /api/models/status | 当前激活的 LLM/Embedding/Forecast/Rerank/OCR/VLM |
| 知识 | GET/POST | /api/knowledge | 知识 CRUD |
| 知识 | POST | /api/knowledge/upload | 上传文件 |
| 知识 | POST | /api/knowledge/rebuild-indexes | 重建所有索引 |
| 知识 | GET | /api/knowledge/{id}/status-logs | 状态审计日志 |
| Skill | GET/POST | /api/skills | Skill CRUD |
| Skill | POST | /api/skills/{id}/test | 测试路由匹配 |
| 搜索 | GET | /api/search/semantic | 语义搜索 |
| 搜索 | GET | /api/search/keyword | 关键词搜索 |
| 问答 | POST | /api/qa/ask | SSE 流式问答 |
| 问答 | GET | /api/qa/history | 问答历史 |
| 数据集 | GET/POST | /api/datasets | 数据集 CRUD |
| 数据集 | POST | /api/datasets/import | Excel/CSV 导入 |
| 协变量 | GET/POST | /api/datasets/{id}/covariates | 协变量 CRUD |
| 协变量 | POST | /api/datasets/{id}/covariates/auto-generate | 自动生成 |
| 预测 | POST | /api/forecast/predict | 执行预测 |
| 预测 | POST | /api/forecast/statistical-forecast | 统计模型预测（含协变量） |
| 预测 | POST | /api/forecast/cross-validation | 交叉验证 |
| 预测 | POST | /api/forecast/compare-models | 多模型对比 |
| 预测 | GET | /api/forecast/decomposition/{id} | STL 分解 |
| 仪表盘 | GET | /api/dashboard/stats | 统计数据 |
| 统计 | GET | /api/token-stats | Token 汇总 |
| 统计 | GET | /api/token-stats/model-call-logs | 模型调用日志 |

## 测试

### 后端 API 测试

```bash
cd backend
python api_test.py
```

### 前端 UI 自动化测试

```bash
cd frontend
npm test                # 单次运行
npm run test:watch      # 监听模式
npm run test:coverage   # 覆盖率报告
```

### 构建验证

```bash
cd frontend
npm run build   # TypeScript 类型检查 + Vite 打包
```

## 预制数据

系统首次启动自动创建：
- 4 个分类（制造运营/仓储物流/质量管理/设备管理）
- 6 个标签（故障代码/保养/工艺/质量标准/仓储管理/操作经验）
- 5 个预制 Skill（故障诊断/保养维护/工艺指导/质量检验/通用问答[默认]）
- 10 个 Skill 分类/功能选项
- 2 个 Forecast 模型配置（Chronos-2 / TimesFM 2.5）
- 3 个辅助模型配置（bge-reranker-v2-m3 / DeepSeek-OCR / Qwen3-VL-32B，用户填 API Key 即可激活）★ v0.8
- 2 个示例时序数据集
- 5 个示例知识条目（匹配各 Skill 知识范围）

## 文档

- [设计书](docs/DESIGN.md) — 完整架构设计与数据模型
- [使用说明书](docs/USER_GUIDE.md) — 面向最终用户的功能使用指南
- [Chronos 部署指南](docs/chronos-deploy.md) — Chronos-T5-Small 推理服务
- [Chronos-Large 部署指南](docs/chronos-large-deploy.md) — 高精度预测服务
- [TimesFM 部署指南](docs/timesfm-deploy.md) — Google TimesFM 2.5 推理服务

## 常见问题

**Q: 启动后端报 `ModuleNotFoundError: No module named 'uvicorn'`？**
A: 确认已激活虚拟环境并安装依赖 `pip install -r requirements.txt`。若本机多版本 Python 共存，明确指定解释器，如 `C:\Path\To\Python39\python.exe run.py`。

**Q: 模型测试报 404？**
A: 检查 API URL 是否填写了 base URL（如 `https://api.siliconflow.cn/v1`），系统会自动拼接 `/embeddings` 或 `/chat/completions`。若误填带后缀也会自动剥离。

**Q: 切换 Embedding 模型后检索失败？**
A: 切换不同维度的 Embedding 模型时，系统会自动捕获维度不匹配异常并重建 ChromaDB collection。也可手动调用 `POST /api/knowledge/rebuild-indexes` 重建所有索引。

**Q: 流式问答 token 显示为 0？**
A: 部分国产 LLM API（如小米 MiMo 非 stream 模式）不返回 usage 字段。系统已对 stream 模式启用 `stream_options.include_usage` 以尽量获取准确 token 数。

**Q: 如何避免 API Key 泄露？**
A: API Key 使用 `cryptography` 库 Fernet 加密存储于数据库，前端展示脱敏。`.env` 文件已加入 `.gitignore`。

**Q: 协变量如何接入预测？**
A: 在协变量管理页面创建或自动生成协变量后，在趋势分析页面选择统计模型（ARIMA/Prophet）并勾选"使用协变量"即可。详见 [使用说明书](docs/USER_GUIDE.md)。

**Q: 知识状态有什么用？**
A: draft（草稿）不会被 RAG 检索；published（发布）可被检索；archived（归档）不再被检索。状态变更会自动同步向量索引并记录审计日志。

**Q: OCR/VLM 模型有什么用？怎么配置？**
A: PyPDF2 只能抽取 PDF 文本层，对扫描件/图片型 PDF 无能为力。配置 OCR（DeepSeek-OCR）或 VLM（Qwen-VL/GPT-4o）后，PDF 上传解析将走深度文档理解，输出结构化 Markdown（含表格、标题层级、页码标记），显著提升 RAG 检索质量。在「模型配置」页新增 type=OCR 或 type=VLM 的模型配置并填入 API Key 即可激活，无需重启服务。

**Q: BM25 检索和原来有什么区别？**
A: v0.8 起使用真正的 Okapi BM25 算法（IDF 加权 + 词频饱和 k1=1.5 + 文档长度归一化 b=0.75），替代了早期 SQLite LIKE 的简单打分（标题命中=2分、内容命中=1分）。索引在内存中维护，知识增删改时增量同步，首次查询时按需从数据库全量构建。

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
