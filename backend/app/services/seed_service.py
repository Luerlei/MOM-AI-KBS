"""预制数据初始化服务"""
import json

from app.database import SessionLocal
from app.models import Category, Tag, Skill, ModelConfig, Dataset, Knowledge
from app.services.skill_option_service import seed_options
from app.utils.crypto import encrypt


# 分类定义：(id, name)
INITIAL_CATEGORIES = [
    (1, "制造运营"),
    (2, "仓储物流"),
    (3, "质量管理"),
    (4, "设备管理"),
]

# 标签定义
INITIAL_TAGS = [
    "故障代码", "保养", "工艺", "质量标准", "仓储管理", "操作经验",
]

# 预制 Skill 定义
INITIAL_SKILLS = [
    {
        "name": "故障诊断",
        "description": "针对设备故障、报警、错误代码进行诊断和处理建议",
        "category": "设备管理",
        "function": "故障诊断",
        "trigger_keywords": ["故障", "报错", "异常", "错误代码", "E0", "E1"],
        "trigger_patterns": [r"E\d+", r"故障代码.*", r".*报警.*"],
        "prompt_template": "你是MOM系统设备故障诊断专家。请根据设备故障现象和知识库内容，给出诊断结论和处理建议。\n\n知识上下文：\n{context}\n\n用户问题：{question}\n\n请按以下结构回答：\n1. 故障现象分析\n2. 可能原因\n3. 处理建议\n4. 注意事项",
        "knowledge_scope": {"category_ids": [4], "tag_ids": [1]},
        "is_default": False,
    },
    {
        "name": "保养维护",
        "description": "设备保养计划、维护周期、润滑等维护知识",
        "category": "设备管理",
        "function": "保养维护",
        "trigger_keywords": ["保养", "维护", "检修", "周期", "润滑"],
        "trigger_patterns": [r"保养.*", r"维护.*周期"],
        "prompt_template": "你是MOM系统设备保养维护专家。请根据保养需求和相关知识，给出维护方案和注意事项。\n\n知识上下文：\n{context}\n\n用户问题：{question}\n\n请按以下结构回答：\n1. 保养项目\n2. 维护标准\n3. 周期建议\n4. 安全注意事项",
        "knowledge_scope": {"category_ids": [4], "tag_ids": [2]},
        "is_default": False,
    },
    {
        "name": "工艺指导",
        "description": "生产工艺、工序参数、操作规程等指导",
        "category": "制造运营",
        "function": "工艺指导",
        "trigger_keywords": ["工艺", "工序", "参数", "操作规程", "加工"],
        "trigger_patterns": [r"工艺.*", r"加工.*参数"],
        "prompt_template": "你是MOM系统工艺指导专家。请根据工艺问题给出操作指导和参数建议。\n\n知识上下文：\n{context}\n\n用户问题：{question}\n\n请按以下结构回答：\n1. 工艺要求\n2. 关键参数\n3. 操作步骤\n4. 质量控制点",
        "knowledge_scope": {"category_ids": [1]},
        "is_default": False,
    },
    {
        "name": "质量检验",
        "description": "质量标准、检验方法、合格判定等质量知识",
        "category": "质量管理",
        "function": "质量检验",
        "trigger_keywords": ["质量", "检验", "合格", "不合格", "标准", "偏差"],
        "trigger_patterns": [r"质量.*标准", r"检验.*"],
        "prompt_template": "你是MOM系统质量管理专家。请根据质量检验问题给出判定结果和处理建议。\n\n知识上下文：\n{context}\n\n用户问题：{question}\n\n请按以下结构回答：\n1. 质量标准\n2. 检验方法\n3. 判定结论\n4. 处理建议",
        "knowledge_scope": {"category_ids": [3]},
        "is_default": False,
    },
    {
        "name": "通用问答",
        "description": "通用知识问答，未命中其他Skill时使用",
        "category": "通用",
        "function": "通用问答",
        "trigger_keywords": [],
        "trigger_patterns": [],
        "prompt_template": "你是MOM系统AI知识库助手。请根据以下知识上下文回答用户问题。\n\n知识上下文：\n{context}\n\n用户问题：{question}\n\n请基于上述上下文回答，若上下文不足请如实说明。",
        "knowledge_scope": {},
        "is_default": True,
    },
]


