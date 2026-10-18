from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(
    os.getenv(
        "PROJECT_ROOT",
        Path(__file__).resolve().parent.parent,
    )
).resolve()

DATA_DIR = Path(
    os.getenv(
        "DATA_DIR",
        PROJECT_ROOT / "data",
    )
).resolve()

INCOMING_DIR = Path(
    os.getenv(
        "INCOMING_DIR",
        DATA_DIR / "incoming",
    )
).resolve()

OUTPUT_DIR = Path(
    os.getenv(
        "OUTPUT_DIR",
        PROJECT_ROOT / "outputs",
    )
).resolve()

REPORTS_DIR = Path(
    os.getenv(
        "REPORTS_DIR",
        OUTPUT_DIR / "reports",
    )
).resolve()


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

@dataclass(frozen=True)
class Settings:

    # --------------------------------------------------------
    # Application
    # --------------------------------------------------------

    app_name: str
    app_env: str
    log_level: str

    # --------------------------------------------------------
    # Agent API
    # --------------------------------------------------------

    agent_host: str
    agent_port: int

    # --------------------------------------------------------
    # PostgreSQL
    # --------------------------------------------------------

    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str

    # --------------------------------------------------------
    # Mock ERP
    # --------------------------------------------------------

    mock_erp_host: str
    mock_erp_port: int

    # --------------------------------------------------------
    # Redis
    # --------------------------------------------------------

    redis_host: str
    redis_port: int
    redis_db: int
    redis_ttl: int

    # --------------------------------------------------------
    # Qdrant
    # --------------------------------------------------------

    qdrant_host: str
    qdrant_port: int
    qdrant_collection: str

    # --------------------------------------------------------
    # LiteLLM / AWS Bedrock
    # --------------------------------------------------------

    llm_model: str
    rag_model: str
    translation_model: str
    llm_temperature: float
    llm_max_tokens: int

    # --------------------------------------------------------
    # Embeddings
    # --------------------------------------------------------

    embedding_model: str
    embedding_dimension: int

    # --------------------------------------------------------
    # RAG
    # --------------------------------------------------------

    rag_top_k: int
    rag_score_threshold: float
    rag_max_retries: int

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    amount_tolerance: float

    # --------------------------------------------------------
    # Paths
    # --------------------------------------------------------

    project_root: Path
    data_dir: Path
    incoming_dir: Path
    output_dir: Path
    reports_dir: Path

    # --------------------------------------------------------
    # OCR
    # --------------------------------------------------------

    ocr_enabled: bool
    ocr_languages: str


# ============================================================
# ENVIRONMENT HELPERS
# ============================================================

def _get_env(
    name: str,
    default: str | None = None,
) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        if default is not None:
            return default

        raise RuntimeError(
            f"Required environment variable '{name}' is not set."
        )

    return value.strip()


def _get_int(
    name: str,
    default: int | None = None,
) -> int:
    value = _get_env(
        name,
        str(default) if default is not None else None,
    )

    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(
            f"Environment variable '{name}' must be an integer. "
            f"Received: {value!r}"
        ) from exc


def _get_float(
    name: str,
    default: float | None = None,
) -> float:
    value = _get_env(
        name,
        str(default) if default is not None else None,
    )

    try:
        return float(value)
    except ValueError as exc:
        raise RuntimeError(
            f"Environment variable '{name}' must be a number. "
            f"Received: {value!r}"
        ) from exc


def _get_bool(
    name: str,
    default: bool = False,
) -> bool:
    value = _get_env(
        name,
        str(default),
    ).lower()

    if value in {"1", "true", "yes", "y", "on"}:
        return True

    if value in {"0", "false", "no", "n", "off"}:
        return False

    raise RuntimeError(
        f"Environment variable '{name}' must be a boolean. "
        f"Received: {value!r}"
    )


# ============================================================
# SETTINGS FACTORY
# ============================================================

