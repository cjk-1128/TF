"""业务异常体系 + 统一异常处理器。"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger, get_trace_id

logger = get_logger(__name__)


class TerraForgeError(Exception):
    code: int = 50000
    http_status: int = 500
    message: str = "系统内部错误"

    def __init__(self, message: str | None = None, detail: object = None):
        self.message = message or self.message
        self.detail = detail
        super().__init__(self.message)


class NotFoundError(TerraForgeError):
    code, http_status, message = 40400, 404, "资源不存在"


class ValidationError(TerraForgeError):
    code, http_status, message = 42200, 422, "参数校验失败"


class DocumentParseError(TerraForgeError):
    code, http_status, message = 50010, 500, "文档解析失败"


class EmbeddingError(TerraForgeError):
    code, http_status, message = 50020, 500, "向量化失败"


class VectorStoreError(TerraForgeError):
    code, http_status, message = 50030, 500, "向量库操作失败"


class LLMError(TerraForgeError):
    code, http_status, message = 50040, 500, "大模型调用失败"


class RetrievalError(TerraForgeError):
    code, http_status, message = 50050, 500, "检索失败"


def _payload(code: int, message: str, detail=None) -> dict:
    body = {"code": code, "message": message, "trace_id": get_trace_id(), "data": None}
    if detail is not None:
        body["detail"] = detail if isinstance(detail, (str, list, dict)) else str(detail)
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(TerraForgeError)
    async def _biz(request: Request, exc: TerraForgeError):
        logger.warning("业务异常 %s | %s | %s", exc.code, exc.message, request.url.path)
        return JSONResponse(status_code=exc.http_status,
                            content=_payload(exc.code, exc.message, exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _valid(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422,
                            content=_payload(42200, "参数校验失败", exc.errors()))

    @app.exception_handler(Exception)
    async def _unknown(request: Request, exc: Exception):
        logger.exception("未捕获异常 | %s", request.url.path)
        return JSONResponse(status_code=500,
                            content=_payload(50000, "系统内部错误", str(exc)))
