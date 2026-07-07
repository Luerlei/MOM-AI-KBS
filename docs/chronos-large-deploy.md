# Chronos-T5-Large 模型部署指南

本文档说明如何在服务器上部署 `amazon/chronos-t5-large` 时序预测模型，作为独立 HTTP 推理服务供 MOM AI 知识库平台调用。

> 本文档与 [chronos-deploy.md](./chronos-deploy.md)（Small 版本）配套使用。Large 模型部署流程与 Small 完全一致，仅模型 ID、端口、资源需求不同。本文档重点说明差异点。

## 1. 部署架构

```
MOM 知识库平台 (ForecastClient)
        ↓ HTTP POST /predict
Chronos Large 推理服务 (FastAPI + uvicorn, 端口 8503)
        ↓
ChronosPipeline (amazon/chronos-t5-large, chronos-forecasting SDK)
```

**关键说明**：`chronos-forecasting` 是 Amazon 官方 Python SDK，仅提供 `ChronosPipeline` 类，不暴露 HTTP 接口。本项目通过 `chronos_server.py` 脚本将其包装为 HTTP 服务，约定统一 `POST /predict` 端点。Large 模型与 Small 模型共用同一脚本，仅 `--model` 参数不同。

## 2. 环境要求

| 项 | 要求 | 说明 |
|---|---|---|
| 操作系统 | Linux / Windows / macOS | 推荐 Linux 生产环境 |
| Python | 3.10+（推荐 3.11） | 与 Small 一致 |
| 内存 | ≥ 4GB（CPU 推理） | Large 模型权重约 1.2GB，运行时占用 2-3GB |
| 磁盘 | ≥ 5GB | 模型权重 1.2GB + torch 等依赖约 3GB |
| GPU（可选） | ≥ 4GB 显存 | GPU 可显著降低推理延迟 |
| 网络 | 首次部署需访问 HuggingFace | 模型约 1.2GB，下载耗时 3-15 分钟 |

## 3. 与 Small 模型对比

| 维度 | Chronos-T5-Small | Chronos-T5-Large |
|---|---|---|
| 模型 ID | `amazon/chronos-t5-small` | `amazon/chronos-t5-large` |
| 模型参数量 | 约 20M | 约 200M |
| 权重大小 | 约 100MB | 约 1.2GB |
| 推荐端口 | 8501 | 8503 |
| 内存占用（CPU） | 约 500MB-1GB | 约 2-3GB |
| 首次下载耗时 | 1-2 分钟 | 3-15 分钟（视网络） |
| 模型加载耗时 | 5-10 秒 | 15-30 秒 |
| CPU 推理延迟（已加载） | 300-500ms | 800-1000ms |
| 预测精度 | 基础 | 更高（推荐生产场景） |
| 适用场景 | 测试、Demo、低配机器 | 生产、高精度需求 |

> **选型建议**：资源充足时优先选 Large；开发调试或资源受限场景选 Small。两者可并存部署（不同端口），在 MOM 平台切换启用。

## 4. 部署步骤

### 4.1 准备 Python 环境

**Linux / macOS**：
```bash
python3.11 -m venv venv
source venv/bin/activate
```

**Windows**：
```powershell
C:\Python311\python.exe -m venv venv
.\venv\Scripts\activate
```

### 4.2 安装依赖

```bash
pip install chronos-forecasting fastapi uvicorn pydantic
```

**国内服务器加速**（推荐）：
```bash
pip install chronos-forecasting fastapi uvicorn pydantic \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --timeout 300
```

**验证安装**：
```bash
python -c "from chronos import ChronosPipeline; import torch; print('OK, torch:', torch.__version__)"
```

### 4.3 部署推理服务脚本

将以下脚本放置到服务器任意目录（例如 `/opt/chronos-large/chronos_server.py`）：

