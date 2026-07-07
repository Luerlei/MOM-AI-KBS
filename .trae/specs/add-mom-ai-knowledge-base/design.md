# MOM系统AI知识库平台 - 设计文档

## 1. 系统概述

### 1.1 项目目标
构建面向制造企业MOM系统的AI知识库平台，通过 **Skill路由 + 自实现轻量RAG** 架构，实现知识的智能化管理和检索，降低token消耗和模型性能要求。

### 1.2 核心价值
- **Skill驱动**：通过Skill路由精准匹配用户意图与知识范围，减少无关上下文
- **轻量化**：自实现RAG，不依赖LangChain，依赖包少80%，内存占用低
- **模型无关**：Web界面配置模型API，运行时切换，无需改代码
- **本地可运行**：MVP在开发电脑上可正常运行

### 1.3 设计原则
1. 轻量化优先：保证功能完整性，实现可简化但功能不缺失
2. Skill驱动：通过Skill路由降低token消耗和模型性能要求
3. 自实现RAG：不依赖LangChain/LlamaIndex，依赖最少
4. 本地可运行：MVP在开发电脑上可正常运行
5. 模型无关：通过统一API接口调用模型

---

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端（Vue3 + Ant Design Vue）          │
│  ┌──────┬──────┬──────┬──────┬──────┬──────┬──────┐     │
│  │ 首页 │ 知识 │ 搜索 │ 问答 │Skill │模型配│ 历史 │     │
│  │仪表盘│ 管理 │      │      │ 管理 │ 置管 │ 管理 │     │
│  │      │      │      │      │      │ 理   │      │     │
│  └──────┴──────┴──────┴──────┴──────┴──────┴──────┘     │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP/JSON (Axios)
┌───────────────────────▼─────────────────────────────────┐
│                 后端（Python + FastAPI）                  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐     │
│  │                  API 路由层                       │     │
│  │  /api/knowledge  /api/skills  /api/qa  /api/...  │     │
│  └──────────────────────┬──────────────────────────┘     │
│                         │                               │
│  ┌──────────────────────▼──────────────────────────┐     │
│  │                  业务服务层                       │     │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐         │     │
│  │  │知识管理   │ │Skill管理  │ │模型配置   │         │     │
│  │  │服务      │ │+路由引擎  │ │服务      │         │     │
│  │  └──────────┘ └──────────┘ └──────────┘         │     │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐         │     │
│  │  │RAG检索   │ │问答服务   │ │文件解析   │         │     │
│  │  │服务      │ │          │ │服务      │         │     │
│  │  └──────────┘ └──────────┘ └──────────┘         │     │
│  └──────────────────────┬──────────────────────────┘     │
│                         │                               │
│  ┌──────────────────────▼──────────────────────────┐     │
│  │                  数据访问层                       │     │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐         │     │
│  │  │SQLAlchemy │ │ChromaDB  │ │模型API    │         │     │
│  │  │(SQLite)  │ │(向量库)   │ │(httpx)   │         │     │
│  │  └──────────┘ └──────────┘ └──────────┘         │     │
│  └─────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| 后端框架 | FastAPI | 高性能、自动文档、异步支持 |
| 数据库 | SQLite | MVP轻量，无需安装服务 |
| ORM | SQLAlchemy | 成熟稳定 |
| 向量数据库 | ChromaDB | 嵌入式，无需独立服务 |
| RAG框架 | 自实现 | 不依赖LangChain，约300行核心代码 |
| 模型调用 | httpx | 异步HTTP客户端 |
| 前端框架 | Vue 3 + TypeScript | 渐进式、类型安全 |
| UI组件库 | Ant Design Vue | 企业级组件 |
| 状态管理 | Pinia | Vue3推荐 |
| 构建工具 | Vite | 快速HMR |
| API请求 | Axios | 拦截器、统一错误处理 |

---

## 3. 核心模块设计

### 3.1 知识管理模块

#### 数据模型
```python
# 知识条目
Knowledge {
  id: int (PK)
  title: str                    # 标题
  content: str                  # 内容（Markdown）
  content_type: str             # 类型：标准文档/经验知识/培训资料/数据报表
  category_id: int (FK)         # 分类目录
  source_type: str              # 来源：upload/manual
  source_file: str              # 原始文件名（上传时）
  created_at: datetime
  updated_at: datetime
}

# 分类目录（树形）
Category {
  id: int (PK)
  name: str                     # 分类名称
  parent_id: int (FK, nullable) # 父分类（树形结构）
  sort_order: int               # 排序
}

# 标签
Tag {
  id: int (PK)
  name: str                     # 标签名
}

# 知识-标签关联（多对多）
KnowledgeTag {
  knowledge_id: int (FK)
  tag_id: int (FK)
}

# 上传文件记录
Document {
  id: int (PK)
  filename: str                 # 原始文件名
  file_path: str                # 存储路径
  file_type: str                # pdf/docx/xlsx/md
  file_size: int                # 文件大小
  knowledge_id: int (FK)        # 关联的知识条目
  uploaded_at: datetime
}
```

#### 文件解析流程
```
上传文件 → 保存到本地 → 按类型选择解析器 → 提取文本 → 创建知识条目 → 分块 → 生成Embedding → 存入ChromaDB
```

解析器支持：
- PDF: PyPDF2
- Word: python-docx
- Excel: openpyxl
- Markdown: 直接读取

#### 向量索引自动同步
```
创建知识 → 分块 → Embedding → ChromaDB.add()
更新知识 → ChromaDB.delete(old) → 分块 → Embedding → ChromaDB.add(new)
删除知识 → ChromaDB.delete(by_knowledge_id)
```

### 3.2 Skill管理模块（核心）

#### 数据模型
```python
Skill {
  id: int (PK)
  name: str                         # Skill名称
  description: str                  # 描述
  category: str                     # 模块维度：制造运营/仓储物流/质量管理/设备管理
  function: str                     # 功能维度：故障查询/保养提醒/工艺指导等
  trigger_keywords: str (JSON)      # 触发关键词列表 ["故障", "报错", "E"]
  trigger_patterns: str (JSON)      # 触发模式（正则） ["E\\d+", "故障代码.*"]
  prompt_template: str              # Prompt模板（含{context}{question}变量）
  knowledge_scope: str (JSON)      # 知识范围 {"category_ids": [1,2], "tag_ids": [3,4]}
  enabled: bool                     # 启用状态
  is_default: bool                  # 是否默认Skill
  created_at: datetime
  updated_at: datetime
}
```

#### Skill路由引擎流程
```
用户问题
  │
  ▼
┌─────────────────────┐
│ 1. 关键词匹配        │ ← 遍历所有启用Skill的trigger_keywords
│    命中关键词的Skill │    和trigger_patterns（正则）
└─────────┬───────────┘
          │ 无命中
          ▼
┌─────────────────────┐
│ 2. 语义匹配          │ ← 将问题Embedding与Skill描述Embedding
│    计算相似度Top-K   │    计算相似度，取Top-1（阈值>0.7）
└─────────┬───────────┘
          │ 无匹配或低于阈值
          ▼
┌─────────────────────┐
│ 3. 默认Skill兜底     │ ← 使用is_default=true的Skill
│    全量知识库检索     │    knowledge_scope为空
└─────────────────────┘
```

