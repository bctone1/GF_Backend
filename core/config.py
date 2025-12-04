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

# 2) 확장자
DOCUMENT_EXTENSION = os.getenv("DOCUMENT_EXTENSION", ".txt,.pdf,.docx,.doc,.csv")
IMAGE_EXTENSION = os.getenv("IMAGE_EXTENSION", ".png,.jpg")

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
    f"{DB}://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}:{DB_PORT}/{DB_NAME}" if all([DB_USER, DB_PASSWORD, DB_SERVER, DB_NAME]) else ""
)

# 7) 임베딩·채팅·Chroma
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
CHROMA_PERSIST_DIRECTORY = os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db")

# 8) 모델 카탈로그
OPENAI_MODELS = os.getenv("OPENAI_MODELS", "gpt-4,gpt-4o,gpt-4-turbo")
CLAUDE_MODELS = os.getenv("CLAUDE_MODELS", "")
ANTHROPIC_MODELS = os.getenv("ANTHROPIC_MODELS", "")
GOOGLE_MODELS = os.getenv("GOOGLE_MODELS", "")
FRIENDLI_MODELS = os.getenv("FRIENDLI_MODELS", "")
DEFAULT_CHAT_MODEL = os.getenv("DEFAULT_CHAT_MODEL", "gpt-4o-mini")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL    = os.getenv("LLM_MODEL", DEFAULT_CHAT_MODEL)


# 9) 엔드포인트
EXAONE_ENDPOINT = os.getenv("EXAONE_ENDPOINT")
EXAONE_URL = os.getenv("EXAONE_URL", "https://api.friendli.ai/dedicated/v1")

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
        "gpt-4o-mini": {"per_1k_token_usd": 0.00004},    # 대략적으로 잡음
    },
    "stt": {
        "CLOVA_STT": {"per_second_usd": 0.0002},  # 엄밀히 0.00019(환율차로 무의미)
    },
}


TIMEZONE = "Asia/Seoul"
COST_PRECISION = 6
TOKEN_UNIT = 1000
LLM_TOKEN_MODE = "merged"

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_STT_MODEL = "CLOVA_STT"

ENABLE_API_USAGE_LOG = False  # 기본은 로그 비활성화


# CLOVA STT 과금 규칙
CLOVA_STT_BILLING_UNIT_SECONDS = 6   # 6초 단위 과금
CLOVA_STT_PRICE_PER_UNIT_KRW = 1.6      # 15초당 4원
FX_KRW_PER_USD = 1400                 # 원→달러 환산. 미사용 시 None

DEFAULT_ORGANIZATION_ID = "1"

# 13) 모델 프로바이더 매핑정의
ProviderName = Literal["lg", "openai", "anthropic", "google"]
class PracticeModelConfig(TypedDict):
    provider: ProviderName
    model_name: str          # 실제 API 모델명
    display_name: str        # UI 표기용 (원하면)
    enabled: bool            # 나중에 on/off 용도


# 실습용 고정 모델 4개
PRACTICE_MODELS = {
    "gpt-4o-mini": {
        "provider": "openai",
        "model_name": "gpt-4o-mini",
        "display_name": "GPT-4o mini",
        "enabled": True,
        "default": True,
    },
    "gpt-5-nano": {
        "provider": "openai",
        "model_name": "gpt-5-nano",
        "display_name": "GPT-5 nano",
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
        "enabled": True,
        "default": False,
    },
}

    # "gemini-2.5-flash": {
    #     "provider": "google",
    #     "model_name": "gemini-2.5-flash",
    #     "display_name": "Gemini 2.5 Flash",
    #     "enabled": True,
    #     "default": False,
    # },
    # "exaone-4.0": {
    #     "provider": "lg",
    #     "model_name": "exaone-4.0",
    #     "display_name": "EXAONE 4.0",
    #     "enabled": True,
    #     "default": False,
    # },
# }