```python
"""Chronos 时序预测模型 HTTP 推理服务

启动：
    python chronos_server.py --model amazon/chronos-t5-large --port 8503
"""
import argparse
import os
import time

# 环境变量需在 huggingface_hub import 前设置
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")  # 国内镜像加速
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")               # 禁用 Xet 避免 401

import torch
from fastapi import FastAPI
from pydantic import BaseModel

_pipeline = None
_model_id = "amazon/chronos-t5-large"


class PredictRequest(BaseModel):
    series: list[float]
    horizon: int = 12
    quantiles: list[float] | None = None


app = FastAPI(title="Chronos Large Forecast Server")


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        from chronos import ChronosPipeline
        from huggingface_hub import snapshot_download
        print(f"[chronos] 加载模型: {_model_id} (首次加载需下载权重约 1.2GB)...")
        # 下载到本地目录，避免 Windows symlink 权限问题
        local_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "models",
            _model_id.replace("/", "--")
        )
        local_path = snapshot_download(
            repo_id=_model_id,
            local_dir=local_dir,
        )
        print(f"[chronos] 模型已下载到: {local_path}")
        _pipeline = ChronosPipeline.from_pretrained(local_path)
        print(f"[chronos] 模型加载完成")
    return _pipeline


@app.get("/health")
def health():
    return {"status": "ok", "model": _model_id}


@app.post("/predict")
def predict(req: PredictRequest):
    """时序预测

    请求：{series: [float], horizon: int, quantiles: [float]}
    响应：{forecasts: [float], quantiles: {"0.1": [...], "0.5": [...], "0.9": [...]}, model: str}
    """
    start = time.time()
    quantiles = req.quantiles or [0.1, 0.5, 0.9]

    pipeline = get_pipeline()
    context = torch.tensor([req.series], dtype=torch.float32)
    samples = pipeline.predict(context, prediction_length=req.horizon)
    samples = samples[0]  # (num_samples, horizon)

    forecasts = torch.quantile(samples, 0.5, dim=0).tolist()

    quantile_result = {}
    for q in quantiles:
        quantile_result[f"{q}"] = torch.quantile(samples, q, dim=0).tolist()

    duration_ms = int((time.time() - start) * 1000)
    return {
        "forecasts": forecasts,
        "quantiles": quantile_result,
        "model": _model_id,
        "duration_ms": duration_ms,
        "num_samples": int(samples.shape[0]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="amazon/chronos-t5-large")
    parser.add_argument("--port", type=int, default=8503)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    _model_id = args.model

    import uvicorn
    print(f"[chronos] 启动服务: http://0.0.0.0:{args.port}")
    print(f"[chronos] 模型: {_model_id} | 设备: {args.device}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
```

> 也可直接从项目仓库复制：`backend/scripts/chronos_server.py`（脚本通用，通过 `--model` 参数区分 Small/Large）

### 4.4 下载模型权重

Large 模型权重约 1.2GB，**强烈建议提前下载**（避免首次请求超时）：

```bash
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1

python -c "
from huggingface_hub import snapshot_download
path = snapshot_download(
    repo_id='amazon/chronos-t5-large',
    local_dir='./models/amazon--chronos-t5-large'
)
print('下载完成:', path)
"
```

> **下载耗时预估**：使用国内镜像约 3-10 分钟，直连 HuggingFace 可能 10-30 分钟。

**离线部署**（目标服务器无外网）：
1. 在有网络的机器上执行上述下载命令
2. 将 `models/amazon--chronos-t5-large/` 整个目录（约 1.2GB）复制到目标服务器脚本同级目录
3. 脚本会自动从本地路径加载，无需联网

### 4.5 启动服务

**前台启动**（用于测试）：
```bash
python chronos_server.py --model amazon/chronos-t5-large --port 8503
```

**后台启动**（Linux）：
```bash
nohup python chronos_server.py --model amazon/chronos-t5-large --port 8503 \
    > chronos-large.log 2>&1 &
```

**后台启动**（Windows PowerShell）：
```powershell
$env:HF_ENDPOINT="https://hf-mirror.com"
$env:HF_HUB_DISABLE_XET="1"
Start-Process python -ArgumentList "chronos_server.py","--model","amazon/chronos-t5-large","--port","8503" `
    -WindowStyle Hidden -RedirectStandardOutput "chronos-large.log"
```

**GPU 启动**（如有 CUDA，显著降低延迟）：
```bash
python chronos_server.py --model amazon/chronos-t5-large --port 8503 --device cuda
```

### 4.6 验证服务

**健康检查**：
```bash
curl http://localhost:8503/health
# 预期: {"status":"ok","model":"amazon/chronos-t5-large"}
```

**预测测试**：
```bash
curl -X POST http://localhost:8503/predict \
    -H "Content-Type: application/json" \
    -d '{"series":[1,2,3,4,5,6,7,8],"horizon":3,"quantiles":[0.1,0.5,0.9]}'
```

**预期响应**（实测样例）：
```json
{
    "forecasts": [9.01, 8.76, 9.25],
    "quantiles": {
        "0.1": [7.82, 7.14, 7.45],
        "0.5": [9.01, 8.76, 9.25],
        "0.9": [10.05, 10.31, 10.89]
    },
    "model": "amazon/chronos-t5-large",
    "duration_ms": 874,
    "num_samples": 20
}
```

> 首次调用耗时较长（约 200+ 秒，含模型下载和加载）。模型加载完成后，单次预测约 800-1000ms（CPU）。

## 5. 配置到 MOM 知识库平台

Chronos Large 推理服务启动后，需要在 MOM 知识库平台中配置模型。

### 5.1 前置条件

- MOM 知识库平台后端已启动（默认端口 8000）
- MOM 知识库平台前端已启动（默认端口 5173）
- Chronos Large 推理服务已启动并可访问（`curl http://<服务器IP>:8503/health` 返回 ok）

