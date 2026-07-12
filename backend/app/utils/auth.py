"""JWT 认证工具

当 AUTH_ENABLED=true 时，敏感 API 需要 Bearer token 认证。
默认关闭（开发环境），生产环境通过环境变量开启。
"""
import hmac
import jwt
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Request
from app.config import SECRET_KEY, AUTH_ENABLED, ADMIN_USERNAME, ADMIN_PASSWORD, JWT_EXPIRE_HOURS
from app.utils.response import APIError

logger = logging.getLogger(__name__)


def _is_bcrypt_hash(password: str) -> bool:
    """检查密码是否为 bcrypt 哈希格式（$2b$、$2a$、$2y$ 前缀）"""
    return password.startswith(("$2b$", "$2a$", "$2y$")) and len(password) == 60


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
    """验证用户名密码，成功返回 token，失败返回 None

    B-1: 支持 bcrypt 哈希密码（ADMIN_PASSWORD 以 $2b$ 开头时使用 bcrypt 验证）。
    B-14: 明文密码使用 hmac.compare_digest 常量时间比较，防止时序攻击。
    """
    # 常量时间比较用户名
    username_ok = hmac.compare_digest(username.encode("utf-8"), ADMIN_USERNAME.encode("utf-8"))
    if not username_ok:
        return None

    # B-1: 密码验证——支持 bcrypt 哈希和明文两种模式
    if _is_bcrypt_hash(ADMIN_PASSWORD):
        # bcrypt 哈希模式：用 bcrypt.checkpw 验证
        try:
            import bcrypt
            if bcrypt.checkpw(password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8")):
                return create_access_token(username)
        except Exception:
            logger.exception("[authenticate] bcrypt 验证异常")
        return None
    else:
        # 明文模式：常量时间比较（向后兼容）
        password_ok = hmac.compare_digest(password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))
        if password_ok:
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
