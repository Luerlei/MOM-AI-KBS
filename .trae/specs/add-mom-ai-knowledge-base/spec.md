# MOM系统AI知识库平台 Spec

## Why
制造企业MOM系统（制造运营、仓储物流、质量管理、设备管理）积累了大量标准文档、经验知识、培训资料和数据报表，但缺乏统一的智能化管理和检索手段。一线操作工、技术人员、管理人员和培训人员需要快速准确地获取所需知识。

本平台采用 **Skill路由 + 自实现轻量RAG** 架构，不依赖LangChain等重型框架，通过Skill管理机制精准匹配用户意图与知识范围，显著降低token消耗和对模型性能的要求，实现轻量化MVP。

## What Changes
- 新建 Python + FastAPI 后端服务，提供知识管理、Skill管理、AI问答、搜索、推荐等API
- 新建 Vue3 + Ant Design 前端界面，支持知识浏览、搜索、问答交互、Skill管理、模型配置管理
- 实现混合知识组织体系：目录分类 + 多维标签（MVP不建知识关联）
- 实现 **Skill管理系统**：支持Skill的增删改查，按模块/功能等维度分类，路由用户意图
- 实现 **模型配置管理**：Web界面维护模型API地址、密钥，支持多模型配置和运行时切换
- **自实现轻量RAG**：直接使用ChromaDB SDK + 模型API，不依赖LangChain/LlamaIndex
- 实现文档上传与解析，支持PDF、Word、Excel、Markdown等格式
- 预留DB/API数据源适配器接口（MVP仅定义接口，不实现具体适配器）

## Impact
- Affected specs: 无（全新项目）
- Affected code: 全新项目，无现有代码影响

## 设计原则
1. **轻量化优先**：MVP阶段保证功能完整性，实现可以简化但功能不能缺失
2. **Skill驱动**：通过Skill路由机制降低token消耗和模型性能要求
3. **自实现RAG**：不依赖LangChain/LlamaIndex，直接用ChromaDB + 模型API，依赖最少
4. **本地可运行**：MVP需在开发电脑上可正常运行
5. **模型无关**：平台不关心模型选型和环境，通过统一API接口调用模型

## ADDED Requirements

### Requirement: 知识内容管理
系统 SHALL 支持知识内容的创建、编辑、删除、查看，支持多种内容类型（标准文档、经验知识、培训资料、数据报表）。

#### Scenario: 上传文档
- **WHEN** 用户上传PDF/Word/Excel/Markdown文件
- **THEN** 系统解析文件内容，自动提取文本，存储到知识库

#### Scenario: 手动录入知识条目
- **WHEN** 用户通过表单录入知识标题、内容、标签
- **THEN** 系统保存知识条目并建立向量索引

### Requirement: 混合知识组织
系统 SHALL 支持目录分类和多维标签两种组织方式。

#### Scenario: 目录分类浏览
- **WHEN** 用户按MOM模块（制造运营/仓储物流/质量管理/设备管理）浏览
- **THEN** 系统展示树形目录结构，支持逐级展开

#### Scenario: 标签筛选
- **WHEN** 用户选择一个或多个标签进行筛选
- **THEN** 系统返回匹配所有选中标签的知识条目

### Requirement: Skill管理系统（核心）
系统 SHALL 提供Skill管理功能，支持Skill的创建、查看、编辑、删除，按模块和功能等维度分类组织Skill。每个Skill定义特定的知识范围、Prompt模板和触发规则，用于路由用户意图并精准检索知识。

#### Scenario: 创建Skill
- **WHEN** 管理员在Skill管理页面创建新Skill
- **THEN** 系统保存Skill配置，包括名称、描述、分类、触发关键词、Prompt模板、关联知识范围

#### Scenario: Skill分类管理
- **WHEN** 管理员查看Skill列表
- **THEN** 系统按模块（制造运营/仓储物流/质量管理/设备管理）和功能维度分类展示Skill

#### Scenario: 编辑Skill
- **WHEN** 管理员编辑已有Skill
- **THEN** 系统更新Skill配置，支持修改Prompt模板、触发条件、知识范围

#### Scenario: 删除Skill
- **WHEN** 管理员删除Skill
- **THEN** 系统移除Skill配置，相关路由规则失效

#### Scenario: Skill路由
- **WHEN** 用户提出问题
- **THEN** 系统根据问题意图匹配对应Skill，仅在Skill关联的知识范围内检索，使用Skill的Prompt模板生成答案