# 预制 Forecast 时序预测模型配置（Chronos-2 / TimesFM 2.5 本地推理服务示例）
# 约定各推理服务暴露统一 POST /predict 端点
INITIAL_FORECAST_MODELS = [
    {
        "name": "Chronos-2 (本地)",
        "type": "Forecast",
        "api_url": "http://localhost:8501",
        "api_key": "",
        "model_name": "amazon/chronos-bolt-base",
        "is_active": False,
    },
    {
        "name": "TimesFM 2.5 (本地)",
        "type": "Forecast",
        "api_url": "http://localhost:8502",
        "api_key": "",
        "model_name": "google/timesfm-2.0-200m-pytorch",
        "is_active": False,
    },
]

# P0-3: 预置硅基流动 Rerank/OCR/VLM 模型配置（用户只需填 API Key 即可激活）
# 参照 RAGFlow 的多模型重排序能力，开箱即用
INITIAL_AUX_MODELS = [
    {
        "name": "bge-reranker-v2-m3 (硅基流动)",
        "type": "Rerank",
        "api_url": "https://api.siliconflow.cn/v1",
        "api_key": "",  # 用户填入硅基流动 API Key 后激活
        "model_name": "BAAI/bge-reranker-v2-m3",
        "is_active": False,
    },
    {
        "name": "DeepSeek-OCR (硅基流动)",
        "type": "OCR",
        "api_url": "https://api.siliconflow.cn/v1",
        "api_key": "",  # 用户填入硅基流动 API Key 后激活
        "model_name": "deepseek-ai/DeepSeek-OCR",
        "is_active": False,
    },
    {
        "name": "Qwen3-VL-32B (硅基流动)",
        "type": "VLM",
        "api_url": "https://api.siliconflow.cn/v1",
        "api_key": "",  # 用户填入硅基流动 API Key 后激活
        "model_name": "Qwen/Qwen3-VL-32B-Instruct",
        "is_active": False,
    },
]


# 预制示例时序数据集（用于趋势分析演示）
# 数据格式: [{time, value, label}, ...]
INITIAL_DATASETS = [
    {
        "name": "某车间月度产量（示例）",
        "description": "2023-2024 年某车间月度产量数据，含上升趋势与季节波动，用于演示时序预测功能",
        "frequency": "monthly",
        "unit": "万件",
        "source": "seed",
        "series_data": [
            {"time": "2023-01", "value": 110.2, "label": ""},
            {"time": "2023-02", "value": 98.5, "label": "春节"},
            {"time": "2023-03", "value": 125.4, "label": ""},
            {"time": "2023-04", "value": 118.6, "label": ""},
            {"time": "2023-05", "value": 130.1, "label": ""},
            {"time": "2023-06", "value": 122.8, "label": ""},
            {"time": "2023-07", "value": 135.3, "label": "旺季"},
            {"time": "2023-08", "value": 138.9, "label": "旺季"},
            {"time": "2023-09", "value": 128.7, "label": ""},
            {"time": "2023-10", "value": 142.5, "label": ""},
            {"time": "2023-11", "value": 145.2, "label": ""},
            {"time": "2023-12", "value": 150.8, "label": "年终冲刺"},
            {"time": "2024-01", "value": 115.6, "label": "春节"},
            {"time": "2024-02", "value": 102.3, "label": "春节"},
            {"time": "2024-03", "value": 132.1, "label": ""},
            {"time": "2024-04", "value": 125.7, "label": ""},
            {"time": "2024-05", "value": 138.4, "label": ""},
            {"time": "2024-06", "value": 130.9, "label": ""},
            {"time": "2024-07", "value": 143.2, "label": "旺季"},
            {"time": "2024-08", "value": 147.6, "label": "旺季"},
            {"time": "2024-09", "value": 136.8, "label": ""},
            {"time": "2024-10", "value": 151.3, "label": ""},
            {"time": "2024-11", "value": 154.7, "label": ""},
            {"time": "2024-12", "value": 160.5, "label": "年终冲刺"},
        ],
    },
    {
        "name": "某设备季度故障次数（示例）",
        "description": "2022-2024 年某关键设备季度故障次数，含周期性波动，用于演示时序预测功能",
        "frequency": "quarterly",
        "unit": "次",
        "source": "seed",
        "series_data": [
            {"time": "2022-Q1", "value": 8, "label": ""},
            {"time": "2022-Q2", "value": 12, "label": ""},
            {"time": "2022-Q3", "value": 15, "label": "高温季"},
            {"time": "2022-Q4", "value": 6, "label": ""},
            {"time": "2023-Q1", "value": 9, "label": ""},
            {"time": "2023-Q2", "value": 14, "label": ""},
            {"time": "2023-Q3", "value": 18, "label": "高温季"},
            {"time": "2023-Q4", "value": 7, "label": ""},
            {"time": "2024-Q1", "value": 10, "label": ""},
            {"time": "2024-Q2", "value": 13, "label": ""},
            {"time": "2024-Q3", "value": 16, "label": "高温季"},
            {"time": "2024-Q4", "value": 5, "label": "检修后"},
        ],
    },
]


