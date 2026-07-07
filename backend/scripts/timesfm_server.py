"""TimesFM 时序预测模型 HTTP 推理服务

将 google/timesfm-2.5-200m-pytorch 包装为 HTTP 服务，
暴露统一 POST /predict 端点，供本项目的 ForecastClient 调用。

启动：
    python timesfm_server.py --model google/timesfm-2.5-200m-pytorch --port 8502
    python timesfm_server.py --model google/timesfm-2.5-200m-pytorch --port 8502 --device cpu

依赖：
    pip install timesfm fastapi uvicorn pydantic pandas

环境变量：
    HF_ENDPOINT=https://hf-mirror.com   # 国内镜像加速模型下载
    HF_HUB_DISABLE_XET=1                # 禁用 Xet 避免 401
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

# 模型懒加载（启动时加载一次）
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
            "..", "data", "models",
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
    响应：{forecasts: [float], quantiles: {"0.1": [float], "0.5": [float], "0.9": [float]}, model: str}

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
    parser.add_argument("--model", default="google/timesfm-2.5-200m-pytorch",
                        help="HuggingFace 模型 ID")
    parser.add_argument("--port", type=int, default=8502)
    parser.add_argument("--device", default="cpu", help="cpu / cuda")
    args = parser.parse_args()

    _model_id = args.model

    import uvicorn
    print(f"[timesfm] 启动服务: http://0.0.0.0:{args.port}")
    print(f"[timesfm] 模型: {_model_id} | 设备: {args.device}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
