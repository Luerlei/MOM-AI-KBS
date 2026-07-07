# Chronos-T5-Small 模型部署指南

本文档说明如何在服务器上部署 `amazon/chronos-t5-small` 时序预测模型，作为独立 HTTP 推理服务供 MOM AI 知识库平台调用。

## 1. 部署架构

```
MOM 知识库平台 (ForecastClient)
        ↓ HTTP POST /predict
Chronos 推理服务 (FastAPI + uvicorn, 端口 8501)
        ↓
ChronosPipeline (amazon/chronos-t5-small, chronos-forecasting SDK)
```

**关键说明**：`chronos-forecasting` 是 Amazon 官方 Python SDK，仅提供 `ChronosPipeline` 类，不暴露 HTTP 接口。本项目通过 `chronos_server.py` 脚本将其包装为 HTTP 服务，约定统一 `POST /predict` 端点。

## 2. 环境要求

| 项 | 要求 |
|---|---|
| 操作系统 | Linux / Windows / macOS |
| Python | 3.10+（推荐 3.11） |
| 内存 | ≥ 2GB（CPU 推理） |
| 磁盘 | ≥ 2GB（含模型权重约 100MB + torch 等依赖） |
| GPU | 可选，CPU 可运行（chronos-t5-small 模型较小） |
| 网络 | 首次部署需访问 HuggingFace 下载模型权重 |

## 3. 部署步骤

### 3.1 准备 Python 环境

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

### 3.2 安装依赖

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

### 3.3 部署推理服务脚本

将以下脚本放置到服务器任意目录（例如 `/opt/chronos/chronos_server.py`）：

```python
"""Chronos 时序预测模型 HTTP 推理服务

启动：
    python chronos_server.py --model amazon/chronos-t5-small --port 8501
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
_model_id = "amazon/chronos-t5-small"


class PredictRequest(BaseModel):
    series: list[float]
    horizon: int = 12
    quantiles: list[float] | None = None


app = FastAPI(title="Chronos Forecast Server")


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        from chronos import ChronosPipeline
        from huggingface_hub import snapshot_download
        print(f"[chronos] 加载模型: {_model_id} (首次加载需下载权重)...")
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
    parser.add_argument("--model", default="amazon/chronos-t5-small")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    _model_id = args.model

    import uvicorn
    print(f"[chronos] 启动服务: http://0.0.0.0:{args.port}")
    print(f"[chronos] 模型: {_model_id} | 设备: {args.device}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
```

> 也可直接从项目仓库复制：`backend/scripts/chronos_server.py`

### 3.4 下载模型权重

模型权重在首次调用 `/predict` 时自动下载到脚本同目录的 `models/amazon--chronos-t5-small/` 文件夹。

**如需提前下载（避免生产环境首次延迟）**：

```bash
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1

python -c "
from huggingface_hub import snapshot_download
path = snapshot_download(
    repo_id='amazon/chronos-t5-small',
    local_dir='./models/amazon--chronos-t5-small'
)
print('下载完成:', path)
"
```

**离线部署**（目标服务器无外网）：
1. 在有网络的机器上执行上述下载命令
2. 将 `models/amazon--chronos-t5-small/` 整个目录复制到目标服务器脚本同级目录
3. 脚本会自动从本地路径加载，无需联网

### 3.5 启动服务

**前台启动**（用于测试）：
```bash
python chronos_server.py --model amazon/chronos-t5-small --port 8501
```

**后台启动**（Linux）：
```bash
nohup python chronos_server.py --model amazon/chronos-t5-small --port 8501 \
    > chronos.log 2>&1 &
```

**后台启动**（Windows PowerShell）：
```powershell
$env:HF_ENDPOINT="https://hf-mirror.com"
$env:HF_HUB_DISABLE_XET="1"
Start-Process python -ArgumentList "chronos_server.py","--port","8501" `
    -WindowStyle Hidden -RedirectStandardOutput "chronos.log"
```

**GPU 启动**（如有 CUDA）：
```bash
python chronos_server.py --model amazon/chronos-t5-small --port 8501 --device cuda
```

### 3.6 验证服务

**健康检查**：
```bash
curl http://localhost:8501/health
# 预期: {"status":"ok","model":"amazon/chronos-t5-small"}
```

**预测测试**：
```bash
curl -X POST http://localhost:8501/predict \
    -H "Content-Type: application/json" \
    -d '{"series":[1,2,3,4,5,6,7,8],"horizon":3,"quantiles":[0.1,0.5,0.9]}'
