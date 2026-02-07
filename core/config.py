# core/config.py
import os
from pathlib import Path
from dotenv import load_dotenv
import base64
from typing import Literal, TypedDict

# 0) .env 로드
load_dotenv()

# 1) 경로
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "file" / "upload"))

# 2) 확장자 / 업로드 제한
DOCUMENT_EXTENSION = os.getenv("DOCUMENT_EXTENSION", ".txt,.pdf,.docx,.csv,.md")
IMAGE_EXTENSION = os.getenv("IMAGE_EXTENSION", ".png,.jpg")
DOCUMENT_MAX_SIZE_MB = int(os.getenv("DOCUMENT_MAX_SIZE_MB", "10"))
DOCUMENT_MAX_SIZE_BYTES = DOCUMENT_MAX_SIZE_MB * 1024 * 1024

# 3) 키·토큰
DEFAULT_API_KEY = os.getenv("DEFAULT_API_KEY")
OPENAI_API = os.getenv("OPENAI_API")
CLAUDE_API = os.getenv("CLAUDE_API")
GOOGLE_API = os.getenv("GOOGLE_API")
FRIENDLI_API = os.getenv("FRIENDLI_API")
EMBEDDING_API = os.getenv("EMBEDDING_API")
SEARCH_API = os.getenv("SEARCH_API")
UPSTAGE_API = os.getenv("UPSTAGE_API")

# 4) LangSmith
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING")  # 문자열 "true"/"false"
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT")
LANGSMITH_LOGGING_MODE = os.getenv("LANGSMITH_LOGGING_MODE", "full")

# 5) 이메일(SMTP)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

# 6) DB
DB = os.getenv("DB", "postgresql")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_SERVER = os.getenv("DB_SERVER", "")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "")

VECTOR_DB_CONNECTION = os.getenv(
    "VECTOR_DB_CONNECTION",
    f"{DB}://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}:{DB_PORT}/{DB_NAME}"
    if all([DB_USER, DB_PASSWORD, DB_SERVER, DB_NAME])
    else ""
)

# 7) 임베딩 / 벡터DB(Chroma)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
CHROMA_PERSIST_DIRECTORY = os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db")

# 임베딩 모델별 차원 기본값(지식베이스 설정 sanity-check용)
EMBEDDING_MODEL_DIMS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
}

# 8) 모델 카탈로그
OPENAI_MODELS = os.getenv("OPENAI_MODELS", "gpt-4o-mini,gpt-5-mini,gpt-3.5-turbo")
CLAUDE_MODELS = os.getenv("CLAUDE_MODELS", "")
ANTHROPIC_MODELS = os.getenv("ANTHROPIC_MODELS", "")
GOOGLE_MODELS = os.getenv("GOOGLE_MODELS", "")
FRIENDLI_MODELS = os.getenv("FRIENDLI_MODELS", "LGAI-EXAONE/K-EXAONE-236B-A23B")
DEFAULT_CHAT_MODEL = os.getenv("DEFAULT_CHAT_MODEL", "gpt-4o-mini")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", DEFAULT_CHAT_MODEL)

# 9) 엔드포인트
EXAONE_ENDPOINT = os.getenv("EXAONE_ENDPOINT")
EXAONE_URL = os.getenv("EXAONE_URL", "https://api.friendli.ai/serverless/v1")

# 10) 관리자·문자
COOL_SMS_API = os.getenv("COOL_SMS_API")
COOL_SMS_SECRET = os.getenv("COOL_SMS_SECRET")
ADMIN_PHONE_NUMBER = os.getenv("ADMIN_PHONE_NUMBER")

# 11) Friendli·Ollama
TEAM_ID = os.getenv("TEAM_ID")
FRIENDLI_TOKEN = os.getenv("FRIENDLI_TOKEN")
FRIENDLI_BASE_URL = os.getenv("FRIENDLI_BASE_URL")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")

# 12) cost usage 설정
API_PRICING = {
    "embedding": {
        "text-embedding-3-small": {"per_1k_token_usd": 0.00002},
        # "text-embedding-3-large": {"per_1k_token_usd": 0.13},
    },
    "llm": {
        "gpt-4o-mini": {"per_1k_token_usd": 0.00004},  # 대략적으로 잡음
    },
    "stt": {
        "CLOVA_STT": {"per_second_usd": 0.0002},
    },
}

TIMEZONE = "Asia/Seoul"

# 비용 견적 상수(구현 하기 전)
from decimal import Decimal as _Decimal
PLATFORM_FEE_PER_STUDENT = _Decimal("5000")       # 학생당 플랫폼 수수료 (KRW)
DAILY_API_FEE_ESTIMATE = _Decimal("1500")          # 학생·일·모델당 API 비용 추정 (KRW)
API_FEE_DISCOUNT_FACTOR = _Decimal("0.7")          # API 비용 할인 계수