#### Skill知识范围过滤
```python
def get_search_scope(skill: Skill) -> dict:
    """根据Skill的knowledge_scope构建检索过滤条件"""
    scope = json.loads(skill.knowledge_scope)
    where_filter = {}
    if scope.get("category_ids"):
        where_filter["category_id"] = {"$in": scope["category_ids"]}
    if scope.get("tag_ids"):
        where_filter["tag_ids"] = {"$in": scope["tag_ids"]}
    return where_filter  # 传给ChromaDB的where参数
```

### 3.3 模型配置管理模块

#### 数据模型
```python
ModelConfig {
  id: int (PK)
  name: str                     # 配置名称（如：千问本地、MIMO在线）
  type: str                      # 模型类型：LLM / Embedding
  api_url: str                   # API地址
  api_key: str                   # 密钥（加密存储）
  model_name: str                # 模型名称（如：qwen2.5-7b、mimo-v1）
  is_active: bool                # 是否启用（同类型仅一个启用）
  created_at: datetime
  updated_at: datetime
}
```

#### 模型接口抽象层
```python
class LLMClient(ABC):
    @abstractmethod
    async def chat(self, messages: list, **kwargs) -> str:
        """对话接口"""
    
    @abstractmethod
    async def embedding(self, texts: list) -> list:
        """向量化接口"""

class OpenAICompatibleClient(LLMClient):
    """OpenAI兼容格式客户端（千问/MIMO均兼容此格式）"""
    def __init__(self, config: ModelConfig):
        self.api_url = config.api_url
        self.api_key = config.api_key
        self.model_name = config.model_name
    
    async def chat(self, messages, **kwargs):
        # POST {api_url}/chat/completions
        # OpenAI兼容格式
        ...
    
    async def embedding(self, texts):
        # POST {api_url}/embeddings
        # OpenAI兼容格式
        ...

class ModelManager:
    """模型管理器，从数据库读取启用的配置"""
    def get_active_llm(self) -> LLMClient:
        config = db.query(ModelConfig).filter(
            ModelConfig.type == "LLM",
            ModelConfig.is_active == True
        ).first()
        return OpenAICompatibleClient(config)
    
    def get_active_embedding(self) -> LLMClient:
        config = db.query(ModelConfig).filter(
            ModelConfig.type == "Embedding",
            ModelConfig.is_active == True
        ).first()
        return OpenAICompatibleClient(config)
```

#### 运行时热更新
```python
# 每次请求时从数据库读取当前启用配置，不缓存
# 修改配置后立即生效
```

### 3.4 自实现轻量RAG

#### 核心组件
```python
# 1. 文本分块器
class TextChunker:
    def chunk(self, text: str, chunk_size=500, overlap=50) -> list[str]:
        """按段落+长度分块，保留overlap"""
        paragraphs = text.split("\n\n")
        chunks = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) < chunk_size:
                current += para + "\n\n"
            else:
                if current:
                    chunks.append(current.strip())
                current = para + "\n\n"
        if current:
            chunks.append(current.strip())
        return chunks

# 2. Embedding服务
class EmbeddingService:
    def __init__(self, model_manager: ModelManager):
        self.client = model_manager.get_active_embedding()
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self.client.embedding(texts)

# 3. 向量存储
class VectorStore:
    def __init__(self):
        self.collection = chromadb.PersistentClient(path="./data/vectors").get_or_create_collection("knowledge")
    
    def add(self, knowledge_id, chunks, embeddings, metadata):
        self.collection.add(
            ids=[f"{knowledge_id}_{i}" for i in range(len(chunks))],
            documents=chunks,
            embeddings=embeddings,
            metadatas=[metadata] * len(chunks)
        )
    
    def search(self, query_embedding, where=None, top_k=5):
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where  # Skill知识范围过滤
        )
        return results

# 4. Prompt组装器
class PromptAssembler:
    def assemble(self, skill: Skill, question: str, context_chunks: list) -> list:
        context = "\n\n".join(context_chunks)
        prompt = skill.prompt_template.replace("{context}", context).replace("{question}", question)
        return [
            {"role": "system", "content": prompt},
            {"role": "user", "content": question}
        ]

# 5. RAG服务（串联以上组件）
class RAGService:
    async def answer(self, question: str, skill: Skill) -> dict:
        # 1. Embedding问题
        query_emb = await self.embedding_service.embed([question])
        # 2. 在Skill知识范围内检索
        where = get_search_scope(skill)
        results = self.vector_store.search(query_emb[0], where=where, top_k=5)
        # 3. 组装Prompt
        messages = self.prompt_assembler.assemble(skill, question, results["documents"][0])
        # 4. 调用LLM
        llm = self.model_manager.get_active_llm()
        answer = await llm.chat(messages)
        # 5. 返回答案+来源
        return {"answer": answer, "sources": results["metadatas"][0]}
```

### 3.5 问答流程（端到端）

```
用户提问 "设备E01故障怎么处理？"
  │
  ▼
Skill路由引擎
  ├─ 关键词匹配 → 命中"设备管理"模块的"故障查询"Skill
  │
  ▼
RAG服务
  ├─ 问题Embedding生成
  ├─ ChromaDB检索（where: category_id="设备管理"）
  ├─ 返回Top-5相关知识片段
  ├─ 组装Prompt（Skill模板 + 检索结果 + 问题）
  ├─ 调用LLM生成答案
  │
  ▼
返回结果
  ├─ 答案文本
  ├─ 来源标注（知识标题、片段内容）
  ├─ 匹配的Skill信息
  │
  ▼
保存问答历史
  ├─ 问题、答案、来源、Skill、时间戳
```

### 3.6 Token优化机制

| 机制 | 说明 | 节省效果 |
|------|------|---------|
| Skill限定检索 | 仅在Skill关联的知识范围内检索 | 减少50-80%上下文 |
| RAG分块检索 | 仅传Top-K片段而非全量文档 | 减少90%+上下文 |
| 问答缓存 | 相似问题向量匹配，命中直接返回 | 减少100%（命中时） |
| Prompt精简 | Skill级别Prompt模板优化 | 减少20-30% |

#### 缓存机制设计
```python
class AnswerCache:
    def __init__(self, vector_store, threshold=0.95):
        self.threshold = threshold  # 相似度阈值
    
    async def get(self, question: str) -> Optional[dict]:
        # 将问题Embedding后与缓存库中的问题比对
        query_emb = await self.embedding_service.embed([question])
        results = self.cache_collection.query(
            query_embeddings=[query_emb[0]],
            n_results=1
        )
        if results["distances"][0][0] > self.threshold:
            return json.loads(results["metadatas"][0][0]["answer"])
        return None
    
    async def put(self, question: str, answer: dict):
        query_emb = await self.embedding_service.embed([question])
        self.cache_collection.add(
            ids=[str(uuid4())],
            documents=[question],
            embeddings=[query_emb[0]],
            metadatas=[{"answer": json.dumps(answer)}]
        )
```

---

## 4. 前端设计

### 4.1 页面结构

