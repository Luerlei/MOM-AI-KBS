"""Chronos 时序预测模型 HTTP 推理服务

将 amazon/chronos-t5-small（及 chronos-forecasting 支持的其他模型）包装为 HTTP 服务，
暴露统一 POST /predict 端点，供本项目的 ForecastClient 调用。

启动：
    python chronos_server.py --model amazon/chronos-t5-small --port 8501
    python chronos_server.py --model amazon/chronos-t5-small --port 8501 --device cpu

依赖：
    pip install chronos-forecasting fastapi uvicorn

环境变量：
    HF_ENDPOINT=https://hf-mirror.com   # 国内镜像加速模型下载
"""
import argparse
import os
import time

# 环境变量需在 huggingface_hub import 前设置
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

import torch
from fastapi import FastAPI
from pydantic import BaseModel

# 模型懒加载（启动时加载一次）
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
            "..", "data", "models",
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
    响应：{forecasts: [float], quantiles: {"0.1": [float], "0.5": [float], "0.9": [float]}, model: str}
    """
    start = time.time()
    quantiles = req.quantiles or [0.1, 0.5, 0.9]

    pipeline = get_pipeline()
    context = torch.tensor([req.series], dtype=torch.float32)
    # predict 返回 shape: (1, num_samples, horizon)，为采样路径
    samples = pipeline.predict(context, prediction_length=req.horizon)
    samples = samples[0]  # (num_samples, horizon)

    # 中位数作为点预测
    forecasts = torch.quantile(samples, 0.5, dim=0).tolist()

    # 各分位数
    quantile_result = {}
    for q in quantiles:
        key = f"{q}"
        quantile_result[key] = torch.quantile(samples, q, dim=0).tolist()

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
    parser.add_argument("--model", default="amazon/chronos-t5-small",
                        help="HuggingFace 模型 ID")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--device", default="cpu", help="cpu / cuda / mps")
    args = parser.parse_args()

    _model_id = args.model

    import uvicorn
    print(f"[chronos] 启动服务: http://localhost:{args.port}")
    print(f"[chronos] 模型: {_model_id} | 设备: {args.device}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
