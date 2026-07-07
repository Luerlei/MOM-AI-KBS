"""统一响应格式"""
from typing import Any, Optional
from fastapi.responses import JSONResponse


def success(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def error(message: str = "error", code: int = -1, data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data}


def page_result(items: list, total: int, page: int, page_size: int) -> dict:
    return {
        "code": 0,
        "message": "success",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
        },
    }


class APIError(Exception):
    """自定义API异常"""

    def __init__(self, message: str, code: int = -1, status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