```
┌─────────────────────────────────────────────────────────┐
│  顶部导航栏（Logo + 全局搜索框 + 用户信息）                 │
├──────────┬──────────────────────────────────────────────┤
│          │                                              │
│  侧边栏   │              内容区                           │
│  导航     │                                              │
│          │                                              │
│  ├─首页   │   根据路由切换页面：                            │
│  ├─知识   │   - 首页仪表盘                                │
│  │  ├─列表│   - 知识列表/详情/编辑                        │
│  │  ├─上传│   - 文档上传                                  │
│  │  └─分类│   - 搜索结果                                  │
│  ├─搜索   │   - 智能问答                                  │
│  ├─问答   │   - 问答历史                                  │
│  ├─历史   │   - Skill管理                                 │
│  ├─Skill │   - 模型配置管理                                │
│  │  管理  │                                              │
│  └─模型   │                                              │
│     配置  │                                              │
│          │                                              │
└──────────┴──────────────────────────────────────────────┘
```

### 4.2 核心页面设计

#### 首页/仪表盘
```
┌─────────────────────────────────────────────────────────┐
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│  │ 知识总数 │ │ Skill数 │ │今日问答 │ │ 文档数  │        │
│  │   156   │ │   12    │ │   23    │ │   89   │        │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │
│                                                         │
│  最近问答记录                              快捷操作        │
│  ┌─────────────────────────────┐     ┌──────────┐       │
│  │ Q: 设备E01故障怎么处理？     │     │ 上传文档  │       │
│  │ A: E01故障代码表示...        │     ├──────────┤       │
│  │ Skill: 故障查询  10:30       │     │ 新建知识  │       │
│  ├─────────────────────────────┤     ├──────────┤       │
│  │ Q: 保养计划如何制定？         │     │ 管理Skill │       │
│  │ A: 保养计划应按照...          │     └──────────┘       │
│  └─────────────────────────────┘                        │
└─────────────────────────────────────────────────────────┘
```

#### Skill管理页面
```
┌─────────────────────────────────────────────────────────┐
│  Skill管理                              [+ 新建Skill]    │
├──────────┬──────────────────────────────────────────────┤
│ 筛选      │  ┌───────────────────────────────────────┐  │
│          │  │ 名称        分类     功能     状态  操作│  │
│ 模块维度: │  ├───────────────────────────────────────┤  │
│ □ 制造运营│  │ 故障查询    设备管理  故障诊断  启用  ✎✕│  │
│ □ 仓储物流│  │ 保养提醒    设备管理  保养维护  启用  ✎✕│  │
│ □ 质量管理│  │ 工艺指导    制造运营  工艺指导  禁用  ✎✕│  │
│ □ 设备管理│  │ 质量标准    质量管理  质量检验  启用  ✎✕│  │
│          │  └───────────────────────────────────────┘  │
│ 功能维度: │                                              │
│ 故障诊断 │                                              │
│ 保养维护 │                                              │
│ 工艺指导 │                                              │
└──────────┴──────────────────────────────────────────────┘
```

#### Skill编辑表单
```
┌─────────────────────────────────────────────────────────┐
│  编辑Skill                                               │
│                                                         │
│  名称: [故障查询                              ]          │
│  描述: [查询设备故障代码含义和处理方案          ]          │
│  分类: [设备管理 ▼]    功能: [故障诊断 ▼]                │
│                                                         │
│  触发关键词: [故障] [报错] [E] [+ 添加]                  │
│  触发模式:  [E\d+] [故障代码.*] [+ 添加]                 │
│                                                         │
│  知识范围:                                               │
│    分类: [✓]设备管理 [ ]制造运营 [ ]质量管理             │
│    标签: [✓]故障代码 [ ]保养 [ ]工艺                    │
│                                                         │
│  Prompt模板:                                             │
│  ┌─────────────────────────────────────────────────┐    │
│  │ 你是设备故障诊断专家。                            │    │
│  │ 根据以下知识内容回答问题：                        │    │
│  │                                                  │    │
│  │ {context}                                        │    │
│  │                                                  │    │
│  │ 问题：{question}                                  │    │
│  └─────────────────────────────────────────────────┘    │
│  支持变量: {context} 检索结果, {question} 用户问题       │
│                                                         │
│           [取消]  [保存]                                 │
└─────────────────────────────────────────────────────────┘
```

#### 模型配置管理页面
```
┌─────────────────────────────────────────────────────────┐
│  模型配置管理                              [+ 新增模型]   │
├─────────────────────────────────────────────────────────┤
│  LLM 模型                                               │
│  ┌────────┬──────────┬──────────┬──────┬──────────────┐ │
│  │ 名称   │ 模型名称  │ API地址   │ 状态 │ 操作         │ │
│  ├────────┼──────────┼──────────┼──────┼──────────────┤ │
│  │千问本地│qwen2.5-7b│localhost:│ ●启用│ 测试 ✎ ✕     │ │
│  │MIMO在线│mimo-v1   │api.mimo. │ ○未用│ 测试 ✎ ✕     │ │
│  └────────┴──────────┴──────────┴──────┴──────────────┘ │
│                                                         │
│  Embedding 模型                                         │
│  ┌────────┬──────────┬──────────┬──────┬──────────────┐ │
│  │ 名称   │ 模型名称  │ API地址   │ 状态 │ 操作         │ │
│  ├────────┼──────────┼──────────┼──────┼──────────────┤ │
│  │千问Embed│text-emb │localhost:│ ●启用│ 测试 ✎ ✕     │ │
│  └────────┴──────────┴──────────┴──────┴──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

#### 智能问答界面（流式输出+反馈+追问）
```
┌─────────────────────────────────────────────────────────┐
│  面包屑: 首页 / 智能问答                                  │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────┐    │
│  │  Q: 设备E01故障怎么处理？                         │    │
│  │                                                  │    │
│  │  A: E01故障代码表示电机过热▌（流式输出中...）      │    │
│  │     1. 停机检查冷却系统                           │    │
│  │     2. 检查电机负载                               │    │
│  │                                                  │    │
│  │     来源: [设备故障代码手册] [电机维护规程]        │    │
│  │     匹配Skill: 故障查询  Token: 1,234             │    │
│  │     👍 有用  👎 无用                               │    │
│  │                                                  │    │
│  │  推荐追问:                                        │    │
│  │  [E02故障怎么处理？] [冷却系统检查步骤？]          │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │ [输入问题...                              ] [发送]│    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

#### 批量上传界面
```
┌─────────────────────────────────────────────────────────┐
│  面包屑: 首页 / 知识管理 / 批量上传                       │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────┐    │
│  │           拖拽文件到此处或点击上传                  │    │
│  │           支持 PDF/Word/Excel/Markdown            │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  上传队列:                                               │
│  ┌──────────┬──────┬──────┬────────┐                    │
│  │ 文件名    │ 大小 │ 状态 │ 操作   │                    │
│  ├──────────┼──────┼──────┼────────┤                    │
│  │ 设备手册.pdf│2.3MB│ ✓完成│ ✕移除  │                    │
│  │ 工艺规程.docx│1.1MB│ ⏳上传中│ ✕    │                    │
│  │ 质量标准.xlsx│856KB│ ⏳待上传│ ✕    │                    │
│  └──────────┴──────┴──────┴────────┘                    │
│                                                         │
│  批量设置元数据:                                         │
│  分类: [设备管理 ▼]   标签: [故障代码] [保养] [+添加]    │
│                                                         │
│  [取消]  [批量提交并创建知识]                             │
└─────────────────────────────────────────────────────────┘
```

