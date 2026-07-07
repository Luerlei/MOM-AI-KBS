# MOM系统AI知识库平台

> Skill 路由 + 自实现轻量 RAG 架构的制造企业知识库平台

基于 FastAPI + Vue3 + ChromaDB 构建，平台模型无关（统一接口抽象层），支持 LLM 智能问答、语义/关键词搜索、Skill 路由分发、Token 统计优化等完整功能。

## 核心特性

- **Skill 路由引擎**：根据用户问题关键词/语义匹配对应 Skill，使用专属 Prompt 模板和知识范围
- **自实现轻量 RAG**：不依赖 LangChain/LlamaIndex，直接使用 ChromaDB SDK + httpx 调用模型 API
- **模型无关架构**：统一 LLMClient 抽象层，支持任意 OpenAI 兼容模型（MiMo/通义千问/OpenAI 等）
- **优雅降级**：仅有 LLM 时 RAG 自动降级为直接对话；语义搜索失败时自动切换为关键词搜索
- **运行时热更新**：模型配置修改后立即生效，无需重启服务
- **Token 优化**：问答缓存 + 缓存命中率统计 + Skill 路由限定检索范围
- **完整测试覆盖**：前端 51 用例 + 后端 21 接口测试 + 构建验证全部通过

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI 0.115 | 异步 API，自动生成 Swagger 文档 |
| 数据库 | SQLAlchemy + SQLite | 关系型数据（MVP） |
| 向量数据库 | ChromaDB | 嵌入式，无需独立服务 |
| 前端框架 | Vue 3 + TypeScript | Composition API |
| UI 组件 | Ant Design Vue 4.x | 企业级中后台 |
| 状态管理 | Pinia | 轻量响应式 |
| 构建工具 | Vite 5 | 极速 HMR |
| 图表 | ECharts | 仪表盘 + Token 趋势 |
| 测试 | Vitest + @vue/test-utils | 前端 UI 自动化测试 |

## 项目结构

```
LLM Wiki/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── main.py             # FastAPI 入口
│   │   ├── config.py           # 配置管理
│   │   ├── database.py         # 数据库初始化
│   │   ├── models/             # 9 个数据模型
│   │   ├── routers/            # 10 个 API 路由模块
│   │   ├── schemas/            # Pydantic 验证模型
│   │   ├── services/           # 16 个业务服务
│   │   │   ├── llm_client.py          # LLM 客户端抽象层
│   │   │   ├── rag_service.py         # RAG 检索增强生成
│   │   │   ├── skill_router.py        # Skill 路由引擎
│   │   │   ├── vector_store.py        # ChromaDB 封装
│   │   │   └── ...
│   │   └── utils/              # 工具类
│   ├── data/                   # 数据目录（SQLite + ChromaDB + 上传文件）
│   ├── run.py                  # 启动脚本
│   ├── requirements.txt
│   └── api_test.py             # 后端 API 测试脚本
├── frontend/                   # 前端应用
│   ├── src/
│   │   ├── views/              # 12 个页面
│   │   ├── components/         # 5 个通用组件
│   │   ├── api/                # 9 个 API 模块
│   │   ├── stores/             # Pinia 状态
│   │   ├── layouts/            # 布局
│   │   └── types/              # TypeScript 类型
│   ├── tests/                  # 10 个测试文件，51 个用例
│   ├── package.json
│   └── vite.config.ts
└── README.md
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
| LLM | ✅ 必需 | 大语言模型，用于智能问答生成答案 |
| Embedding | ❌ 可选 | 向量化模型，用于语义搜索和 RAG 检索；未配置时 RAG 降级为直接对话 |

**支持的 LLM 提供商**（OpenAI 兼容格式）：
- MiMo（小米）：`https://api.xiaomimimo.com/v1`
- 通义千问：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- OpenAI：`https://api.openai.com/v1`
- 本地部署：`http://localhost:11434/v1`（Ollama）等

**支持的 Embedding 提供商**（OpenAI 兼容格式，通过模型配置页添加）：
- SiliconFlow：`https://api.siliconflow.cn/v1`（如 BAAI/bge-m3）
- 通义千问、OpenAI 等兼容服务商

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

## 核心流程

### 智能问答流程

```
用户提问
  │
  ▼
[Skill 路由引擎] 关键词/语义匹配 → 命中 Skill
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

## 功能模块

| 模块 | 路径 | 说明 |
|------|------|------|
| 首页仪表盘 | /dashboard | 统计卡片、最近问答、知识/Skill/Token 概览 |
| 知识管理 | /knowledge | 列表/详情/编辑/上传，支持批量操作 |
| 智能搜索 | /search | 语义+关键词搜索，二次筛选（分类/标签/时间） |
| 智能问答 | /qa | SSE 流式问答，来源标注、反馈、追问推荐 |
| 问答历史 | /qa/history | 历史记录、搜索、删除 |
| Skill 管理 | /skills | CRUD、分类自定义、模板创建、启用切换 |
| 模型配置 | /models | LLM/Embedding 配置、连通测试、热更新 |
| Token 统计 | /token-stats | 趋势图、维度统计、缓存命中率 |

## 预制数据

系统首次启动自动创建：
- 4 个分类：制造运营、仓储物流、质量管理、设备管理
- 6 个标签：故障代码、保养、工艺、质量标准、仓储管理、操作经验
- 5 个预制 Skill：故障诊断、保养维护、工艺指导、质量检验、通用问答
- 10 个 Skill 分类/功能选项（可自定义扩展）

## 数据源扩展

预留 `DataAdapter` 接口（[data_adapter.py](backend/app/services/data_adapter.py)），支持后续从外部数据库或 API 接入数据。MVP 阶段不实现具体适配器。

## 许可证

内部使用，未公开发布。
