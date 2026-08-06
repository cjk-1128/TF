-- =====================================================================
--  TerraForge · 土木工程智能知识平台 · MySQL 初始化脚本
--  仅在 MySQL 部署时使用；SQLite 部署无需执行（后端会自动建表）
--  适用版本：MySQL 8.0+
-- =====================================================================

CREATE DATABASE IF NOT EXISTS terraforge
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE terraforge;

-- 知识库
CREATE TABLE IF NOT EXISTS knowledge_base (
    id              VARCHAR(64)  PRIMARY KEY,
    name            VARCHAR(128) NOT NULL,
    domain          VARCHAR(32)  NOT NULL COMMENT 'standard / case / enterprise',
    description     TEXT,
    owner           VARCHAR(64),
    tags            JSON,
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    created_at      DATETIME     NOT NULL,
    updated_at      DATETIME     NOT NULL,
    INDEX idx_kb_domain (domain),
    INDEX idx_kb_active (is_active)
) ENGINE=InnoDB;

-- 文档
CREATE TABLE IF NOT EXISTS documents (
    id                VARCHAR(64)  PRIMARY KEY,
    kb_id             VARCHAR(64)  NOT NULL,
    title             VARCHAR(255) NOT NULL,
    file_name         VARCHAR(255),
    file_path         VARCHAR(512),
    file_type         VARCHAR(32),
    file_size         BIGINT       NOT NULL DEFAULT 0,
    standard_code     VARCHAR(64),
    standard_name     VARCHAR(255),
    discipline        VARCHAR(32)  NOT NULL DEFAULT 'general',
    project_name      VARCHAR(128),
    governance_status VARCHAR(32)  NOT NULL DEFAULT 'valid',
    owner             VARCHAR(64),
    version           VARCHAR(32)  NOT NULL DEFAULT '1.0',
    summary           TEXT,
    keywords          JSON,
    tags              JSON,
    status            VARCHAR(32)  NOT NULL DEFAULT 'pending',
    error_msg         TEXT,
    effective_date    DATETIME,
    expire_date       DATETIME,
    created_at        DATETIME     NOT NULL,
    updated_at        DATETIME     NOT NULL,
    INDEX idx_doc_kb (kb_id),
    INDEX idx_doc_status (status),
    INDEX idx_doc_gov (governance_status),
    INDEX idx_doc_expire (expire_date)
) ENGINE=InnoDB;

-- 切片
CREATE TABLE IF NOT EXISTS chunks (
    id              VARCHAR(64)  PRIMARY KEY,
    doc_id          VARCHAR(64)  NOT NULL,
    seq             INT          NOT NULL DEFAULT 0,
    content         MEDIUMTEXT   NOT NULL,
    char_count      INT          NOT NULL DEFAULT 0,
    section_path    VARCHAR(512),
    clause_no       VARCHAR(64),
    page_no         INT          NOT NULL DEFAULT 0,
    is_mandatory    TINYINT(1)   NOT NULL DEFAULT 0,
    domain          VARCHAR(32)  NOT NULL DEFAULT 'standard',
    vector_id       VARCHAR(96),
    created_at      DATETIME     NOT NULL,
    INDEX idx_chunk_doc (doc_id),
    INDEX idx_chunk_domain (domain),
    INDEX idx_chunk_mandatory (is_mandatory)
) ENGINE=InnoDB;

-- 会话
CREATE TABLE IF NOT EXISTS conversations (
    id              VARCHAR(64)  PRIMARY KEY,
    title           VARCHAR(255) NOT NULL DEFAULT '新会话',
    user_id         VARCHAR(64)  NOT NULL DEFAULT 'anonymous',
    project_name    VARCHAR(128),
    project_type    VARCHAR(64),
    discipline      VARCHAR(32)  NOT NULL DEFAULT 'general',
    region          VARCHAR(64),
    kb_ids          JSON,
    created_at      DATETIME     NOT NULL,
    updated_at      DATETIME     NOT NULL,
    INDEX idx_conv_user (user_id),
    INDEX idx_conv_updated (updated_at)
) ENGINE=InnoDB;

