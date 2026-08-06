"""
TerraForge 全局配置
================
所有配置项均可通过环境变量或 .env 文件覆盖，遵循 12-Factor 原则。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------------- 应用 ----------------
    APP_NAME: str = "TerraForge 土木工程智能知识平台"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = ["*"]

    # ---------------- 日志 ----------------
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = str(PROJECT_ROOT / "logs")
    LOG_RETENTION_DAYS: int = 14

    # ---------------- 数据库 ----------------
    # 生产: mysql+pymysql://user:pwd@host:3306/terraforge?charset=utf8mb4
    # 开发: sqlite:///./terraforge.db  （零依赖启动）
    DATABASE_URL: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'terraforge.db'}"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ---------------- Redis ----------------
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = False
    CACHE_TTL_SECONDS: int = 3600

    # ---------------- 向量库 ----------------
    # milvus | local  (local = 内置轻量向量库，便于零依赖运行与测试)
    VECTOR_BACKEND: Literal["milvus", "local"] = "local"
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_USER: str = ""
    MILVUS_PASSWORD: str = ""
    MILVUS_COLLECTION: str = "terraforge_chunks"
    MILVUS_INDEX_TYPE: str = "HNSW"
    MILVUS_METRIC_TYPE: str = "COSINE"
    LOCAL_VECTOR_DIR: str = str(PROJECT_ROOT / "data" / "vectorstore")

    # ---------------- LLM ----------------
    LLM_PROVIDER: Literal["openai_compatible", "mock"] = "mock"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 2048
    LLM_TIMEOUT: int = 90

    # ---------------- Embedding ----------------
    EMBEDDING_PROVIDER: Literal["openai_compatible", "hash"] = "hash"
    EMBEDDING_BASE_URL: str = "https://api.openai.com/v1"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1024
    EMBEDDING_BATCH_SIZE: int = 32

    # ---------------- Rerank ----------------
    # cross_encoder_api  : 远程 bge-reranker 类 HTTP 服务（需 RERANK_BASE_URL）
    # cross_encoder_local: 本地 CrossEncoder 风格重排器（向量交互+词面，零依赖，默认）
    # rule               : 纯规则重排（兜底）
    RERANK_PROVIDER: Literal["cross_encoder_api", "cross_encoder_local", "rule"] = "cross_encoder_local"
    RERANK_BASE_URL: str = ""
    RERANK_API_KEY: str = ""
    RERANK_MODEL: str = "bge-reranker-v2-m3"
    RERANK_TIMEOUT: int = 30

    # ---------------- Intent Agent（Sprint 2 查询意图路由）----------------
    # 开启后用 LLM 做结构化意图分类（需 LLM_API_KEY），否则用规则兜底
    INTENT_AGENT_ENABLED: bool = True
    # 是否允许把"与工程无关"的问题标记为越域（越域的 unknown 问题不强行检索）
    INTENT_OUT_OF_SCOPE: bool = True

    # ---------------- 文档处理 ----------------
    UPLOAD_DIR: str = str(PROJECT_ROOT / "data" / "uploads")
    MAX_UPLOAD_MB: int = 100
    CHUNK_SIZE: int = 600
    CHUNK_OVERLAP: int = 100
    MIN_CHUNK_SIZE: int = 40

    # ---------------- 检索 ----------------
    RETRIEVAL_TOP_K: int = 20          # 单路召回数量
    RERANK_TOP_N: int = 6              # 重排后进入上下文的数量
    HYBRID_VECTOR_WEIGHT: float = 0.6  # 向量通道权重
    HYBRID_BM25_WEIGHT: float = 0.4    # 关键词通道权重
    RRF_K: int = 60                    # RRF 融合常数
    SCORE_THRESHOLD: float = 0.15      # 召回分数下限

    # ---------------- 相关性门槛（防止"无依据硬答"） ----------------
    # 重排后 top1 必须达到该分数，否则视为知识库未覆盖该问题
    MIN_RELEVANCE_SCORE: float = 0.45
    # 且至少需要 MIN_SUPPORT_COUNT 条达到 MIN_RELEVANCE_SCORE*MIN_SUPPORT_RATIO，
    # 避免"孤证"（仅一条勉强擦边、其余断崖式无关）也被当成有效依据
    MIN_SUPPORT_RATIO: float = 0.75
    MIN_SUPPORT_COUNT: int = 2

    # ---------------- 可信度 ----------------
    CONFIDENCE_HIGH: float = 0.75
    CONFIDENCE_LOW: float = 0.45
    MAX_CONTEXT_CHARS: int = 8000
    MAX_HISTORY_ROUNDS: int = 6

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    def ensure_dirs(self) -> None:
        for p in (self.LOG_DIR, self.UPLOAD_DIR, self.LOCAL_VECTOR_DIR,
                  str(PROJECT_ROOT / "data")):
            Path(p).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s


settings = get_settings()