### 5.2 配置步骤

1. **打开模型配置页面**

   浏览器访问 http://localhost:5173/models，进入「模型配置」页面。

2. **新增 Forecast 配置**

   在页面底部「Forecast 时序预测模型配置」卡片，点击右上角「新增 Forecast」。

3. **填写配置字段**

   | 字段 | 值 | 说明 |
   |---|---|---|
   | 名称 | `Chronos-T5 Large (本地)` | 自定义易识别名称 |
   | 类型 | `Forecast` | 必选 |
   | API 地址 | `http://localhost:8503` | Large 服务地址（**注意端口 8503**） |
   | API Key | 留空 | 本地部署无需鉴权 |
   | 模型名称 | `amazon/chronos-t5-large` | 与启动 `--model` 参数一致 |

   > **远程服务器部署时**：API 地址填 `http://<服务器IP>:8503`。

4. **测试连通性**

   点击「测试」按钮，预期结果：
   - 弹出「连通成功」提示
   - 延迟约 800-1000ms（CPU，已加载模型）
   - 调用日志记录 `input_pts=5, output_pts=2`

5. **启用模型**

   点击「启用」开关。同类型（Forecast）仅允许一个启用，启用 Large 会自动停用 Small（如已启用）。

   > **多模型并存策略**：Small 和 Large 可同时配置，但只能启用一个。切换启用模型即可切换精度/性能权衡。

6. **验证配置状态**

   ```bash
   curl http://localhost:8000/api/models/status
   ```
   预期响应中 `forecast` 字段指向 Large：
   ```json
   {
       "forecast": {
           "id": 12,
           "name": "Chronos-T5 Large (本地)",
           "model_name": "amazon/chronos-t5-large",
           "source": "external"
       }
   }
   ```

### 5.3 查看调用日志

访问 http://localhost:5173/call-logs，筛选 `call_type=test` 或 `source=test_model` 查看测试记录。

**实测日志样例**：
```
call_type=test | model=amazon/chronos-t5-large | input_pts=5 | output_pts=2 | duration=874ms | source=test_model
```

字段说明：
- `input_tokens`：复用为输入序列点数
- `output_tokens`：复用为输出预测点数
- `duration_ms`：单次调用耗时

### 5.4 通过 API 配置（可选）

```bash
# 新增配置
curl -X POST http://localhost:8000/api/models \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Chronos-T5 Large (本地)",
        "type": "Forecast",
        "api_url": "http://localhost:8503",
        "api_key": "",
        "model_name": "amazon/chronos-t5-large",
        "is_active": true
    }'

# 启用配置（替换 <id>）
curl -X PUT http://localhost:8000/api/models/<id>/activate

# 测试连通性（替换 <id>）
curl -X POST http://localhost:8000/api/models/<id>/test
```

## 6. 生产环境建议

### 6.1 进程守护（Linux）

```bash
sudo tee /etc/systemd/system/chronos-large.service > /dev/null <<'EOF'
[Unit]
Description=Chronos Large Forecast Server
After=network.target

[Service]
Type=simple
User=app
WorkingDirectory=/opt/chronos-large
Environment=HF_ENDPOINT=https://hf-mirror.com
Environment=HF_HUB_DISABLE_XET=1
ExecStart=/opt/chronos-large/venv/bin/python chronos_server.py \
    --model amazon/chronos-t5-large --port 8503
Restart=on-failure
RestartSec=10
# Large 模型内存占用较高，建议设置限制
MemoryMax=4G

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now chronos-large
sudo systemctl status chronos-large
```

### 6.2 反向代理（Nginx）

```nginx
server {
    listen 80;
    server_name forecast-large.example.com;

    location / {
        proxy_pass http://127.0.0.1:8503;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;  # Large 预测可能更耗时
    }
}
```

### 6.3 防火墙

```bash
sudo ufw allow 8503/tcp
```

### 6.4 资源调优

- **CPU 推理**：单次预测约 800-1000ms（已加载模型后）
- **GPU 推理**：单次预测约 100-200ms（推荐生产环境）
- **模型加载**：约 15-30 秒加载到内存
- **并发**：uvicorn 默认单进程，Large 模型建议 `--workers 1`（避免内存翻倍），高并发用队列削峰
- **内存占用**：约 2-3GB，建议服务器内存 ≥ 4GB
- **预热**：服务启动后建议先发一个测试请求，避免首个业务请求超时