```

**预期响应**：
```json
{
    "forecasts": [8.41, 8.74, 8.63],
    "quantiles": {
        "0.1": [7.29, 6.72, 6.71],
        "0.5": [8.41, 8.74, 8.63],
        "0.9": [9.11, 9.70, 9.74]
    },
    "model": "amazon/chronos-t5-small",
    "duration_ms": 364,
    "num_samples": 20
}
```

## 4. 配置到 MOM 知识库平台

Chronos 推理服务启动后，需要在 MOM 知识库平台中配置模型，使其可被系统的 `ForecastClient` 调用。

### 4.1 前置条件

- MOM 知识库平台后端已启动（默认端口 8000）
- MOM 知识库平台前端已启动（默认端口 5173）
- Chronos 推理服务已启动并可访问（`curl http://<服务器IP>:8501/health` 返回 ok）

### 4.2 配置步骤

1. **打开模型配置页面**

   浏览器访问 http://localhost:5173/models （或对应服务器地址），进入「模型配置」页面。

2. **找到 Forecast 卡片**

   页面底部有「Forecast 时序预测模型配置」卡片。系统启动时会预置两条示例配置（Chronos-2 / TimesFM），可直接编辑，也可点击右上角「新增 Forecast」创建新配置。

3. **编辑或新增配置**

   点击配置行的「编辑」按钮，填写以下字段：

   | 字段 | 值 | 说明 |
   |---|---|---|
   | 名称 | `Chronos-T5 (本地)` | 自定义易识别名称 |
   | 类型 | `Forecast` | 必选，单选框切换 |
   | API 地址 | `http://localhost:8501` | Chronos 服务地址（不含 `/predict` 后缀，系统自动拼接） |
   | API Key | 留空 | 本地部署无需鉴权 |
   | 模型名称 | `amazon/chronos-t5-small` | 与 Chronos 服务启动时的 `--model` 参数一致 |

   > **远程服务器部署时**：API 地址填 `http://<服务器IP>:8501`，确保 MOM 后端服务器能访问该地址。

4. **测试连通性**

   点击配置行的「测试」按钮，系统会发送测试请求：
   - 请求：`POST /predict`，body 为 `{"series":[1,2,3,4,5],"horizon":2}`
   - 预期结果：弹出「连通成功」提示，显示模型名和预测步数，延迟约 300-500ms

   若失败，检查：
   - Chronos 服务是否在运行
   - API 地址是否正确
   - 防火墙是否放行 8501 端口
   - 后端服务器到 Chronos 服务的网络连通性

5. **启用模型**

   测试通过后，点击「启用」开关切换为启用状态。
   - 同类型（Forecast）仅允许一个启用，启用新模型会自动停用旧模型
   - 启用后，系统通过 `ModelManager.get_active_forecast()` 获取该配置

6. **验证配置状态**

   访问 http://localhost:5173/dashboard 首页，或调用接口验证：
   ```bash
   curl http://localhost:8000/api/models/status
   ```
   预期响应中 `forecast` 字段非 null：
   ```json
   {
       "llm": {...},
       "embedding": {...},
       "forecast": {
           "id": 10,
           "name": "Chronos-T5 (本地)",
           "model_name": "amazon/chronos-t5-small",
           "source": "external"
       }
   }
   ```

### 4.3 查看调用日志

所有 Forecast 模型的调用（包括测试和后续业务调用）都会记录到 TokenUsage 表：

1. 访问 http://localhost:5173/call-logs 调用日志页面
2. 筛选 `call_type=test` 或 `source=test_model` 查看测试记录
3. 字段说明：
   - `input_tokens`：复用为输入序列点数
   - `output_tokens`：复用为输出预测点数
   - `duration_ms`：单次调用耗时

### 4.4 通过 API 配置（可选）

若需通过脚本批量配置，可直接调用后端 API：

