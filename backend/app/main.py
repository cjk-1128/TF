"""TerraForge 应用入口。"""
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, new_trace_id, setup_logging
from app.db.session import init_db

setup_logging()
logger = get_logger(__name__)

_FRONTEND_DIST_ENV = os.environ.get("TERRAFORGE_FRONTEND_DIST")
FRONTEND_DIST = (
    Path(_FRONTEND_DIST_ENV) if _FRONTEND_DIST_ENV
    else Path(__file__).resolve().parents[2] / "frontend" / "dist"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("%s v%s 启动中", settings.APP_NAME, settings.APP_VERSION)
    init_db()
    from app.llm.factory import get_embedding, get_llm, get_reranker
    from app.retrieval.bm25_index import get_bm25_index
    from app.vectorstore.factory import get_vector_store
    get_llm(); get_embedding(); get_reranker()
    vs, bm = get_vector_store(), get_bm25_index()
    logger.info("索引就绪 | 向量 %d 条 | BM25 %d 条", vs.count(), bm.count())
    logger.info("接口文档: http://%s:%d/docs", settings.HOST, settings.PORT)
    logger.info("=" * 60)
    # Sprint7-T2：启动质量巡检后台定时调度（周期巡检 + 阈值告警）
    from app.core.scheduler import start_quality_scheduler, stop_quality_scheduler
    start_quality_scheduler()
    yield
    stop_quality_scheduler()
    logger.info("%s 已停止", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "面向土木工程行业的企业级 RAG 智能知识平台。\n\n"
        "**架构**：Stage0 工程上下文 → Stage1 智能路由 → Stage2 查询改写 → "
        "Stage3 混合检索 → Stage4 重排序 → Stage5 上下文构建 → "
        "Stage6 智能生成与引用增强 → Stage7 知识治理闭环"
    ),
    docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    tid = new_trace_id()
    start = time.perf_counter()
    response = await call_next(request)
    cost = int((time.perf_counter() - start) * 1000)
    response.headers["X-Trace-Id"] = tid
    response.headers["X-Process-Time-Ms"] = str(cost)
    if not request.url.path.startswith(("/docs", "/openapi", "/static", "/assets")):
        logger.info("%s %s -> %d | %dms", request.method, request.url.path,
                    response.status_code, cost)
    return response


app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["系统"], summary="健康检查")
async def health():
    from app.retrieval.bm25_index import get_bm25_index
    from app.vectorstore.factory import get_vector_store
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "llm_provider": settings.LLM_PROVIDER,
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "vector_backend": settings.VECTOR_BACKEND,
        "vector_count": get_vector_store().count(),
        "bm25_count": get_bm25_index().count(),
    }


# ---------------- 前端静态托管 ----------------
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """Vue Router history 模式回退：非 API 路径统一返回 index.html。"""
        if full_path.startswith(("api/", "docs", "redoc", "openapi.json", "health")):
            return JSONResponse({"code": 404, "message": "接口不存在", "data": None},
                                status_code=404)
        static_file = FRONTEND_DIST / full_path
        if static_file.is_file():
            return FileResponse(static_file)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return JSONResponse({
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/health",
            "api_prefix": settings.API_V1_PREFIX,
        })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT,
                reload=settings.DEBUG)
