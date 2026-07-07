# TimesFM 2.5-200M 模型部署指南

本文档说明如何在服务器上部署 `google/timesfm-2.5-200m-pytorch` 时序预测模型，作为独立 HTTP 推理服务供 MOM AI 知识库平台调用。

## 1. 部署架构

```
MOM 知识库平台 (ForecastClient)
        ↓ HTTP POST /predict
TimesFM 推理服务 (FastAPI + uvicorn, 端口 8502)
        ↓
TimesFM_2p5_200M_torch (google/timesfm-2.5-200m-pytorch, timesfm 2.0+ SDK)
```

**关键说明**：
- `timesfm` 是 Google 官方 Python SDK，仅提供 `TimesFM_2p5_200M_torch` 类，不暴露 HTTP 接口
- 本项目通过 `timesfm_server.py` 脚本将其包装为 HTTP 服务，约定统一 `POST /predict` 端点
- TimesFM 2.5 支持点预测 + 9 个分位数预测（0.1~0.9）
- **重要**：`timesfm` 包 2.0+ 仅支持 2.5 模型，不再支持 1.0 模型；若需 1.0 模型需降级到 `timesfm==1.0.0`

## 2. 环境要求

| 项 | 要求 |
|---|---|
| 操作系统 | Linux / Windows / macOS |
| Python | 3.10+（推荐 3.11） |
| 内存 | ≥ 4GB（TimesFM 2.5 加载需约 1-2GB） |
| 磁盘 | ≥ 2GB（含模型权重约 800MB + torch 等依赖） |
| GPU | 可选，CPU 可运行（200M 参数模型） |
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
pip install timesfm fastapi uvicorn pydantic numpy
```

**国内服务器加速**（推荐）：
```bash
pip install timesfm fastapi uvicorn pydantic numpy \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --timeout 300
```

**验证安装**：
```bash
python -c "import timesfm; print('timesfm OK')"
python -c "from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch; print('class OK')"
```

### 3.3 部署推理服务脚本

将以下脚本放置到服务器任意目录（例如 `/opt/timesfm/timesfm_server.py`）：

```python
"""TimesFM 时序预测模型 HTTP 推理服务

启动：
    python timesfm_server.py --model google/timesfm-2.5-200m-pytorch --port 8502
"""
import argparse
import os
import time

# 环境变量需在 huggingface_hub import 前设置
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel

_model = None
_model_id = "google/timesfm-2.5-200m-pytorch"


class PredictRequest(BaseModel):
    series: list[float]
    horizon: int = 12
    quantiles: list[float] | None = None


app = FastAPI(title="TimesFM Forecast Server")


def get_model():
    """加载 TimesFM 2.5 模型（首次加载从 HuggingFace 下载，后续从本地缓存）"""
    global _model
    if _model is None:
        from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch
        from timesfm import ForecastConfig
        from huggingface_hub import snapshot_download
        print(f"[timesfm] 加载模型: {_model_id} (首次加载需下载权重)...")

        # 下载到本地目录，避免 Windows symlink 权限问题
        local_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "models",
            _model_id.replace("/", "--")
        )
        os.makedirs(local_dir, exist_ok=True)
        local_path = snapshot_download(
            repo_id=_model_id,
            local_dir=local_dir,
        )
        print(f"[timesfm] 模型已下载到: {local_path}")

        # 从本地路径加载模型
        _model = TimesFM_2p5_200M_torch.from_pretrained(local_path)
        # TimesFM 2.5 要求先 compile 才能预测
        forecast_config = ForecastConfig(
            max_context=512,      # 最大上下文长度
            max_horizon=64,       # 最大预测步数
            per_core_batch_size=32,
        )
        _model.compile(forecast_config=forecast_config)
        print(f"[timesfm] 模型已加载并编译")
    return _model


@app.get("/health")
def health():
    return {"status": "ok", "model": _model_id}