```bash
# 新增配置
curl -X POST http://localhost:8000/api/models \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Chronos-T5 (本地)",
        "type": "Forecast",
        "api_url": "http://localhost:8501",
        "api_key": "",
        "model_name": "amazon/chronos-t5-small",
        "is_active": true
    }'

# 启用某个配置（替换 <id>）
curl -X PUT http://localhost:8000/api/models/<id>/activate

# 测试连通性（替换 <id>）
curl -X POST http://localhost:8000/api/models/<id>/test
```

### 4.5 多环境配置示例

| 部署场景 | API 地址 | 说明 |
|---|---|---|
| 本地开发 | `http://localhost:8501` | Chronos 与 MOM 同机部署 |
| 同内网服务器 | `http://192.168.1.100:8501` | Chronos 在内网其他机器 |
| 反向代理 | `https://forecast.example.com` | 通过 Nginx 暴露，需配置 HTTPS |
| Docker 容器 | `http://chronos:8501` | 同一 Docker 网络内服务名访问 |

## 5. 生产环境建议

### 5.1 进程守护（Linux）

推荐使用 systemd 管理服务：

```bash
sudo tee /etc/systemd/system/chronos.service > /dev/null <<'EOF'
[Unit]
Description=Chronos Forecast Server
After=network.target

[Service]
Type=simple
User=app
WorkingDirectory=/opt/chronos
Environment=HF_ENDPOINT=https://hf-mirror.com
Environment=HF_HUB_DISABLE_XET=1
ExecStart=/opt/chronos/venv/bin/python chronos_server.py --port 8501
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now chronos
sudo systemctl status chronos
```

### 5.2 反向代理（Nginx）

如需通过 80/443 端口访问或添加鉴权：

```nginx
server {
    listen 80;
    server_name forecast.example.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;  # 预测可能耗时较长
    }
}
```

### 5.3 防火墙

仅放行必要端口：
```bash
sudo ufw allow 8501/tcp
```

### 5.4 资源调优

- CPU 推理：单次预测约 300-500ms（已加载模型后）
- 首次加载：约 5-10 秒加载模型到内存
- 并发：uvicorn 默认单进程，高并发场景用 `--workers 2`
- 内存占用：约 500MB-1GB

## 6. 常见问题

### Q1: `OSError: [WinError 14007]` 符号链接创建失败

**原因**：Windows 上 huggingface_hub 默认用 symlink 缓存，需管理员权限。

**解决**：脚本已通过 `snapshot_download(local_dir=...)` 下载到普通目录规避。若仍出现，确保 `HF_HUB_DISABLE_XET=1` 环境变量在 import 前设置。

### Q2: `RuntimeError: HTTP status client error (401 Unauthorized)` Xet 认证失败

**原因**：HuggingFace 新版 Xet 存储需要认证。

**解决**：设置环境变量 `HF_HUB_DISABLE_XET=1` 回退到普通 HTTP 下载。

### Q3: 模型下载慢或超时

**原因**：默认从 huggingface.co 下载，国内访问不稳定。

**解决**：
```bash
export HF_ENDPOINT=https://hf-mirror.com
```
或使用离线部署方式（见 3.4 节）。

### Q4: `ModuleNotFoundError: No module named 'chronos'`

**原因**：未安装 `chronos-forecasting` 包。

**解决**：
```bash
pip install chronos-forecasting
```

### Q5: 预测结果 `forecasts` 为空或 NaN

**原因**：输入序列过短或包含非数值。

**解决**：确保 `series` 为数值列表，长度至少 ≥ 3，推荐 ≥ 10 获得更好效果。

### Q6: 端口 8501 被占用

**解决**：更换端口启动 `--port 8502`，同步更新 MOM 平台的 API 地址配置。

## 7. 接口规格

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
    "model": "amazon/chronos-t5-small",
    "duration_ms": 364,
    "num_samples": 20
}
```

### GET /health

**响应**：
```json
{"status": "ok", "model": "amazon/chronos-t5-small"}
```

## 8. 参考资源

- Chronos 官方仓库：https://github.com/amazon-science/chronos-forecasting
- HuggingFace 模型页：https://huggingface.co/amazon/chronos-t5-small
- chronos-forecasting PyPI：https://pypi.org/project/chronos-forecasting/
- HF 国内镜像：https://hf-mirror.com