#### Token统计页面
```
┌─────────────────────────────────────────────────────────┐
│  面包屑: 首页 / Token统计                                 │
├─────────────────────────────────────────────────────────┤
│  时间范围: [今日] [本周] [本月] [自定义]   模型: [全部▼] │
│                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ 总Token   │ │ 输入Token │ │ 输出Token│ │ 总调用次数│    │
│  │  125,430  │ │  89,200  │ │  36,230  │ │   156    │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
│                                                         │
│  Token消耗趋势 (近7天)                                   │
│  ┌─────────────────────────────────────────────────┐    │
│  │     ╭─╮                                         │    │
│  │   ╭─╯ ╰─╮     ╭─╮                              │    │
│  │ ╭─╯      ╰────╯ ╰──╮                           │    │
│  ╭─╯                    ╰──                        │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  按Skill分布              按调用类型分布                   │
│  ┌──────────────┐        ┌──────────────┐               │
│  │故障查询 42%  │        │ 问答 68%     │               │
│  │保养提醒 25%  │        │ Embedding 22%│               │
│  │工艺指导 18%  │        │ 摘要 10%     │               │
│  │默认     15%  │        └──────────────┘               │
│  └──────────────┘                                       │
└─────────────────────────────────────────────────────────┘
```

#### 知识列表（快速预览+批量操作）
```
┌─────────────────────────────────────────────────────────┐
│  面包屑: 首页 / 知识管理                                  │
├──────────┬──────────────────────────────────────────────┤
│ 筛选      │ ☑ 全选  [批量删除] [批量打标签] [批量移动]   │
│          │ ┌──┬──────────┬──────┬──────┬──────┬────┐   │
│ 分类:    │ │☑│ 标题      │ 类型 │ 分类 │ 标签 │操作│   │
│ □全部    │ ├──┼──────────┼──────┼──────┼──────┼────┤   │
│ □制造运营│ │☑│设备故障手册│标准文档│设备管理│故障码│👁✎✕│   │
│ □仓储物流│ │ │  > 预览: E01代码表示电机过热...│展开│   │
│ □质量管理│ │☐│工艺规程    │标准文档│制造运营│工艺  │👁✎✕│   │
│ □设备管理│ │☐│质量标准    │标准文档│质量管理│质量  │👁✎✕│   │
│          │ └──┴──────────┴──────┴──────┴──────┴────┘   │
│ 标签:    │                              < 1 2 3 >      │
│ 故障代码 │                                              │
│ 保养     │                                              │
└──────────┴──────────────────────────────────────────────┘
```

---

## 5. 后端目录结构

```
backend/
├── app/
│   ├── main.py                    # FastAPI应用入口
│   ├── config.py                  # 基础配置
│   ├── database.py                # 数据库连接
│   ├── models/                    # 数据模型
│   │   ├── __init__.py
│   │   ├── knowledge.py           # 知识条目模型
│   │   ├── category.py            # 分类目录模型
│   │   ├── tag.py                 # 标签模型
│   │   ├── document.py            # 文档模型
│   │   ├── skill.py               # Skill模型
│   │   ├── model_config.py        # 模型配置
│   │   └── qa_history.py          # 问答历史
│   ├── schemas/                   # Pydantic请求/响应模型
│   │   ├── __init__.py
│   │   ├── knowledge.py
│   │   ├── skill.py
│   │   ├── model_config.py
│   │   └── qa.py
│   ├── routers/                   # API路由
│   │   ├── __init__.py
│   │   ├── knowledge.py           # 知识管理API
│   │   ├── category.py            # 分类管理API
│   │   ├── tag.py                 # 标签管理API
│   │   ├── skill.py               # Skill管理API
│   │   ├── model_config.py        # 模型配置API
│   │   ├── search.py              # 搜索API
│   │   ├── qa.py                  # 问答API
│   │   └── dashboard.py           # 首页统计API
│   ├── services/                  # 业务服务层
│   │   ├── __init__.py
│   │   ├── knowledge_service.py   # 知识管理服务
│   │   ├── file_parser.py         # 文件解析服务
│   │   ├── skill_service.py       # Skill管理服务
│   │   ├── skill_router.py        # Skill路由引擎
│   │   ├── model_service.py       # 模型配置服务
│   │   ├── llm_client.py          # LLM客户端抽象层
│   │   ├── rag_service.py         # RAG检索增强服务
│   │   ├── text_chunker.py        # 文本分块器
│   │   ├── embedding_service.py   # Embedding服务
│   │   ├── vector_store.py        # 向量存储服务
│   │   ├── prompt_assembler.py    # Prompt组装器
│   │   ├── qa_service.py          # 问答服务
│   │   ├── cache_service.py       # 问答缓存服务
│   │   └── data_adapter.py        # 数据源适配器接口（预留）
│   └── utils/
│       ├── __init__.py
│       ├── response.py            # 统一响应格式
│       └── crypto.py              # 密钥加密工具
├── data/                          # 数据目录
│   ├── knowledge.db               # SQLite数据库
│   ├── vectors/                   # ChromaDB向量数据
│   └── uploads/                  # 上传文件存储
├── requirements.txt
├── .env.example
└── run.py                         # 启动脚本
```

---

## 6. 前端目录结构

```
frontend/
├── src/
│   ├── App.vue
│   ├── main.ts
│   ├── router/
│   │   └── index.ts               # 路由配置
│   ├── stores/                    # Pinia状态管理
│   │   ├── auth.ts                # 认证状态
│   │   └── app.ts                 # 全局状态
│   ├── api/                       # API请求
│   │   ├── request.ts             # Axios封装
│   │   ├── knowledge.ts           # 知识管理API
│   │   ├── skill.ts               # Skill管理API
│   │   ├── model.ts               # 模型配置API
│   │   ├── search.ts              # 搜索API
│   │   ├── qa.ts                  # 问答API
│   │   └── dashboard.ts           # 首页统计API
│   ├── views/                     # 页面组件
│   │   ├── Dashboard.vue          # 首页仪表盘
│   │   ├── knowledge/
│   │   │   ├── List.vue           # 知识列表（快速预览+批量操作）
│   │   │   ├── Detail.vue         # 知识详情
│   │   │   ├── Edit.vue           # 知识编辑
│   │   │   └── Upload.vue         # 批量文档上传
│   │   ├── Search.vue             # 搜索页面（二次筛选+搜索历史）
│   │   ├── QA.vue                 # 智能问答（流式+反馈+追问）
│   │   ├── QAHistory.vue          # 问答历史
│   │   ├── skill/
│   │   │   ├── List.vue           # Skill列表
│   │   │   └── Edit.vue           # Skill编辑（含模板创建）
│   │   ├── ModelConfig.vue        # 模型配置管理
│   │   └── TokenStats.vue         # Token统计页面
│   ├── components/                # 公共组件
│   │   ├── MarkdownEditor.vue     # Markdown编辑器
│   │   ├── CategoryTree.vue       # 分类树形组件
│   │   ├── TagSelect.vue          # 标签选择组件
│   │   ├── KnowledgeCard.vue      # 知识卡片
│   │   └── FileUpload.vue         # 文件上传组件
│   ├── layouts/
│   │   └── MainLayout.vue         # 主布局
│   └── types/
│       └── index.ts               # TypeScript类型定义
├── package.json
├── vite.config.ts
└── tsconfig.json
```