### Requirement: 智能搜索
系统 SHALL 支持语义搜索和关键词搜索。

#### Scenario: 语义搜索
- **WHEN** 用户输入自然语言查询
- **THEN** 系统返回语义最相关的Top-K知识片段，按相关度排序

#### Scenario: 关键词搜索
- **WHEN** 用户输入关键词
- **THEN** 系统通过数据库LIKE查询返回包含该关键词的知识条目

### Requirement: 智能问答
系统 SHALL 基于知识库内容回答用户问题，通过Skill路由精准检索，生成准确、有据可查的答案。

#### Scenario: 知识问答
- **WHEN** 用户提出问题
- **THEN** 系统匹配Skill，在Skill限定的知识范围内检索相关内容，结合AI生成答案，并标注答案来源

#### Scenario: 单轮问答与历史记录
- **WHEN** 用户提问
- **THEN** 系统返回答案，并将问答记录保存到历史，用户可查看历史问答记录

#### Scenario: 无匹配Skill
- **WHEN** 用户问题无法匹配到任何Skill
- **THEN** 系统使用默认Skill在全量知识库中检索回答

### Requirement: 相关内容推荐
系统 SHALL 根据用户当前浏览的内容，推荐同分类或同标签的相关知识。

#### Scenario: 相关内容推荐
- **WHEN** 用户查看某条知识详情
- **THEN** 系统在侧边栏展示同分类或共享标签的其他知识条目

### Requirement: Token消耗优化
系统 SHALL 通过Skill路由限定检索范围、自实现轻量RAG检索、问答缓存等手段降低token消耗。

#### Scenario: Skill限定检索
- **WHEN** 用户提问且匹配到Skill
- **THEN** 系统仅在Skill关联的知识范围内检索，减少上下文token

#### Scenario: 轻量RAG检索
- **WHEN** 用户提问
- **THEN** 系统仅检索最相关的Top-K知识片段作为上下文，而非全量文档

#### Scenario: 答案缓存
- **WHEN** 用户提出与之前相同或相似的问题
- **THEN** 系统直接返回缓存的答案，不调用AI模型

### Requirement: 模型配置管理（核心）
系统 SHALL 提供模型配置管理功能，支持通过Web界面维护AI模型的API地址、密钥、模型名称等配置，支持多模型配置并指定当前启用模型。配置修改后无需重启服务即可生效。

#### Scenario: 查看模型配置列表
- **WHEN** 管理员进入模型配置管理页面
- **THEN** 系统展示已配置的模型列表（LLM模型、Embedding模型），包含名称、类型、API地址、启用状态

#### Scenario: 新增模型配置
- **WHEN** 管理员在配置页面新增模型，填写名称、类型（LLM/Embedding）、API地址、密钥、模型名称
- **THEN** 系统保存模型配置，支持后续启用

#### Scenario: 编辑模型配置
- **WHEN** 管理员编辑已有模型配置的API地址或密钥
- **THEN** 系统更新配置，新配置立即生效

#### Scenario: 删除模型配置
- **WHEN** 管理员删除某个模型配置
- **THEN** 系统移除该模型配置，若删除的是启用中模型则提示先切换其他模型

#### Scenario: 切换启用模型
- **WHEN** 管理员将某个模型设置为启用
- **THEN** 系统将该模型作为当前使用的模型，其他同类模型自动设为未启用

#### Scenario: 模型连通性测试
- **WHEN** 管理员在配置页面点击测试按钮
- **THEN** 系统使用该模型配置发送测试请求，返回连通状态和延迟

### Requirement: 模型接口抽象
系统 SHALL 通过统一的API接口调用AI模型，模型配置来源于模型配置管理，支持运行时切换。

### Requirement: 系统首页/仪表盘
系统 SHALL 提供系统首页，展示知识库概况和快捷入口。

#### Scenario: 查看首页
- **WHEN** 用户进入系统首页
- **THEN** 系统展示统计卡片（知识总数、Skill数、今日问答数、文档数）和最近问答记录

### Requirement: 问答历史管理
系统 SHALL 提供问答历史记录的查看、搜索和删除功能。

#### Scenario: 查看问答历史
- **WHEN** 用户进入问答历史页面
- **THEN** 系统展示问答记录列表（问题、答案摘要、时间、匹配Skill）

#### Scenario: 搜索问答历史
- **WHEN** 用户按关键词搜索问答历史
- **THEN** 系统返回匹配的问答记录

#### Scenario: 删除问答历史
- **WHEN** 用户删除某条问答记录
- **THEN** 系统移除该记录

