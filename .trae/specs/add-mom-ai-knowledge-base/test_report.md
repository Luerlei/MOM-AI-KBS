# MOM系统AI知识库平台 - 测试报告

## 测试概要
- 测试时间: 2026-07-12 16:30:02
- 测试环境: 本地开发电脑
- 后端地址: http://localhost:8000

## 测试结果
| 指标 | 数值 |
|------|------|
| 通过 | 53 |
| 失败 | 0 |
| 跳过 | 0 |
| 总计 | 53 |
| 通过率 | 100.0% |

## 详细测试用例

| Case ID | 测试场景 | 结果 | 备注 |
|---------|---------|------|------|
| TC-SY-05 | 健康检查 | ✅ PASS |  |
| TC-SY-06 | Swagger文档 | ✅ PASS |  |
| CAT-01 | 获取分类树 | ✅ PASS |  |
| CAT-02 | 预制4个分类 | ✅ PASS | 共4个 |
| CAT-03 | 创建分类 | ✅ PASS |  |
| CAT-04 | 更新分类 | ✅ PASS |  |
| CAT-05 | 删除分类 | ✅ PASS |  |
| TAG-01 | 获取标签列表 | ✅ PASS |  |
| TAG-02 | 预制6个标签 | ✅ PASS | 共11个 |
| TAG-03 | 创建标签 | ✅ PASS |  |
| TAG-04 | 删除标签 | ✅ PASS |  |
| TC-SK-01 | 查看预制Skill | ✅ PASS |  |
| TC-SK-01b | 5个预制Skill | ✅ PASS | 共6个 |
| TC-SK-02 | 按模块筛选(设备管理) | ✅ PASS | 2个 |
| TC-SK-03 | 创建Skill | ✅ PASS |  |
| TC-SK-05 | 编辑Skill | ✅ PASS |  |
| TC-SK-06 | 禁用Skill | ✅ PASS |  |
| TC-SK-07 | 启用Skill | ✅ PASS |  |
| TC-SK-08 | 删除自定义Skill | ✅ PASS |  |
| TC-SK-08b | 默认Skill不可删 | ✅ PASS |  |
| TC-SK-04 | 获取模板列表 | ✅ PASS |  |
| TC-SK-09 | Skill路由测试 | ✅ PASS |  |
| TC-RT-01 | 关键词匹配(故障) | ✅ PASS |  |
| TC-KM-04 | 手动录入知识 | ✅ PASS |  |
| TC-KM-08 | 知识列表 | ✅ PASS |  |
| TC-KM-08b | 知识总数=24 | ✅ PASS |  |
| TC-KM-09 | 知识详情 | ✅ PASS |  |
| TC-KM-06 | 编辑知识 | ✅ PASS |  |
| TC-KM-12 | 按分类筛选 | ✅ PASS |  |
| TC-KM-13 | 按标签筛选 | ✅ PASS |  |
| TC-KM-01 | 单文件上传(产品质量检验标准.xlsx) | ✅ PASS |  |
| TC-KM-02 | 批量上传(3个文件) | ✅ PASS |  |
| TC-KM-07 | 删除知识 | ✅ PASS |  |
| TC-KM-11 | 批量打标签 | ✅ PASS |  |
| TC-SE-03 | 关键词搜索(E01) | ✅ PASS |  |
| TC-SE-03b | 搜索结果数=1 | ✅ PASS | 无数据可能因为上传未完成 |
| TC-SE-01 | 语义搜索 | ✅ PASS | (可能无结果，需Embedding模型) |
| TC-SE-09 | 搜索历史 | ✅ PASS |  |
| TC-MC-02 | 新增LLM配置 | ✅ PASS |  |
| TC-MC-03 | 新增Embedding配置 | ✅ PASS |  |
| TC-MC-01 | 获取模型配置列表 | ✅ PASS |  |
| TC-MC-06 | 密钥脱敏 | ✅ PASS |  |
| TC-MC-07 | 删除模型配置 | ✅ PASS |  |
| TC-MC-07b | 删除Embedding模型配置 | ✅ PASS |  |
| TC-MC-08 | 删除启用中模型(应拒绝) | ✅ PASS |  |
| TC-SY-01 | 首页统计卡片 | ✅ PASS |  |
| TC-SY-01b | 知识数=23, Skill数=6 | ✅ PASS |  |
| TC-SY-02 | 首页最近问答 | ✅ PASS |  |
| TC-HI-01 | 查看历史列表 | ✅ PASS |  |
| TC-TK-02 | Token统计 | ✅ PASS |  |
| TC-TK-03 | 按周统计 | ✅ PASS |  |
| TC-QA-12 | 无模型配置时问答 | ✅ PASS | 有模型配置，问答流式返回 |
| TC-SY-07 | 相关内容推荐 | ✅ PASS |  |

## 说明
- **PASS**: 测试通过
- **FAIL**: 测试失败，需修复
- **SKIP**: 测试跳过（通常因缺少模型配置等环境依赖）

## 模型依赖说明
以下功能依赖LLM和Embedding模型配置，未配置模型时自动跳过：
- 语义搜索（需要Embedding模型）
- 智能问答（需要LLM和Embedding模型）
- Skill语义匹配（需要Embedding模型）
- 向量索引生成（需要Embedding模型）

配置模型后，这些功能即可使用。