# 预制示例知识条目（匹配各 Skill 的 knowledge_scope，用于演示智能问答 Skill 路由）
# Skill1 故障诊断: category_ids=[4], tag_ids=[1]
# Skill2 保养维护: category_ids=[4], tag_ids=[2]
# Skill3 工艺指导: category_ids=[1]
# Skill4 质量检验: category_ids=[3]
# Skill5 通用问答: {}
INITIAL_KNOWLEDGE = [
    {
        "title": "CNC加工中心E01报警故障诊断与处理指南",
        "category_id": 4,
        "tag_ids": [1],
        "content": "# CNC加工中心E01报警故障诊断与处理\n\n## 1. 故障现象\nCNC加工中心在运行过程中出现 E01 报警代码，主轴停止运转，设备无法继续加工。\n\n## 2. 可能原因\n1. **主轴驱动器故障**：驱动器内部功率模块过热或损坏\n2. **电源电压异常**：输入电压波动超出允许范围（±10%）\n3. **主轴电机过载**：加工负荷超过电机额定功率\n4. **编码器反馈异常**：主轴编码器连接松动或信号干扰\n\n## 3. 诊断步骤\n1. 查看驱动器面板报警代码，确认是否为 E01\n2. 测量输入电源电压，确认三相电压平衡且在范围内\n3. 检查主轴电机温升，用手持测温仪测量外壳温度（正常<60℃）\n4. 检查编码器连接线插头是否松动\n\n## 4. 处理建议\n- **电源问题**：加装稳压器，排查车间电网\n- **过载问题**：降低进给速度或切削深度，建议主轴负载率不超过 80%\n- **驱动器故障**：联系设备厂家更换驱动器功率模块\n- **编码器问题**：重新插拔编码器接头，必要时更换编码器线缆\n\n## 5. 注意事项\n- 处理前务必断电并挂\"禁止合闸\"警示牌\n- E01 报警复位前需等待驱动器完全放电（至少 5 分钟）\n- 同一故障反复出现应记录频次并上报设备管理部门",
    },
    {
        "title": "设备定期保养维护规程与周期表",
        "category_id": 4,
        "tag_ids": [2],
        "content": "# 设备定期保养维护规程与周期表\n\n## 一、日常保养（每日，操作员执行）\n1. **开机点检**：检查设备外观、急停按钮、安全防护门\n2. **润滑检查**：查看导轨润滑油位，低于下限立即补充\n3. **清洁作业**：清除工作台铁屑，擦拭切削液溅落区域\n4. **运行监听**：开机空转 5 分钟，监听有无异响\n\n## 二、周保养（每周，操作员执行）\n1. 清洗切削液过滤网\n2. 检查气动系统压力（标准 0.5-0.7 MPa）\n3. 检查液压油位，观察有无泄漏\n4. 检查刀具夹持力，必要时校准\n\n## 三、月保养（每月，维修人员执行）\n1. **导轨润滑**：手动注油，检查自动润滑系统工作状态\n2. **电气检查**：紧固接线端子，检查接触器触点磨损\n3. **精度校验**：用千分表检查主轴径向跳动（≤0.01mm）\n4. **备份参数**：导出 NC 程序和设备参数\n\n## 四、年度大保养（每年，厂家或专业团队执行）\n1. 更换主轴轴承（寿命约 8000 小时）\n2. 更换液压油和导轨润滑油\n3. 检查伺服电机绝缘电阻\n4. 全面精度校准与几何精度检测\n\n## 五、保养记录要求\n- 每次保养填写《设备保养记录表》\n- 记录保养项目、更换备件、发现异常\n- 保养记录存档不少于 3 年",
    },
    {
        "title": "数控加工工艺参数规范与操作要点",
        "category_id": 1,
        "tag_ids": [3],
        "content": "# 数控加工工艺参数规范与操作要点\n\n## 一、切削参数选用原则\n\n### 1. 主轴转速（S）\n| 材料 | 高速钢刀具 | 硬质合金刀具 |\n|------|-----------|-------------|\n| 低碳钢 | 80-120 m/min | 200-400 m/min |\n| 中碳钢 | 60-100 m/min | 150-300 m/min |\n| 铝合金 | 150-300 m/min | 400-800 m/min |\n\n计算公式：`S = (Vc × 1000) / (π × D)`\n\n### 2. 进给速度（F）\n- 粗加工：0.1-0.3 mm/齿\n- 精加工：0.05-0.15 mm/齿\n- 计算公式：`F = fz × Z × S`（Z=齿数）\n\n### 3. 切削深度\n- 粗加工：轴向 3-6mm，径向 50%-80% 刀具直径\n- 精加工：轴向 0.1-0.5mm，径向 0.05-0.2mm\n\n## 二、操作步骤\n1. **工艺分析**：阅读图纸，确认加工余量、公差、表面粗糙度要求\n2. **刀具选择**：根据材料和工序选择刀具类型与规格\n3. **装夹定位**：遵循\"基准统一\"原则，夹紧力适当\n4. **程序调试**：空运行验证，单段试切确认\n5. **首件检验**：加工首件后全尺寸检验，合格后批量生产\n\n## 三、质量控制点\n- 关键尺寸首检、抽检\n- 刀具磨损监控（建议每加工 50 件检查刀具）\n- 切削液浓度检测（标准 8%-12%）",
    },
    {
        "title": "产品质量检验标准与不合格品判定规则",
        "category_id": 3,
        "tag_ids": [4],
        "content": "# 产品质量检验标准与不合格品判定规则\n\n## 一、检验分类\n1. **首件检验**：每班次开始或换型后首件必须全尺寸检验\n2. **过程检验（巡检）**：按设定频次（如每 2 小时）抽检关键尺寸\n3. **完工检验**：产品完工入库前的最终检验\n\n## 二、合格判定标准\n### 尺寸公差\n- 关键尺寸（KP）：实测值在公差范围内为合格\n- 一般尺寸：实测值在公差范围内为合格\n- 超差但可返工的判定为\"返工品\"\n\n### 表面质量\n- 粗糙度 Ra ≤ 图纸标注值\n- 不允许有划伤、磕碰、锈蚀\n\n## 三、不合格品处理流程\n1. **标识隔离**：挂红色\"不合格\"标签，移至不合格品区\n2. **评审定责**：质量工程师组织评审，确定不合格原因与责任\n3. **处置方式**：\n   - 返工：修复后重新检验合格可放行\n   - 返修：降低规格接收（需客户批准）\n   - 报废：无法修复的予以报废\n4. **预防措施**：分析根因，制定纠正预防措施（CAPA）\n\n## 四、检验记录\n- 检验结果录入 QMS 系统\n- 保存检验报告至少 5 年\n- 不合格品须填写《不合格品处理单》",
    },
    {
        "title": "MOM系统操作常见问题FAQ",
        "category_id": None,
        "tag_ids": [6],
        "content": "# MOM系统操作常见问题FAQ\n\n## Q1: 如何录入新的生产工单？\nA: 进入【生产管理】→【工单管理】→点击\"新建工单\"，填写工单编号、产品型号、计划数量、计划开完工时间后保存。\n\n## Q2: 设备点检数据如何提交？\nA: 打开【设备管理】→【点检记录】→选择设备→逐项勾选点检项目→提交。点检数据实时同步至设备状态看板。\n\n## Q3: 质量异常如何在系统中上报？\nA: 【质量管理】→【异常上报】→选择产品和工序→填写异常描述、数量→上传照片→提交。系统自动通知质量工程师。\n\n## Q4: 如何查看车间实时产量？\nA: 首页仪表盘展示关键指标，或进入【生产监控】查看各产线实时产量、OEE、达成率。\n\n## Q5: 忘记密码怎么办？\nA: 联系系统管理员重置，或通过登录页\"忘记密码\"链接自助重置（需配置邮箱）。\n\n## Q6: 系统支持哪些数据导出格式？\nA: 报表支持 Excel、PDF 导出，生产数据支持 CSV 导出供二次分析使用。",
    },
]