### Requirement: 知识内容编辑器
系统 SHALL 提供Markdown编辑器用于知识内容录入和编辑，支持实时预览。

#### Scenario: 编辑知识内容
- **WHEN** 用户在知识编辑表单中编辑内容
- **THEN** 系统提供Markdown编辑器，支持工具栏（标题、列表、代码块、加粗等）和实时预览

### Requirement: 向量索引自动同步
系统 SHALL 在知识条目创建、更新、删除时自动同步向量索引，保持数据一致性。

#### Scenario: 新增知识同步索引
- **WHEN** 用户新建知识条目或上传文档
- **THEN** 系统自动将文本分块并生成Embedding存入向量数据库

#### Scenario: 更新知识同步索引
- **WHEN** 用户编辑知识内容
- **THEN** 系统自动删除旧向量，重新生成新向量存入向量数据库

#### Scenario: 删除知识同步索引
- **WHEN** 用户删除知识条目
- **THEN** 系统自动从向量数据库中移除对应向量

### Requirement: 搜索结果分页
系统 SHALL 对搜索结果和列表查询支持分页展示。

#### Scenario: 分页展示
- **WHEN** 搜索结果或列表数据超过单页限制
- **THEN** 系统分页返回结果，支持页码导航

### Requirement: API文档
系统 SHALL 提供自动生成的API文档（Swagger UI），方便开发调试。

#### Scenario: 访问API文档
- **WHEN** 开发者访问 /docs 路径
- **THEN** 系统展示FastAPI自动生成的Swagger UI交互式文档

### Requirement: 健康检查
系统 SHALL 提供健康检查端点，用于验证系统运行状态。

#### Scenario: 健康检查
- **WHEN** 访问 /health 端点
- **THEN** 系统返回运行状态（数据库连接、向量数据库连接、模型配置状态）

### Requirement: 数据源扩展性
系统 SHALL 预留数据源适配器接口，支持后续从ERP/MES/WMS等系统导入数据。

#### Scenario: 数据源适配器
- **WHEN** 需要对接新的外部数据源
- **THEN** 通过实现数据源适配器接口（fetch方法），无需修改核心代码

### Requirement: 批量文件上传
系统 SHALL 支持批量多文件上传，提供上传队列管理。

#### Scenario: 批量上传
- **WHEN** 用户拖拽多个文件到上传区域
- **THEN** 系统展示上传队列（文件名、大小、状态、进度），并行上传

#### Scenario: 上传后批量编辑元数据
- **WHEN** 文件上传完成
- **THEN** 系统展示批量编辑界面，用户可统一设置分类和标签后提交

### Requirement: 答案流式输出
系统 SHALL 支持问答答案流式输出（SSE），逐步展示生成内容。

#### Scenario: 流式回答
- **WHEN** 用户提问
- **THEN** 系统通过SSE逐步返回答案内容，前端实时渲染

### Requirement: 搜索结果二次筛选
系统 SHALL 支持搜索结果按分类、标签、时间范围二次筛选。

#### Scenario: 搜索后筛选
- **WHEN** 用户在搜索结果页选择分类或标签
- **THEN** 系统在当前搜索结果范围内进一步筛选

### Requirement: 知识列表快速预览
系统 SHALL 支持知识列表行的快速预览，无需进入详情页。

#### Scenario: 快速预览
- **WHEN** 用户在知识列表点击预览按钮
- **THEN** 系统展开内容摘要（前200字+元数据）

### Requirement: 知识批量操作
系统 SHALL 支持知识条目的批量删除、批量打标签、批量移动分类。

#### Scenario: 批量操作
- **WHEN** 用户选中多条知识后选择批量操作
- **THEN** 系统执行批量删除/打标签/移动分类，并显示操作结果

### Requirement: 答案反馈
系统 SHALL 支持用户对问答答案进行反馈（有用/无用）。

#### Scenario: 答案反馈
- **WHEN** 用户对答案点击"有用"或"无用"
- **THEN** 系统记录反馈，用于后续优化

### Requirement: 快捷追问建议
系统 SHALL 在问答完成后，基于当前问答推荐相关问题。

#### Scenario: 推荐追问
- **WHEN** 系统返回答案后
- **THEN** 展示2-3个推荐追问问题，用户可点击直接提问

### Requirement: Skill模板
系统 SHALL 提供预设Skill模板，支持一键创建后修改。

#### Scenario: 使用模板创建Skill
- **WHEN** 管理员点击"从模板创建"
- **THEN** 系统展示模板列表，选择后预填Skill配置，用户修改后保存

