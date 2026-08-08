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
    # 日志格式：text（默认，管道分隔）或 json（结构化，便于采集）
    LOG_FORMAT: str = "text"

    # ---------------- 治理门禁阈值（Phase 5 门禁报告）----------------
    # 入库/发布前质量门禁：向量完整率（已分配 vector_id 切片占比）下限
    GATE_VECTOR_COMPLETENESS_MIN: float = 0.99
    # 质量巡检综合分下限
    GATE_QUALITY_SCORE_MIN: float = 80.0

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
    # 答案（管线结果）缓存：对完全相同的首轮问题直接复用上次计算结果，
    # 跳过 Stage0-7 全链路 + LLM 调用。多轮对话（带历史）不参与，避免上下文串缓存。
    CACHE_ANSWER_ENABLED: bool = True
    CACHE_ANSWER_TTL: int = 3600

    # ---------------- 通知（可选） ----------------
    # 治理任务自动创建后推送的 Webhook URL；为空则不推送（no-op）。
    NOTIFIER_WEBHOOK_URL: str = ""

    # ---------------- 向量库 ----------------
    # milvus | local  (local = 内置轻量向量库，便于零依赖运行与测试)
    VECTOR_BACKEND: Literal["milvus", "local"] = "local"
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_USER: str = ""
    MILVUS_PASSWORD: str = ""
    MILVUS_COLLECTION: str = "terraforge_chunks"   # 共享集合（VECTOR_TENANT_ISOLATION=False 时使用）
    MILVUS_COLLECTION_PREFIX: str = "tf_kb_"        # 按库隔离集合前缀 -> tf_kb_{kb_id}
    # 向量索引按知识库隔离：开启后每个 KB 独立 Milvus 集合(tf_kb_{kb_id}) + BM25 按库分区，
    # 删除知识库即 drop 整个集合/分区，根除「共享向量/BM25 索引污染」隐患（企业级生产改造）。
    VECTOR_TENANT_ISOLATION: bool = True
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

    # ---------------- 多租户 / RBAC（Sprint 4）----------------
    # 租户隔离维度：所有 KB/文档/切片/会话按 tenant_id 过滤；请求头 X-Tenant-Id 指定。
    DEFAULT_TENANT_ID: str = "default"
    # 是否启用 API-Key 鉴权（写操作 + 问答强制）；关闭时一律以虚拟 admin 放行（仅演示用）。
    RBAC_ENABLED: bool = True
    # 首次启动若 tf_user 为空，自动 seed 的默认管理员 api_key（X-API-Key 携带）。
    BOOTSTRAP_API_KEY: str = "tf-admin-seed-key"
    API_KEY_HEADER: str = "X-API-Key"
    TENANT_HEADER: str = "X-Tenant-Id"

    # ---------------- 质量巡检定时 + 阈值告警（Sprint7-T2）----------------
    # 是否启用后台定时巡检（周期自动运行 + 阈值告警）。
    QUALITY_INSPECT_ENABLED: bool = True
    # 巡检周期（秒）；默认 1 小时。演示可设小值（如 120）观察调度。
    QUALITY_INSPECT_INTERVAL_SECONDS: int = 3600
    # 质量分低于该阈值触发 low_score 告警。
    QUALITY_ALERT_SCORE_THRESHOLD: float = 80.0
    # 相对上次巡检新增高危问题数 ≥ 该值触发 new_high_severity 告警。
    QUALITY_ALERT_NEW_HIGH_THRESHOLD: int = 1

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
    # BM25 通道候选放大倍数：词面召回常在更深处命中（精确规范号/术语/错别字的词面匹配），
    # 令 BM25 比向量通道多取若干倍候选再参与 RRF 融合，提升词面召回覆盖而不影响向量主信号。
    HYBRID_BM25_CANDIDATE_MULT: float = 2.0

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