---

## 7. API设计

### 7.1 知识管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/knowledge | 知识列表（分页、筛选） |
| GET | /api/knowledge/{id} | 知识详情 |
| POST | /api/knowledge | 创建知识条目 |
| PUT | /api/knowledge/{id} | 更新知识 |
| DELETE | /api/knowledge/{id} | 删除知识 |
| POST | /api/knowledge/upload | 上传文档 |

### 7.2 分类与标签 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/categories | 分类树 |
| POST | /api/categories | 创建分类 |
| PUT | /api/categories/{id} | 更新分类 |
| DELETE | /api/categories/{id} | 删除分类 |
| GET | /api/tags | 标签列表 |
| POST | /api/tags | 创建标签 |
| DELETE | /api/tags/{id} | 删除标签 |

### 7.3 Skill管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/skills | Skill列表（分类筛选） |
| GET | /api/skills/{id} | Skill详情 |
| POST | /api/skills | 创建Skill |
| PUT | /api/skills/{id} | 更新Skill |
| DELETE | /api/skills/{id} | 删除Skill |
| PUT | /api/skills/{id}/toggle | 启用/禁用Skill |
| POST | /api/skills/{id}/test | 测试Skill路由匹配 |
| GET | /api/skills/templates | Skill模板列表 |
| POST | /api/skills/from-template | 从模板创建Skill |

### 7.4 模型配置 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/models | 模型配置列表 |
| POST | /api/models | 新增模型配置 |
| PUT | /api/models/{id} | 更新模型配置 |
| DELETE | /api/models/{id} | 删除模型配置 |
| PUT | /api/models/{id}/activate | 切换启用模型 |
| POST | /api/models/{id}/test | 测试模型连通性 |

### 7.5 搜索与问答 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/search/semantic | 语义搜索（支持二次筛选参数） |
| GET | /api/search/keyword | 关键词搜索 |
| GET | /api/search/history | 搜索历史 |
| POST | /api/qa/ask | 智能问答（SSE流式返回） |
| POST | /api/qa/feedback | 答案反馈（点赞/点踩） |
| GET | /api/qa/suggestions | 快捷追问推荐 |
| GET | /api/qa/history | 问答历史 |
| DELETE | /api/qa/history/{id} | 删除问答记录 |

### 7.6 首页、统计与系统 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/dashboard/stats | 首页统计数据 |
| GET | /api/dashboard/recent-qa | 最近问答记录 |
| GET | /api/token-stats | Token统计（按时间/Skill/模型维度） |
| GET | /health | 健康检查 |
| GET | /docs | Swagger API文档 |

---

## 8. 数据库设计

### 8.1 ER关系图

```
┌───────────┐     ┌───────────────┐     ┌──────────┐
│ Category  │1───N│   Knowledge   │N───N│   Tag    │
│           │     │               │     │          │
│ id (PK)   │     │ id (PK)       │     │ id (PK)  │
│ name      │     │ title         │     │ name     │
│ parent_id │     │ content       │     └──────────┘
│ sort_order│     │ content_type  │
└───────────┘     │ category_id   │
                  │ source_type   │     ┌──────────────┐
                  │ source_file   │     │ KnowledgeTag│
                  └───────────────┘     │ knowledge_id │
                                        │ tag_id      │
                  ┌───────────────┐     └──────────────┘
                  │   Document    │
                  │ id (PK)       │
                  │ filename      │     ┌──────────────┐
                  │ file_path     │     │   Skill      │
                  │ file_type     │     │ id (PK)      │
                  │ knowledge_id  │     │ name         │
                  └───────────────┘     │ category     │
                                        │ function     │
                  ┌───────────────┐     │ trigger_kw   │
                  │  ModelConfig  │     │ prompt_tpl   │
                  │ id (PK)       │     │ knowledge_   │
                  │ name          │     │   scope     │
                  │ type          │     │ enabled      │
                  │ api_url       │     │ is_default   │
                  │ api_key       │     └──────────────┘
                  │ model_name    │
                  │ is_active     │     ┌──────────────┐
                  └───────────────┘     │  QAHistory   │
                                        │ id (PK)      │
                                        │ question     │
                  ┌───────────────┐     │ answer       │
                  │  TokenUsage   │     │ sources      │
                  │ id (PK)       │     │ skill_id     │
                  │ call_type     │     │ feedback     │
                  │ model_name    │     │ created_at   │
                  │ input_tokens  │     └──────────────┘
                  │ output_tokens │
                  │ duration_ms   │     ┌──────────────┐
                  │ skill_id      │     │ SearchHistory│
                  │ qa_history_id │     │ id (PK)      │
                  │ created_at    │     │ query        │
                  └───────────────┘     │ created_at   │
                                        └──────────────┘
```

### 8.2 初始数据

系统初始化时自动创建：
- 4个一级分类：制造运营、仓储物流、质量管理、设备管理
- 1个默认Skill（is_default=true，knowledge_scope为空，全量检索）
- 预设Skill模板：
  - 故障诊断模板（设备管理模块）
  - 保养提醒模板（设备管理模块）
  - 工艺指导模板（制造运营模块）
  - 质量标准查询模板（质量管理模块）
  - 库存查询模板（仓储物流模块）

---

## 9. 本地运行设计

### 9.1 环境配置（.env.example）
```bash
# 数据库
DATABASE_URL=sqlite:///./data/knowledge.db

# 向量数据库
VECTOR_DB_PATH=./data/vectors

# 文件存储
UPLOAD_PATH=./data/uploads

# 服务
HOST=0.0.0.0
PORT=8000
DEBUG=true
```

### 9.2 启动流程
```bash
# 后端
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py  # 或 uvicorn app.main:app --reload

# 前端
cd frontend
npm install
npm run dev
```

### 9.3 首次使用流程
1. 启动后端和前端服务
2. 系统检测无模型配置，弹窗引导配置LLM和Embedding模型的API地址和密钥
3. 测试模型连通性
4. 进入知识管理，批量上传文档或手动录入知识
5. 进入Skill管理，从模板创建或自定义Skill配置
6. 进入智能问答，开始使用
7. 在Token统计页面查看消耗情况

---

## 10. 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| RAG方案 | 自实现 | 轻量、可控、依赖少 |
| 向量数据库 | ChromaDB嵌入式 | 无需独立服务，本地可运行 |
| 数据库 | SQLite | 无需安装，MVP够用 |
| 模型接口 | OpenAI兼容格式 | 千问/MIMO均兼容，一套适配器通用 |
| 模型配置 | 存数据库 | Web界面管理，运行时热更新 |
| 问答输出 | SSE流式 | 提升用户体验，逐步展示 |
| 文件上传 | 批量+队列 | 提升效率，统一编辑元数据 |
| Token统计 | 独立模块 | 监控消耗，优化成本 |
| Skill模板 | 预设模板 | 降低使用门槛，快速创建 |
| Skill路由 | 关键词+语义+默认兜底 | 三级匹配，保证覆盖 |
| 前端框架 | Vue3 + Ant Design Vue | 企业级组件丰富，开发效率高 |
| 知识关联 | 不做 | 标签已足够，MVP简化 |
| 多轮对话 | 单轮+历史记录 | MVP简化，后续扩展 |