def load_settings() -> Settings:

    settings = Settings(

        # ----------------------------------------------------
        # Application
        # ----------------------------------------------------

        app_name=_get_env(
            "APP_NAME",
            "AI Invoice Auditor",
        ),

        app_env=_get_env(
            "APP_ENV",
            "development",
        ),

        log_level=_get_env(
            "LOG_LEVEL",
            "INFO",
        ),

        # ----------------------------------------------------
        # Agent API
        # ----------------------------------------------------

        agent_host=_get_env(
            "AGENT_HOST",
            "0.0.0.0",
        ),

        agent_port=_get_int(
            "AGENT_PORT",
            8000,
        ),

        # ----------------------------------------------------
        # PostgreSQL
        # ----------------------------------------------------

        postgres_host=_get_env(
            "POSTGRES_HOST",
            "postgres",
        ),

        postgres_port=_get_int(
            "POSTGRES_PORT",
            5432,
        ),

        postgres_db=_get_env(
            "POSTGRES_DB",
            "invoice_auditor",
        ),

        postgres_user=_get_env(
            "POSTGRES_USER",
            "invoice_user",
        ),

        postgres_password=_get_env(
            "POSTGRES_PASSWORD",
            "invoice_password",
        ),

        # ----------------------------------------------------
        # Mock ERP
        # ----------------------------------------------------

        mock_erp_host=_get_env(
            "MOCK_ERP_HOST",
            "mock-erp",
        ),

        mock_erp_port=_get_int(
            "MOCK_ERP_PORT",
            8000,
        ),

        # ----------------------------------------------------
        # Redis
        # ----------------------------------------------------

        redis_host=_get_env(
            "REDIS_HOST",
            "redis",
        ),

        redis_port=_get_int(
            "REDIS_PORT",
            6379,
        ),

        redis_db=_get_int(
            "REDIS_DB",
            0,
        ),

        redis_ttl=_get_int(
            "REDIS_TTL",
            3600,
        ),

        # ----------------------------------------------------
        # Qdrant
        # ----------------------------------------------------

        qdrant_host=_get_env(
            "QDRANT_HOST",
            "qdrant",
        ),

        qdrant_port=_get_int(
            "QDRANT_PORT",
            6333,
        ),

        qdrant_collection=_get_env(
            "QDRANT_COLLECTION",
            "invoice_documents",
        ),

        # ----------------------------------------------------
        # LiteLLM / AWS Bedrock
        # ----------------------------------------------------

        # Reasoning / summarization
        llm_model=_get_env(
            "LLM_MODEL",
            "bedrock/amazon.nova-lite-v1:0",
        ),

        # RAG answer generation
        rag_model=_get_env(
            "RAG_MODEL",
            "bedrock/amazon.nova-lite-v1:0",
        ),

        # Translation
        translation_model=_get_env(
            "TRANSLATION_MODEL",
            "bedrock/amazon.nova-lite-v1:0",
        ),

        llm_temperature=_get_float(
            "LLM_TEMPERATURE",
            0.0,
        ),

        llm_max_tokens=_get_int(
            "LLM_MAX_TOKENS",
            1500,
        ),

        # ----------------------------------------------------
        # Embeddings
        # ----------------------------------------------------

        # Bedrock Cohere embedding model.
        # IMPORTANT:
        # This is NOT an OpenAI embedding model.
        embedding_model=_get_env(
            "EMBEDDING_MODEL",
            "bedrock/amazon.titan-embed-text-v1",
        ),

        # Cohere Embed English v3 produces 1024-dimensional
        # embeddings.
        embedding_dimension=_get_int(
            "EMBEDDING_DIMENSION",
            1024,
        ),

        # ----------------------------------------------------
        # RAG
        # ----------------------------------------------------

        rag_top_k=_get_int(
            "RAG_TOP_K",
            5,
        ),

        rag_score_threshold=_get_float(
            "RAG_SCORE_THRESHOLD",
            0.7,
        ),

        rag_max_retries=_get_int(
            "RAG_MAX_RETRIES",
            3,
        ),

        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        amount_tolerance=_get_float(
            "AMOUNT_TOLERANCE",
            0.01,
        ),

        # ----------------------------------------------------
        # Paths
        # ----------------------------------------------------

        project_root=PROJECT_ROOT,
        data_dir=DATA_DIR,
        incoming_dir=INCOMING_DIR,
        output_dir=OUTPUT_DIR,
        reports_dir=REPORTS_DIR,

        # ----------------------------------------------------
        # OCR
        # ----------------------------------------------------

        ocr_enabled=_get_bool(
            "OCR_ENABLED",
            True,
        ),

        ocr_languages=_get_env(
            "OCR_LANGUAGES",
            "eng+vie",
        ),
    )

    return settings


# ============================================================
# GLOBAL SETTINGS INSTANCE
# ============================================================

settings = load_settings()


# ============================================================
# DIRECTORY INITIALIZATION
# ============================================================

def ensure_directories() -> None:

    settings.incoming_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    settings.output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    settings.reports_dir.mkdir(
        parents=True,
        exist_ok=True,
    )