def seed_initial_data():
    """系统启动时调用：创建预制数据（仅在不存在时创建）"""
    db = SessionLocal()
    try:
        # 1. 创建分类
        for cid, cname in INITIAL_CATEGORIES:
            existing = db.query(Category).filter(Category.id == cid).first()
            if not existing:
                c = Category(id=cid, name=cname, sort_order=cid)
                db.add(c)
        db.commit()

        # 2. 创建标签
        for tname in INITIAL_TAGS:
            existing = db.query(Tag).filter(Tag.name == tname).first()
            if not existing:
                t = Tag(name=tname)
                db.add(t)
        db.commit()

        # 3. 创建预制 Skill
        for sdef in INITIAL_SKILLS:
            existing = db.query(Skill).filter(Skill.name == sdef["name"]).first()
            if not existing:
                s = Skill(
                    name=sdef["name"],
                    description=sdef["description"],
                    category=sdef["category"],
                    function=sdef["function"],
                    trigger_keywords=json.dumps(sdef["trigger_keywords"], ensure_ascii=False),
                    trigger_patterns=json.dumps(sdef["trigger_patterns"], ensure_ascii=False),
                    prompt_template=sdef["prompt_template"],
                    knowledge_scope=json.dumps(sdef["knowledge_scope"], ensure_ascii=False),
                    enabled=True,
                    is_default=sdef["is_default"],
                )
                db.add(s)
        db.commit()

        # 4. 创建预制 Skill 分类/功能选项
        seed_options(db)

        # 5. 创建预制 Forecast 时序预测模型配置
        for fdef in INITIAL_FORECAST_MODELS:
            existing = db.query(ModelConfig).filter(
                ModelConfig.name == fdef["name"], ModelConfig.type == "Forecast"
            ).first()
            if not existing:
                fc = ModelConfig(
                    name=fdef["name"],
                    type=fdef["type"],
                    api_url=fdef["api_url"],
                    api_key=encrypt(fdef["api_key"]) if fdef["api_key"] else "",
                    model_name=fdef["model_name"],
                    is_active=fdef["is_active"],
                )
                db.add(fc)
        db.commit()

        # 5.5 P0-3: 创建预制 Rerank/OCR 模型配置（用户填 API Key 即可激活）
        for adef in INITIAL_AUX_MODELS:
            existing = db.query(ModelConfig).filter(
                ModelConfig.name == adef["name"], ModelConfig.type == adef["type"]
            ).first()
            if not existing:
                ac = ModelConfig(
                    name=adef["name"],
                    type=adef["type"],
                    api_url=adef["api_url"],
                    api_key=encrypt(adef["api_key"]) if adef["api_key"] else "",
                    model_name=adef["model_name"],
                    is_active=adef["is_active"],
                )
                db.add(ac)
        db.commit()

        # 6. 创建预制示例时序数据集
        for ddef in INITIAL_DATASETS:
            existing = db.query(Dataset).filter(Dataset.name == ddef["name"]).first()
            if not existing:
                ds = Dataset(
                    name=ddef["name"],
                    description=ddef.get("description", ""),
                    frequency=ddef.get("frequency", "other"),
                    unit=ddef.get("unit", ""),
                    series_data=json.dumps(ddef["series_data"], ensure_ascii=False),
                    point_count=len(ddef["series_data"]),
                    source=ddef.get("source", "seed"),
                )
                db.add(ds)
        db.commit()

        # 7. 创建预制示例知识条目（匹配各 Skill 知识范围，演示 Skill 路由）
        from app.models.knowledge import knowledge_tags
        for kdef in INITIAL_KNOWLEDGE:
            existing = db.query(Knowledge).filter(Knowledge.title == kdef["title"]).first()
            if not existing:
                k = Knowledge(
                    title=kdef["title"],
                    content=kdef["content"],
                    content_type="markdown",
                    category_id=kdef.get("category_id"),
                    source_type="manual",
                    status="published",
                )
                db.add(k)
                db.flush()
                # 关联标签
                for tid in kdef.get("tag_ids", []):
                    tag = db.query(Tag).filter(Tag.id == tid).first()
                    if tag:
                        db.execute(knowledge_tags.insert().values(knowledge_id=k.id, tag_id=tid))
        db.commit()

        # 8. 为示例数据集自动生成协变量 + 手动促销协变量（演示协变量功能）
        try:
            from app.services import covariate_service
            # 月度产量数据集：自动生成 + 手动促销协变量
            monthly_ds = db.query(Dataset).filter(Dataset.frequency == "monthly", Dataset.source == "seed").first()
            if monthly_ds:
                existing_covs = db.query(covariate_service.DatasetCovariate).filter(
                    covariate_service.DatasetCovariate.dataset_id == monthly_ds.id
                ).count()
                if existing_covs == 0:
                    covariate_service.auto_generate_covariates(db, monthly_ds.id, skip_existing=True)
                    # 手动促销协变量（旺季 7-8 月、年终冲刺 12 月）
                    series = covariate_service._load_series(monthly_ds.series_data)
                    promo_months = {"2023-07", "2023-08", "2023-12", "2024-07", "2024-08", "2024-12"}
                    promo_values = [
                        {"time": p.get("time", ""), "value": 1.0 if p.get("time", "") in promo_months else 0.0}
                        for p in series
                    ]
                    covariate_service.create_covariate(
                        db, dataset_id=monthly_ds.id, name="促销活动", code="promotion",
                        cov_type="binary", values=promo_values,
                        description="旺季(7-8月)与年终冲刺(12月)标记为1，用于体现促销对产量的影响",
                    )
            # 季度故障数据集：自动生成
            quarterly_ds = db.query(Dataset).filter(Dataset.frequency == "quarterly", Dataset.source == "seed").first()
            if quarterly_ds:
                existing_covs = db.query(covariate_service.DatasetCovariate).filter(
                    covariate_service.DatasetCovariate.dataset_id == quarterly_ds.id
                ).count()
                if existing_covs == 0:
                    covariate_service.auto_generate_covariates(db, quarterly_ds.id, skip_existing=True)
        except Exception as e:
            print(f"[seed] 协变量初始化跳过: {e}")
    except Exception as e:
        # 初始化失败不应阻塞启动
        print(f"[seed] 初始化预制数据时出错: {e}")
        db.rollback()
    finally:
        db.close()