---

## 11. 预制数据设计

### 11.1 预制Skill（5个）

系统初始化时自动创建以下Skill，确保开箱即用：

#### Skill 1: 故障诊断（设备管理）
```json
{
  "name": "故障诊断",
  "description": "查询设备故障代码含义和处理方案",
  "category": "设备管理",
  "function": "故障诊断",
  "trigger_keywords": ["故障", "报错", "异常", "错误代码", "E0", "E1"],
  "trigger_patterns": ["E\\d+", "故障代码.*", ".*报警.*"],
  "prompt_template": "你是设备故障诊断专家。根据以下知识内容回答故障相关问题。\n\n知识内容：\n{context}\n\n问题：{question}\n\n请给出故障原因分析和处理方案。",
  "knowledge_scope": {"category_ids": [4], "tag_ids": [1]},
  "enabled": true,
  "is_default": false
}
```

#### Skill 2: 保养维护（设备管理）
```json
{
  "name": "保养维护",
  "description": "设备保养计划、维护周期和保养流程",
  "category": "设备管理",
  "function": "保养维护",
  "trigger_keywords": ["保养", "维护", "检修", "周期", "润滑"],
  "trigger_patterns": ["保养.*", "维护.*周期"],
  "prompt_template": "你是设备保养维护专家。根据以下知识内容回答保养相关问题。\n\n知识内容：\n{context}\n\n问题：{question}\n\n请给出详细的保养计划和维护步骤。",
  "knowledge_scope": {"category_ids": [4], "tag_ids": [2]},
  "enabled": true,
  "is_default": false
}
```

#### Skill 3: 工艺指导（制造运营）
```json
{
  "name": "工艺指导",
  "description": "加工工艺参数、工序步骤和操作规程",
  "category": "制造运营",
  "function": "工艺指导",
  "trigger_keywords": ["工艺", "工序", "参数", "操作规程", "加工"],
  "trigger_patterns": ["工艺.*", "加工.*参数"],
  "prompt_template": "你是制造工艺专家。根据以下知识内容回答工艺相关问题。\n\n知识内容：\n{context}\n\n问题：{question}\n\n请给出详细的工艺参数和操作步骤。",
  "knowledge_scope": {"category_ids": [1]},
  "enabled": true,
  "is_default": false
}
```

#### Skill 4: 质量检验（质量管理）
```json
{
  "name": "质量检验",
  "description": "产品质量检验标准、检验方法和合格判定",
  "category": "质量管理",
  "function": "质量检验",
  "trigger_keywords": ["质量", "检验", "合格", "不合格", "标准", "偏差"],
  "trigger_patterns": ["质量.*标准", "检验.*"],
  "prompt_template": "你是质量管理专家。根据以下知识内容回答质量检验相关问题。\n\n知识内容：\n{context}\n\n问题：{question}\n\n请给出检验标准和判定依据。",
  "knowledge_scope": {"category_ids": [3]},
  "enabled": true,
  "is_default": false
}
```

#### Skill 5: 默认通用问答（兜底）
```json
{
  "name": "通用问答",
  "description": "默认Skill，在无法匹配其他Skill时使用，全量知识库检索",
  "category": "通用",
  "function": "通用问答",
  "trigger_keywords": [],
  "trigger_patterns": [],
  "prompt_template": "你是MOM系统知识助手。根据以下知识内容回答问题。\n\n知识内容：\n{context}\n\n问题：{question}",
  "knowledge_scope": {},
  "enabled": true,
  "is_default": true
}
```

### 11.2 预制测试文档（6个）

系统提供以下测试文档，用于开发完成后的完整功能验证：

#### 文档1: 设备故障代码手册.pdf
- 分类：设备管理
- 类型：标准文档
- 标签：故障代码
- 内容摘要：
  ```
  E01 故障：电机过热
  - 原因：冷却系统故障或负载过大
  - 处理：1.停机检查冷却风扇 2.检查电机负载 3.清理散热器
  
  E02 故障：传感器异常
  - 原因：传感器接线松动或损坏
  - 处理：1.检查接线 2.更换传感器 3.重新校准
  
  E03 故障：气压不足
  - 原因：气路泄漏或空压机故障
  - 处理：1.检查气路密封 2.检查空压机 3.补充气压
  
  E04 故障：PLC通信中断
  - 原因：通信线缆断开或模块故障
  - 处理：1.检查通信线缆 2.重启通信模块 3.检查网络配置
  ```

#### 文档2: 设备保养计划规程.docx
- 分类：设备管理
- 类型：标准文档
- 标签：保养
- 内容摘要：
  ```
  日常保养（每日）：
  1. 开机前检查设备外观，清洁表面
  2. 检查油位、水位，不足时补充
  3. 检查气压是否正常（0.5-0.7MPa）
  4. 空载试运行3分钟，检查无异响
  
  周保养（每周）：
  1. 清洁导轨和丝杠，涂抹润滑脂
  2. 检查紧固件有无松动
  3. 检查电气连接是否可靠
  4. 校准传感器零点
  
  月保养（每月）：
  1. 更换液压油和润滑油
  2. 检查皮带张紧度，必要时更换
  3. 清洁电气柜，检查散热风扇
  4. 全面检查安全装置
  ```

#### 文档3: 数控加工工艺规程.docx
- 分类：制造运营
- 类型：标准文档
- 标签：工艺
- 内容摘要：
  ```
  工序1：粗加工
  - 主轴转速：800 rpm
  - 进给速度：200 mm/min
  - 切削深度：3mm
  - 刀具：φ10立铣刀
  
  工序2：半精加工
  - 主轴转速：1200 rpm
  - 进给速度：150 mm/min
  - 切削深度：1mm
  - 刀具：φ8立铣刀
  
  工序3：精加工
  - 主轴转速：2000 rpm
  - 进给速度：100 mm/min
  - 切削深度：0.5mm
  - 刀具：φ6立铣刀
  
  注意事项：
  1. 粗加工后需冷却5分钟再进行半精加工
  2. 精加工前需校准刀具长度补偿
  ```

#### 文档4: 产品质量检验标准.xlsx
- 分类：质量管理
- 类型：标准文档
- 标签：质量标准
- 内容摘要：
  ```
  检验项目        标准值      公差       检验方法
  外径尺寸      50.00mm    ±0.02mm    千分尺测量
  内径尺寸      30.00mm    ±0.01mm    内径千分尺
  长度          100.00mm   ±0.1mm     游标卡尺
  表面粗糙度    Ra1.6       -          粗糙度仪
  垂直度        0.02mm     -          三坐标测量
  
  判定规则：
  - 关键项目（外径、内径）不合格 → 产品不合格
  - 一般项目（长度、粗糙度）2项以上不合格 → 产品不合格
  - 辅助项目（垂直度）仅记录，不判定
  ```