COST_PRECISION = 6
TOKEN_UNIT = 1000
LLM_TOKEN_MODE = "merged"

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_STT_MODEL = "CLOVA_STT"

ENABLE_API_USAGE_LOG = False  # 기본은 로그 비활성화

# CLOVA STT 과금 규칙
CLOVA_STT_BILLING_UNIT_SECONDS = 6
CLOVA_STT_PRICE_PER_UNIT_KRW = 1.6
FX_KRW_PER_USD = 1450

DEFAULT_ORGANIZATION_ID = "1"

# 13) 모델 프로바이더 매핑 정의
ProviderName = Literal["lg", "openai", "anthropic", "google"]

class PracticeModelConfig(TypedDict):
    provider: ProviderName
    model_name: str
    display_name: str
    enabled: bool

# 14) 지식베이스 기본값(일반 모드 표준) — 유사도(min_score) 기준
KB_SCORE_TYPE = "cosine_similarity"  # 혼용 금지(거리 기반 max_distance 같은 거 쓰지 말기)

DEFAULT_INGESTION = {
    "chunk_size": 800,
    "chunk_overlap": 100,
    "max_chunks": 200,
    "chunk_strategy": "recursive",    # ["\n\n", "\n", " ", ""] 이런거 분할
    "embedding_provider": "openai",
    "embedding_model": DEFAULT_EMBEDDING_MODEL,
    "embedding_dim": EMBEDDING_MODEL_DIMS.get(DEFAULT_EMBEDDING_MODEL, 1536),
    "extra": {},
}

DEFAULT_SEARCH = {
    "top_k": 5,
    "min_score": 0.20,  # 0~1 (cosine_similarity 기준)
    "score_type": KB_SCORE_TYPE,
    "reranker_enabled": False,
    "reranker_model": None,
    "reranker_top_n": 5,
}

# 15) 실습용 고정 모델
PRACTICE_MODELS = {
    "gpt-4o-mini": {
        "provider": "openai",
        "model_name": "gpt-4o-mini",
        "display_name": "GPT-4o mini",
        "enabled": True,
        "default": True,
    },
    "gpt-5-mini": {
        "provider": "openai",
        "model_name": "gpt-5-mini",
        "display_name": "GPT-5 mini",
        "enabled": True,
        "default": False,
    },
    "gpt-3.5-turbo": {
        "provider": "openai",
        "model_name": "gpt-3.5-turbo",
        "display_name": "GPT-3.5 Turbo",
        "enabled": True,
        "default": False,
    },
    "claude-3-haiku-20240307": {
        "provider": "anthropic",
        "model_name": "claude-3-haiku-20240307",
        "display_name": "Claude 3 Haiku (2024-03-07)",
        "max_output_tokens": 4096,  # 모델 상한선 있음
        "enabled": True,
        "default": False,
    },
    "gemini-2.5-flash": {
        "provider": "google",
        "model_name": "gemini-2.5-flash",
        "display_name": "Gemini 2.5 Flash",
        "enabled": True,
        "default": False,
    },
    "LGAI-EXAONE/K-EXAONE-236B-A23B": {
        "provider": "friendli",
        "model_name": "LGAI-EXAONE/K-EXAONE-236B-A23B",
        "display_name": "EXAONE 236B A23B (Friendli)",
        "enabled": True,
        "default": False,
    },
}

# 16) LLM TUNING
PRACTICE_DEFAULT_GENERATION = {
    "temperature": 0.7,
    "top_p": 0.9,
    "response_length_preset": None,
    "max_completion_tokens": 10240,
}

RESPONSE_LENGTH_PRESETS = {
    "short": 256,
    "normal": 512,
    "long": 2048,
}

# 정합성 고정값 (운영 중 바꾸면 사고나는 것들은 고정)
EMBEDDING_DIM_FIXED = 1536
KB_SCORE_TYPE_FIXED = "cosine_similarity"

# 튜닝 가능한 기본값(운영 중 변경 가능)
DEFAULT_INGESTION = {
    # mode
    "chunking_mode": "general",         # "general" | "parent_child"
    "segment_separator": "\n\n",        # parent_child일 때 사용(빈줄 split)
    # child chunk
    "chunk_size": 600,
    "chunk_overlap": 200,
    "max_chunks": 100,
    "chunk_strategy": "recursive",      # MVP: "recursive"만
    # parent chunk (parent_child일 때만 의미)
    "parent_chunk_size": 1500,
    "parent_chunk_overlap": 400,
    # embedding
    "embedding_provider": "openai",
    "embedding_model": "text-embedding-3-small",
    # 기타
    "extra": {},
}

DEFAULT_SEARCH = {
    "top_k": 8,
    "min_score": "0.20",                # Decimal로 파싱될 거라 문자열 추천
    "score_type": KB_SCORE_TYPE_FIXED,  # 고정
    "reranker_enabled": False,
    "reranker_model": None,
    "reranker_top_n": 5,                # <= top_k
}
