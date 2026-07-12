"""认证路由：登录 / 当前用户信息 / 认证状态"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import AUTH_ENABLED
from app.utils.auth import authenticate, require_auth
from app.utils.response import success, APIError

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(req: LoginRequest):
    """用户登录，返回 JWT token"""
    if not AUTH_ENABLED:
        raise APIError("认证未启用，无需登录", status_code=400)
    token = authenticate(req.username, req.password)
    if not token:
        raise APIError("用户名或密码错误", status_code=401)
    return success({"token": token, "username": req.username}, message="登录成功")


@router.get("/me")
async def me(user=Depends(require_auth)):
    """获取当前登录用户信息"""
    return success({"username": user.get("sub", "unknown")})


@router.get("/status")
async def auth_status():
    """获取认证开关状态（前端用于判断是否需要登录）"""
    return success({"auth_enabled": AUTH_ENABLED})