#### 文档5: 仓库管理制度.pdf
- 分类：仓储物流
- 类型：标准文档
- 标签：仓储管理
- 内容摘要：
  ```
  入库流程：
  1. 供应商送货 → 核对采购订单 → 质量检验 → 入库登记 → 上架
  2. 入库需在24小时内完成登记
  3. 不合格品进入退货区，48小时内处理
  
  出库流程：
  1. 领料申请 → 审批 → 拣货 → 复核 → 发料
  2. 生产用料需提前1天申请
  3. 紧急用料需车间主任签字
  
  盘点制度：
  1. 每日循环盘点（A类物料每日，B类每周，C类每月）
  2. 每季度全面盘点一次
  3. 盘点差异超过0.5%需查明原因
  ```

#### 文档6: 设备操作经验记录.md
- 分类：设备管理
- 类型：经验知识
- 标签：操作经验
- 内容摘要：
  ```
  经验1：CNC机床换刀异常处理
  - 现象：换刀时出现E04报警
  - 原因：刀库位置传感器积灰
  - 解决：清洁传感器后恢复正常
  - 预防：每周清洁一次刀库传感器
  
  经验2：液压系统压力波动
  - 现象：压力表指针波动0.2-0.3MPa
  - 原因：蓄能器氮气压力不足
  - 解决：补充氮气至6MPa
  - 预防：每季度检查蓄能器压力
  
  经验3：加工表面粗糙度超标
  - 现象：Ra值从1.6升至3.2
  - 原因：刀具磨损或切削液浓度不足
  - 解决：1.更换刀具 2.调整切削液浓度至8%
  - 预防：每班次检查刀具磨损，每周检测切削液浓度
  ```

### 11.3 预制标签

| 标签名 | 关联文档 |
|--------|---------|
| 故障代码 | 文档1 |
| 保养 | 文档2 |
| 工艺 | 文档3 |
| 质量标准 | 文档4 |
| 仓储管理 | 文档5 |
| 操作经验 | 文档6 |

---

## 12. 测试Case清单

### 12.1 知识管理测试

| Case ID | 测试场景 | 操作步骤 | 预期结果 |
|---------|---------|---------|---------|
| TC-KM-01 | 单文件上传 | 上传设备故障代码手册.pdf | 解析成功，创建知识条目，向量索引生成 |
| TC-KM-02 | 批量文件上传 | 拖拽3个文件同时上传 | 上传队列展示3个文件，全部解析成功 |
| TC-KM-03 | 上传后批量编辑 | 批量上传后统一设置分类和标签 | 所有上传文档关联相同分类和标签 |
| TC-KM-04 | 手动录入知识 | 表单录入标题、内容、分类、标签 | 知识条目创建成功，向量索引生成 |
| TC-KM-05 | Markdown编辑器 | 使用编辑器工具栏格式化内容 | 内容正确渲染，预览正常 |
| TC-KM-06 | 编辑知识 | 修改已有知识内容 | 内容更新，向量索引自动重建 |
| TC-KM-07 | 删除知识 | 删除一条知识条目 | 记录删除，向量索引自动移除 |
| TC-KM-08 | 知识列表分页 | 数据>10条时翻页 | 分页正确，页码导航正常 |
| TC-KM-09 | 快速预览 | 点击列表行预览按钮 | 展开内容摘要（前200字） |
| TC-KM-10 | 批量删除 | 选中3条知识批量删除 | 全部删除成功 |
| TC-KM-11 | 批量打标签 | 选中多条批量添加标签 | 所有选中条目添加标签成功 |
| TC-KM-12 | 按分类筛选 | 选择"设备管理"分类筛选 | 仅展示设备管理分类的知识 |
| TC-KM-13 | 按标签筛选 | 选择"故障代码"标签筛选 | 仅展示含此标签的知识 |

### 12.2 Skill管理测试

| Case ID | 测试场景 | 操作步骤 | 预期结果 |
|---------|---------|---------|---------|
| TC-SK-01 | 查看预制Skill | 进入Skill管理页面 | 展示5个预制Skill |
| TC-SK-02 | 按模块筛选 | 选择"设备管理"筛选 | 展示故障诊断、保养维护2个Skill |
| TC-SK-03 | 创建Skill | 新建Skill填写完整配置 | 保存成功，列表展示 |
| TC-SK-04 | 从模板创建 | 点击"从模板创建"，选择模板 | 预填配置，修改后保存成功 |
| TC-SK-05 | 编辑Skill | 修改Prompt模板 | 更新成功 |
| TC-SK-06 | 禁用Skill | 禁用"故障诊断"Skill | 状态变为禁用 |
| TC-SK-07 | 启用Skill | 启用已禁用的Skill | 状态变为启用 |
| TC-SK-08 | 删除Skill | 删除自定义Skill | 删除成功，预制Skill不可删 |
| TC-SK-09 | Skill路由测试 | 输入"设备E01故障"测试 | 匹配到"故障诊断"Skill |
| TC-SK-10 | 知识范围关联 | 为Skill关联分类和标签 | 保存成功，问答时仅检索关联范围 |

### 12.3 Skill路由引擎测试

| Case ID | 测试场景 | 输入 | 预期匹配Skill |
|---------|---------|------|--------------|
| TC-RT-01 | 关键词精确匹配 | "设备E01故障怎么处理" | 故障诊断 |
| TC-RT-02 | 关键词模糊匹配 | "机床报错了" | 故障诊断 |
| TC-RT-03 | 正则模式匹配 | "E03错误代码含义" | 故障诊断 |
| TC-RT-04 | 保养关键词匹配 | "设备保养周期是多久" | 保养维护 |
| TC-RT-05 | 工艺关键词匹配 | "精加工主轴转速多少" | 工艺指导 |
| TC-RT-06 | 质量关键词匹配 | "外径公差是多少" | 质量检验 |
| TC-RT-07 | 语义匹配（无关键词） | "刀具磨损了怎么办" | 默认通用问答 |
| TC-RT-08 | 无匹配走默认 | "今天的天气怎样" | 默认通用问答 |
| TC-RT-09 | 多Skill命中取最优 | "设备保养时发现E01故障" | 故障诊断（优先级高） |
| TC-RT-10 | 禁用Skill不参与匹配 | 禁用故障诊断后输入"E01故障" | 默认通用问答 |

### 12.4 智能搜索测试

| Case ID | 测试场景 | 输入 | 预期结果 |
|---------|---------|------|---------|
| TC-SE-01 | 语义搜索 | "电机过热怎么办" | 返回E01故障相关内容 |
| TC-SE-02 | 语义搜索 | "如何保养导轨" | 返回周保养相关内容 |
| TC-SE-03 | 关键词搜索 | "E01" | 返回包含E01的知识 |
| TC-SE-04 | 搜索结果排序 | 多结果时检查排序 | 按相关度降序排列 |
| TC-SE-05 | 搜索结果高亮 | 关键词搜索 | 匹配词高亮显示 |
| TC-SE-06 | 搜索结果分页 | 搜索结果>10条 | 分页正常 |
| TC-SE-07 | 二次筛选-分类 | 搜索后选择"设备管理" | 结果缩小为设备管理分类 |
| TC-SE-08 | 二次筛选-标签 | 搜索后选择"故障代码"标签 | 结果缩小为含此标签 |
| TC-SE-09 | 搜索历史记录 | 搜索后查看历史 | 展示最近搜索记录 |
| TC-SE-10 | 搜索历史重复 | 点击历史记录搜索 | 重新执行该搜索 |