-- 消息
CREATE TABLE IF NOT EXISTS messages (
    id                 VARCHAR(64)  PRIMARY KEY,
    conversation_id    VARCHAR(64)  NOT NULL,
    role               VARCHAR(16)  NOT NULL,
    content            MEDIUMTEXT   NOT NULL,
    intent             VARCHAR(32),
    intent_label       VARCHAR(64),
    rewritten_query    TEXT,
    confidence         FLOAT        NOT NULL DEFAULT 0,
    confidence_level   VARCHAR(16),
    need_human_review  TINYINT(1)   NOT NULL DEFAULT 0,
    review_hint        TEXT,
    latency_ms         INT          NOT NULL DEFAULT 0,
    token_usage        JSON,
    created_at         DATETIME     NOT NULL,
    INDEX idx_msg_conv (conversation_id, created_at)
) ENGINE=InnoDB;

-- 引用
CREATE TABLE IF NOT EXISTS citations (
    id            BIGINT       PRIMARY KEY AUTO_INCREMENT,
    message_id    VARCHAR(64)  NOT NULL,
    index_no      INT          NOT NULL,
    chunk_id      VARCHAR(64)  NOT NULL,
    doc_id        VARCHAR(64)  NOT NULL,
    doc_title     VARCHAR(255),
    standard_code VARCHAR(64),
    section_path  VARCHAR(512),
    clause_no     VARCHAR(64),
    page_no       INT,
    snippet       TEXT,
    score         FLOAT,
    domain        VARCHAR(32),
    INDEX idx_cite_msg (message_id)
) ENGINE=InnoDB;

-- 治理任务
CREATE TABLE IF NOT EXISTS governance_tasks (
    id               VARCHAR(64)  PRIMARY KEY,
    task_type        VARCHAR(32)  NOT NULL,
    title            VARCHAR(255) NOT NULL,
    description      TEXT,
    target_doc_ids   JSON,
    kb_id            VARCHAR(64),
    priority         VARCHAR(16)  NOT NULL DEFAULT 'medium',
    status           VARCHAR(16)  NOT NULL DEFAULT 'open',
    assignee         VARCHAR(64),
    watchers         JSON,
    due_date         DATETIME,
    created_at       DATETIME     NOT NULL,
    updated_at       DATETIME     NOT NULL,
    INDEX idx_task_status (status),
    INDEX idx_task_kb (kb_id)
) ENGINE=InnoDB;

-- 反馈
CREATE TABLE IF NOT EXISTS feedback_records (
    id           BIGINT       PRIMARY KEY AUTO_INCREMENT,
    message_id   VARCHAR(64)  NOT NULL,
    rating       TINYINT      NOT NULL,
    reason       VARCHAR(64),
    comment      TEXT,
    created_at   DATETIME     NOT NULL,
    INDEX idx_fb_msg (message_id)
) ENGINE=InnoDB;

-- 查询日志（Stage7 知识盲区与运营报告的数据来源）
CREATE TABLE IF NOT EXISTS query_logs (
    id              BIGINT       PRIMARY KEY AUTO_INCREMENT,
    user_id         VARCHAR(64),
    conversation_id VARCHAR(64),
    query           TEXT         NOT NULL,
    intent          VARCHAR(32),
    rewritten_query TEXT,
    confidence      FLOAT        NOT NULL DEFAULT 0,
    confidence_level VARCHAR(16),
    latency_ms      INT          NOT NULL DEFAULT 0,
    retrieved_count INT          NOT NULL DEFAULT 0,
    citation_count  INT          NOT NULL DEFAULT 0,
    trace_id        VARCHAR(64),
    created_at      DATETIME     NOT NULL,
    INDEX idx_qlog_created (created_at),
    INDEX idx_qlog_intent (intent),
    INDEX idx_qlog_conf (confidence)
) ENGINE=InnoDB;