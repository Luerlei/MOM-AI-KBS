"""JWT 认证工具

当 AUTH_ENABLED=true 时，敏感 API 需要 Bearer token 认证。
默认关闭（开发环境），生产环境通过环境变量开启。
"""
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Request
from app.config import SECRET_KEY, AUTH_ENABLED, ADMIN_USERNAME, ADMIN_PASSWORD, JWT_EXPIRE_HOURS
from app.utils.response import APIError


def create_access_token(username: str) -> str:
    """创建 JWT access token"""
    payload = {
        "sub": username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_token(token: str) -> dict:
    """验证 JWT token，返回 payload；失败抛 APIError"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise APIError("Token 已过期，请重新登录", status_code=401)
    except jwt.InvalidTokenError:
        raise APIError("无效的 Token", status_code=401)


def authenticate(username: str, password: str) -> Optional[str]:
    """验证用户名密码，成功返回 token，失败返回 None"""
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return create_access_token(username)
    return None


async def require_auth(request: Request) -> dict:
    """FastAPI 依赖：要求认证

    AUTH_ENABLED=false 时跳过认证（开发环境默认关闭）。
    AUTH_ENABLED=true 时校验 Authorization: Bearer <token>。
    """
    if not AUTH_ENABLED:
        return {"sub": "anonymous"}

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise APIError("未提供认证信息，请先登录", status_code=401)

    token = auth_header[len("Bearer "):]
    return verify_token(token)