### 12.5 智能问答测试

| Case ID | 测试场景 | 输入 | 预期结果 |
|---------|---------|------|---------|
| TC-QA-01 | Skill路由问答 | "设备E01故障怎么处理？" | 匹配故障诊断Skill，返回处理方案 |
| TC-QA-02 | 流式输出 | 提问后观察 | 答案逐步显示（SSE） |
| TC-QA-03 | 答案来源标注 | 查看答案来源 | 标注来源文档和片段 |
| TC-QA-04 | 匹配Skill展示 | 查看答案信息 | 显示匹配的Skill名称 |
| TC-QA-05 | Token展示 | 查看答案信息 | 显示本次token消耗 |
| TC-QA-06 | 答案反馈-赞 | 点击"有用" | 反馈记录成功 |
| TC-QA-07 | 答案反馈-踩 | 点击"无用" | 反馈记录成功 |
| TC-QA-08 | 追问推荐 | 答案返回后 | 展示2-3个推荐问题 |
| TC-QA-09 | 点击追问推荐 | 点击推荐问题 | 直接发起该问题提问 |
| TC-QA-10 | 默认Skill问答 | "仓库盘点制度" | 默认Skill检索全量库回答 |
| TC-QA-11 | 跨模块问答 | "设备故障导致质量问题" | 默认Skill全量检索回答 |
| TC-QA-12 | 无相关知识问答 | "公司年报数据" | 返回"未找到相关知识"提示 |

### 12.6 问答历史测试

| Case ID | 测试场景 | 操作步骤 | 预期结果 |
|---------|---------|---------|---------|
| TC-HI-01 | 查看历史列表 | 进入问答历史页面 | 展示历史记录列表 |
| TC-HI-02 | 搜索历史 | 输入"故障"搜索 | 返回包含"故障"的历史记录 |
| TC-HI-03 | 历史分页 | 历史>10条时翻页 | 分页正确 |
| TC-QA-04 | 删除历史 | 删除一条记录 | 删除成功 |
| TC-HI-05 | 历史详情 | 点击历史记录 | 展示完整问答内容 |

### 12.7 Token统计测试

| Case ID | 测试场景 | 操作步骤 | 预期结果 |
|---------|---------|---------|---------|
| TC-TK-01 | Token记录 | 执行一次问答 | TokenUsage表新增记录 |
| TC-TK-02 | 统计页面 | 进入Token统计页面 | 展示统计卡片和图表 |
| TC-TK-03 | 按时间筛选 | 选择"今日" | 展示今日token消耗 |
| TC-TK-04 | 按Skill筛选 | 选择"故障诊断" | 展示该Skill的token消耗 |
| TC-TK-05 | 趋势图表 | 查看近7天趋势 | 折线图正常展示 |
| TC-TK-06 | 按类型分布 | 查看调用类型分布 | 饼图展示问答/Embedding分布 |

### 12.8 模型配置测试

| Case ID | 测试场景 | 操作步骤 | 预期结果 |
|---------|---------|---------|---------|
| TC-MC-01 | 首次引导 | 首次启动无模型配置 | 弹窗引导配置 |
| TC-MC-02 | 新增LLM配置 | 填写千问API信息 | 保存成功 |
| TC-MC-03 | 新增Embedding配置 | 填写Embedding API信息 | 保存成功 |
| TC-MC-04 | 模型连通性测试 | 点击测试按钮 | 返回连通状态和延迟 |
| TC-MC-05 | 切换启用LLM | 启用MIMO，停用千问 | 切换成功，问答使用新模型 |
| TC-MC-06 | 密钥脱敏 | 查看模型列表 | API Key脱敏显示 |
| TC-MC-07 | 删除模型配置 | 删除未启用的模型 | 删除成功 |
| TC-MC-08 | 删除启用中模型 | 尝试删除启用中模型 | 提示先切换其他模型 |
| TC-MC-09 | 配置热更新 | 修改API地址后问答 | 新配置立即生效 |

### 12.9 系统辅助功能测试

| Case ID | 测试场景 | 操作步骤 | 预期结果 |
|---------|---------|---------|---------|
| TC-SY-01 | 首页统计卡片 | 进入首页 | 展示知识数、Skill数、今日问答数 |
| TC-SY-02 | 首页最近问答 | 查看首页最近问答 | 展示最近5条问答记录 |
| TC-SY-03 | 面包屑导航 | 进入知识详情 | 面包屑显示层级路径 |
| TC-SY-04 | 面包屑跳转 | 点击面包屑中的分类 | 跳转到该分类列表 |
| TC-SY-05 | 健康检查 | 访问/health | 返回各组件状态 |
| TC-SY-06 | Swagger文档 | 访问/docs | 展示API交互文档 |
| TC-SY-07 | 相关推荐 | 查看知识详情 | 侧边栏展示同分类/同标签知识 |
| TC-SY-08 | 推荐跳转 | 点击推荐知识 | 跳转到该知识详情 |

### 12.10 端到端闭环测试

| Case ID | 测试场景 | 操作步骤 | 预期结果 |
|---------|---------|---------|---------|
| TC-E2E-01 | 完整流程闭环 | 1.上传6个测试文档 → 2.检查Skill配置 → 3.搜索知识 → 4.智能问答 → 5.查看Token统计 → 6.查看问答历史 | 全流程通过 |
| TC-E2E-02 | Skill路由闭环 | 1.提问"设备E01故障" → 2.验证匹配故障诊断Skill → 3.验证答案来源 → 4.验证Token记录 | 全流程通过 |
| TC-E2E-03 | 模型切换闭环 | 1.用千问问答 → 2.切换到MIMO → 3.再次问答 → 4.验证Token统计按模型分类 | 全流程通过 |
| TC-E2E-04 | 缓存命中闭环 | 1.提问"设备E01故障" → 2.再次提问相同问题 → 3.验证第二次命中缓存(无Token消耗) | 全流程通过 |
| TC-E2E-05 | 向量索引同步闭环 | 1.编辑已有知识 → 2.搜索验证新内容 → 3.删除知识 → 4.搜索验证已移除 | 全流程通过 |

### 12.11 异常场景测试

| Case ID | 测试场景 | 操作步骤 | 预期结果 |
|---------|---------|---------|---------|
| TC-EX-01 | 上传不支持的格式 | 上传.txt文件 | 提示不支持该格式 |
| TC-EX-02 | 上传超大文件 | 上传>50MB文件 | 提示文件过大或分批上传 |
| TC-EX-03 | 模型API不可达 | 配置错误API地址后问答 | 返回模型连接错误提示 |
| TC-QA-04 | 空问题提交 | 不输入问题直接发送 | 按钮禁用或提示输入 |
| TC-EX-05 | 删除有知识的分类 | 删除含知识的分类 | 提示先转移知识 |
| TC-EX-06 | 无模型配置时问答 | 未配置模型直接问答 | 引导先配置模型 |