### 6.5 Small 与 Large 共存部署

可在同一服务器同时部署两个服务（不同端口）：

```bash
# Small 服务（端口 8501，低延迟场景）
python chronos_server.py --model amazon/chronos-t5-small --port 8501

# Large 服务（端口 8503，高精度场景）
python chronos_server.py --model amazon/chronos-t5-large --port 8503
```

> **注意**：同时运行两个模型，服务器内存需 ≥ 6GB。

在 MOM 平台分别配置两条 Forecast 记录，按需切换启用。

## 7. 常见问题

### Q1: 首次请求超时（>200 秒）

**原因**：Large 模型权重 1.2GB，首次请求触发下载 + 加载。

**解决**：
1. 按 4.4 节提前下载模型权重
2. 服务启动后先发一个 `curl /health` 或小规模 `/predict` 预热
3. 调整反向代理 `proxy_read_timeout` 为 300s 以上

### Q2: `OSError: [WinError 14007]` 符号链接创建失败

**原因**：Windows 上 huggingface_hub 默认用 symlink 缓存，需管理员权限。

**解决**：脚本已通过 `snapshot_download(local_dir=...)` 下载到普通目录规避。确保 `HF_HUB_DISABLE_XET=1` 在 import 前设置。

### Q3: `RuntimeError: HTTP status client error (401 Unauthorized)` Xet 认证失败

**原因**：HuggingFace 新版 Xet 存储需要认证。

**解决**：设置 `HF_HUB_DISABLE_XET=1` 回退到普通 HTTP 下载。

### Q4: 模型下载慢或超时

**原因**：Large 模型 1.2GB，直连 HuggingFace 耗时较长。

**解决**：
```bash
export HF_ENDPOINT=https://hf-mirror.com
```
或使用离线部署方式（见 4.4 节）。

### Q5: 内存不足（OOM）

**原因**：Large 模型运行时占用 2-3GB，服务器内存不足。

**解决**：
- 升级服务器内存至 ≥ 4GB
- 关闭其他占用内存的进程
- 改用 Small 模型（见 chronos-deploy.md）
- 启用 swap 分区（Linux）：`sudo fallocate -l 4G /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`

### Q6: 推理延迟过高（>2 秒）

**原因**：CPU 推理 Large 模型较慢，尤其在高负载时。

**解决**：
- 使用 GPU（`--device cuda`），延迟可降至 100-200ms
- 增加输入序列长度，减少调用频次（一次预测更长 horizon）
- 评估是否真的需要 Large 精度，必要时切回 Small

### Q7: 端口 8503 被占用

**解决**：更换端口启动 `--port 8504`，同步更新 MOM 平台的 API 地址配置。

### Q8: Small 和 Large 同时启用冲突

**原因**：系统限制同类型（Forecast）仅允许一个启用。

**解决**：在 MOM 平台切换启用开关。如需同时调用两个模型，需扩展类型分类（目前不支持）。

## 8. 接口规格

### POST /predict

**请求体**：
```json
{
    "series": [1.0, 2.0, 3.0, 4.0, 5.0],
    "horizon": 12,
    "quantiles": [0.1, 0.5, 0.9]
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| series | list[float] | 是 | 历史观测值序列，长度 ≥ 3 |
| horizon | int | 否 | 预测步数，默认 12 |
| quantiles | list[float] | 否 | 分位数列表，默认 [0.1, 0.5, 0.9] |

**响应体**：
```json
{
    "forecasts": [6.1, 6.2, 6.3],
    "quantiles": {
        "0.1": [5.5, 5.6, 5.7],
        "0.5": [6.1, 6.2, 6.3],
        "0.9": [6.7, 6.8, 6.9]
    },
    "model": "amazon/chronos-t5-large",
    "duration_ms": 874,
    "num_samples": 20
}
```

### GET /health

**响应**：
```json
{"status": "ok", "model": "amazon/chronos-t5-large"}
```

## 9. 参考资源

- Chronos 官方仓库：https://github.com/amazon-science/chronos-forecasting
- HuggingFace 模型页：https://huggingface.co/amazon/chronos-t5-large
- chronos-forecasting PyPI：https://pypi.org/project/chronos-forecasting/
- HF 国内镜像：https://hf-mirror.com
- Small 模型部署指南：[chronos-deploy.md](./chronos-deploy.md)
- TimesFM 部署指南：[timesfm-deploy.md](./timesfm-deploy.md)