### Requirement: 搜索历史
系统 SHALL 记录用户搜索历史，支持快捷重复搜索。

#### Scenario: 查看搜索历史
- **WHEN** 用户在搜索页查看历史
- **THEN** 系统展示最近搜索记录，点击可直接重新搜索

### Requirement: Token统计
系统 SHALL 记录每次AI调用的token消耗，提供统计页面。

#### Scenario: Token消耗记录
- **WHEN** 系统调用AI模型（问答、Embedding、摘要）
- **THEN** 系统记录调用类型、输入token、输出token、耗时、关联Skill

#### Scenario: Token统计页面
- **WHEN** 管理员进入Token统计页面
- **THEN** 系统展示按时间/Skill/模型维度的token消耗统计和趋势图表

### Requirement: 首次使用引导
系统 SHALL 在首次启动检测到无模型配置时，引导用户完成初始配置。

#### Scenario: 首次引导
- **WHEN** 系统首次启动且无模型配置
- **THEN** 前端弹窗引导用户配置模型API，配置完成后可正常使用

### Requirement: 面包屑导航
系统 SHALL 在内容区顶部展示面包屑导航，指示当前页面层级。

#### Scenario: 面包屑导航
- **WHEN** 用户浏览知识详情
- **THEN** 顶部展示"知识管理 / 设备管理 / 知识详情"面包屑，可点击跳转

## 技术架构

### 后端技术栈
- Python 3.10+
- FastAPI
- SQLAlchemy + SQLite（MVP阶段，开发电脑可运行）
- ChromaDB（向量数据库，嵌入式，无需独立服务）
- httpx（调用模型API）
- 文件解析：PyPDF2、python-docx、openpyxl
- **不依赖** LangChain / LlamaIndex

### 前端技术栈
- Vue 3 + TypeScript
- Ant Design Vue
- Vue Router
- Pinia（状态管理）
- Axios

### 自实现轻量RAG核心组件
```
1. 文本分块器（TextChunker）：按段落+长度分块
2. Embedding服务：通过httpx调用模型API
3. 向量存储：ChromaDB嵌入式
4. 检索器：ChromaDB similarity_search
5. Prompt组装器：Skill模板 + 检索结果
6. LLM调用：通过httpx调用模型API
```

### AI模型接口
- 统一LLM接口抽象层，模型配置存储在数据库，通过Web界面管理
- 支持多模型配置（LLM和Embedding），通过界面切换启用模型
- 本地模型：千问（Qwen），通过模型配置页面填写API地址和密钥
- 在线模型：MIMO，通过模型配置页面填写API地址和密钥
- Embedding模型：通过模型配置页面填写API地址和密钥
- 配置修改后运行时生效，无需重启服务

### 模型配置数据结构
```
ModelConfig {
  id: 唯一标识
  name: 配置名称（如：千问本地、MIMO在线）
  type: 模型类型（LLM / Embedding）
  api_url: API地址
  api_key: 密钥（加密存储）
  model_name: 模型名称（如：qwen2.5-7b、mimo-v1）
  is_active: 是否启用（同类型仅一个启用）
  created_at: 创建时间
  updated_at: 更新时间
}
```

### Skill数据结构
```
Skill {
  id: 唯一标识
  name: Skill名称
  description: Skill描述
  category: 分类（模块维度：制造运营/仓储物流/质量管理/设备管理）
  function: 功能维度（如：故障查询/保养提醒/工艺指导等）
  trigger_keywords: 触发关键词列表
  trigger_patterns: 触发模式（正则或语义匹配）
  prompt_template: Prompt模板
  knowledge_scope: 关联知识范围（分类ID/标签ID列表）
  enabled: 启用状态
}
```

### 数据源适配器接口（预留）
```
DataAdapter {
  fetch() -> List[Document]:
    # 从数据源获取数据并转为标准Document
}
# MVP仅定义接口，具体DBAdapter/APIAdapter后续实现
```

## 精简说明（相对初版）
以下功能在MVP阶段简化或后移，不影响核心功能完整性：
- 知识关联关系管理：砍掉，标签已足够
- 混合搜索加权：简化为语义搜索+数据库LIKE
- 向量相似度推荐：简化为同分类/同标签推荐
- 多轮对话上下文理解：简化为单轮+历史记录
- 内容摘要独立功能：集成到问答流程
- Skill前端测试工具：后端提供测试接口即可
- 数据源适配器实现：仅预留接口定义