@app.post("/predict")
def predict(req: PredictRequest):
    """时序预测

    请求：{series: [float], horizon: int, quantiles: [float]}
    响应：{forecasts: [float], quantiles: {"0.1": [...], "0.5": [...], "0.9": [...]}, model: str}

    说明：TimesFM 2.5 forecast() 返回 (mean, quantile_predictions)，
         quantile_predictions 为固定分位数 [0.1, 0.2, ..., 0.9] 的预测值。
    """
    start = time.time()
    quantiles = req.quantiles or [0.1, 0.5, 0.9]

    tfm = get_model()

    # TimesFM 2.5 forecast API: inputs 为 list[np.ndarray]，每个 ndarray 为一条时序
    inputs = [np.array(req.series, dtype=np.float32)]
    mean_forecast, quantile_forecast = tfm.forecast(
        horizon=req.horizon,
        inputs=inputs,
    )

    # mean_forecast: shape (1, horizon) - 点预测
    forecasts = mean_forecast[0].tolist()

    # quantile_forecast: shape (1, horizon, num_quantiles) - 分位数预测
    # TimesFM 2.5 默认分位数: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    default_quantiles = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    quantile_result = {}
    for q in quantiles:
        if q in default_quantiles:
            idx = default_quantiles.index(q)
            quantile_result[f"{q}"] = quantile_forecast[0, :, idx].tolist()
        else:
            # 用户请求的分位数不在默认列表中，用最接近的代替
            closest_idx = min(range(len(default_quantiles)),
                              key=lambda i: abs(default_quantiles[i] - q))
            quantile_result[f"{q}"] = quantile_forecast[0, :, closest_idx].tolist()

    duration_ms = int((time.time() - start) * 1000)
    return {
        "forecasts": forecasts,
        "quantiles": quantile_result,
        "model": _model_id,
        "duration_ms": duration_ms,
        "num_samples": len(forecasts),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="google/timesfm-2.5-200m-pytorch")
    parser.add_argument("--port", type=int, default=8502)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    _model_id = args.model

    import uvicorn
    print(f"[timesfm] 启动服务: http://0.0.0.0:{args.port}")
    print(f"[timesfm] 模型: {_model_id} | 设备: {args.device}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
```

> 也可直接从项目仓库复制：`backend/scripts/timesfm_server.py`

### 3.4 下载模型权重

模型权重在首次调用 `/predict` 时自动下载到脚本同目录的 `models/google--timesfm-2.5-200m-pytorch/` 文件夹。

**如需提前下载（避免生产环境首次延迟）**：

```bash
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1

python -c "
from huggingface_hub import snapshot_download
path = snapshot_download(
    repo_id='google/timesfm-2.5-200m-pytorch',
    local_dir='./models/google--timesfm-2.5-200m-pytorch',
    etag_timeout=120,
    max_workers=2,
)
print('下载完成:', path)
"
```

**离线部署**（目标服务器无外网）：
1. 在有网络的机器上执行上述下载命令
2. 将 `models/google--timesfm-2.5-200m-pytorch/` 整个目录复制到目标服务器脚本同级目录
3. 脚本会自动从本地路径加载，无需联网

### 3.5 启动服务

**前台启动**（用于测试）：
```bash
python timesfm_server.py --model google/timesfm-2.5-200m-pytorch --port 8502
```

**后台启动**（Linux）：
```bash
nohup python timesfm_server.py --model google/timesfm-2.5-200m-pytorch --port 8502 \
    > timesfm.log 2>&1 &
```

**后台启动**（Windows PowerShell）：
```powershell
$env:HF_ENDPOINT="https://hf-mirror.com"
$env:HF_HUB_DISABLE_XET="1"
Start-Process python -ArgumentList "timesfm_server.py","--port","8502" `
    -WindowStyle Hidden -RedirectStandardOutput "timesfm.log"
```

**GPU 启动**（如有 CUDA）：
```bash
python timesfm_server.py --model google/timesfm-2.5-200m-pytorch --port 8502 --device cuda
```

### 3.6 验证服务

**健康检查**：
```bash
curl http://localhost:8502/health
# 预期: {"status":"ok","model":"google/timesfm-2.5-200m-pytorch"}
```

**预测测试**：
```bash
curl -X POST http://localhost:8502/predict \
    -H "Content-Type: application/json" \
    -d '{"series":[10.5,11.2,12.8,13.1,14.5,15.2,16.8,17.5,18.9,20.1],"horizon":3,"quantiles":[0.1,0.5,0.9]}'
```

**预期响应**：
```json
{
    "forecasts": [20.65, 21.82, 23.06],
    "quantiles": {
        "0.1": [20.60, 21.78, 23.20],
        "0.5": [20.35, 21.60, 22.80],
        "0.9": [20.68, 22.43, 23.78]
    },
    "model": "google/timesfm-2.5-200m-pytorch",
    "duration_ms": 2079,
    "num_samples": 3
}
```

## 4. 配置到 MOM 知识库平台

TimesFM 推理服务启动后，需要在 MOM 知识库平台中配置模型，使其可被系统的 `ForecastClient` 调用。

### 4.1 前置条件

- MOM 知识库平台后端已启动（默认端口 8000）
- MOM 知识库平台前端已启动（默认端口 5173）
- TimesFM 推理服务已启动并可访问（`curl http://<服务器IP>:8502/health` 返回 ok）

### 4.2 配置步骤

1. **打开模型配置页面**

   浏览器访问 http://localhost:5173/models，进入「模型配置」页面。

2. **找到 Forecast 卡片**

   页面底部有「Forecast 时序预测模型配置」卡片。系统启动时会预置 TimesFM 配置（id=11），可直接编辑，也可点击右上角「新增 Forecast」创建新配置。

3. **编辑或新增配置**

   点击配置行的「编辑」按钮，填写以下字段：

   | 字段 | 值 | 说明 |
   |---|---|---|
   | 名称 | `TimesFM 2.5 (本地)` | 自定义易识别名称 |
   | 类型 | `Forecast` | 必选，单选框切换 |
   | API 地址 | `http://localhost:8502` | TimesFM 服务地址（不含 `/predict` 后缀，系统自动拼接） |
   | API Key | 留空 | 本地部署无需鉴权 |
   | 模型名称 | `google/timesfm-2.5-200m-pytorch` | 与 TimesFM 服务启动时的 `--model` 参数一致 |

   > **远程服务器部署时**：API 地址填 `http://<服务器IP>:8502`，确保 MOM 后端服务器能访问该地址。

4. **测试连通性**

   点击配置行的「测试」按钮，系统会发送测试请求：
   - 请求：`POST /predict`，body 为 `{"series":[1,2,3,4,5],"horizon":2}`
   - 预期结果：弹出「连接成功」提示，显示模型名和预测步数，延迟约 1-3 秒（TimesFM 2.5 首次预测因模型加载较慢）

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
       "forecast": {
           "id": 11,
           "name": "TimesFM 2.5 (本地)",
           "model_name": "google/timesfm-2.5-200m-pytorch",
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
        "name": "TimesFM 2.5 (本地)",
        "type": "Forecast",
        "api_url": "http://localhost:8502",
        "api_key": "",
        "model_name": "google/timesfm-2.5-200m-pytorch",
        "is_active": true
    }'

# 启用某个配置（替换 <id>）
curl -X PUT http://localhost:8000/api/models/<id>/activate

# 测试连通性（替换 <id>）
curl -X POST http://localhost:8000/api/models/<id>/test
```

## 5. 与 Chronos 对比

| 维度 | Chronos-T5-Small | TimesFM 2.5-200M |
|---|---|---|
| 参数量 | 23M | 200M |
| 模型大小 | ~100MB | ~800MB |
| 内存占用 | ~500MB | ~1.5GB |
| CPU 推理延迟 | ~300-500ms | ~2000ms |
| 预测能力 | 中位数 + 分位数 | 中位数 + 9 个分位数 |
| 上下文长度 | 512 | 512（可配置） |
| 最大预测步数 | 任意（性能递减） | 64（受 compile 配置限制） |
| 部署端口 | 8501 | 8502 |

## 6. 生产环境建议

### 6.1 进程守护（Linux）

推荐使用 systemd 管理服务：

```bash
sudo tee /etc/systemd/system/timesfm.service > /dev/null <<'EOF'
[Unit]
Description=TimesFM Forecast Server
After=network.target

[Service]
Type=simple
User=app
WorkingDirectory=/opt/timesfm
Environment=HF_ENDPOINT=https://hf-mirror.com
Environment=HF_HUB_DISABLE_XET=1
ExecStart=/opt/timesfm/venv/bin/python timesfm_server.py --port 8502
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now timesfm
sudo systemctl status timesfm
```

### 6.2 反向代理（Nginx）

如需通过 80/443 端口访问或添加鉴权：

```nginx
server {
    listen 80;
    server_name forecast.example.com;

    location / {
        proxy_pass http://127.0.0.1:8502;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;  # 预测可能耗时较长
    }
}
```

### 6.3 防火墙

仅放行必要端口：
```bash
sudo ufw allow 8502/tcp
```

### 6.4 资源调优

- CPU 推理：单次预测约 1-3 秒（已加载模型后）
- 首次加载：约 5-10 秒加载模型 + compile
- 并发：uvicorn 默认单进程，高并发场景用 `--workers 2`
- 内存占用：约 1-2GB

## 7. 常见问题

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

### Q4: `AttributeError: 'TimesFM_2p5_200M_torch' object has no attribute 'forecast_on_df'`

**原因**：TimesFM 2.0+ API 变更，移除了 `forecast_on_df` 方法。
**解决**：使用 `forecast(horizon, inputs)` 方法，inputs 为 `list[np.ndarray]`。

### Q5: `RuntimeError: Model is not compiled. Please call compile() first.`

**原因**：TimesFM 2.5 要求加载后先 `compile()` 才能预测。
**解决**：调用 `_model.compile(forecast_config=ForecastConfig(...))`。

### Q6: `TypeError: compile() missing 1 required positional argument: 'forecast_config'`

**原因**：`compile()` 必须传入 `ForecastConfig` 对象。
**解决**：构造 `ForecastConfig(max_context=512, max_horizon=64, per_core_batch_size=32)`。

### Q7: `timesfm-1.0-200m` 模型无法加载

**原因**：`timesfm` 包 2.0+ 仅支持 2.5 模型，不再支持 1.0。
**解决**：
- 方案 A（推荐）：改用 `google/timesfm-2.5-200m-pytorch`
- 方案 B：降级到 `pip install timesfm==1.0.0`（可能与 chronos-forecasting 依赖冲突）

### Q8: 预测结果 `horizon` 大于 64 报错

**原因**：`ForecastConfig.max_horizon=64` 限制了最大预测步数。
**解决**：增大 `max_horizon` 值（注意内存消耗相应增加）。

### Q9: 端口 8502 被占用

**解决**：更换端口启动 `--port 8503`，同步更新 MOM 平台的 API 地址配置。

## 8. 接口规格

### POST /predict

**请求体**：
```json
{
    "series": [10.5, 11.2, 12.8, 13.1, 14.5],
    "horizon": 12,
    "quantiles": [0.1, 0.5, 0.9]
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| series | list[float] | 是 | 历史观测值序列，长度 ≥ 3，推荐 ≥ 10 |
| horizon | int | 否 | 预测步数，默认 12，最大受 max_horizon 限制 |
| quantiles | list[float] | 否 | 分位数列表，默认 [0.1, 0.5, 0.9]，支持 [0.1~0.9] 任意组合 |

**响应体**：
```json
{
    "forecasts": [20.65, 21.82, 23.06],
    "quantiles": {
        "0.1": [20.60, 21.78, 23.20],
        "0.5": [20.35, 21.60, 22.80],
        "0.9": [20.68, 22.43, 23.78]
    },
    "model": "google/timesfm-2.5-200m-pytorch",
    "duration_ms": 2079,
    "num_samples": 3
}
```

### GET /health

**响应**：
```json
{"status": "ok", "model": "google/timesfm-2.5-200m-pytorch"}
```

## 9. 参考资源

- TimesFM 官方仓库：https://github.com/google-research/timesfm
- HuggingFace 模型页：https://huggingface.co/google/timesfm-2.5-200m-pytorch
- timesfm PyPI：https://pypi.org/project/timesfm/
- HF 国内镜像：https://hf-mirror.com
