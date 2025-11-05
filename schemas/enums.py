# schemas/enums.py
from enum import Enum

# 공통 상태
class Status(str, Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    draft = "draft"
    archived = "archived"

# 사용자 전용
class UserStatus(str, Enum):
    active = "active"
    suspended = "suspended"
    invited = "invited"
    deleted = "deleted"

# 조직/파트너 전용
class OrgStatus(str, Enum):
    active = "active"
    trial = "trial"
    inactive = "inactive"
    suspended = "suspended"

# 계정 삭제 요청
class AccountDeletionStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    rejected = "rejected"

# 결제/정산
class TransactionStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"
    canceled = "canceled"

class InvoiceStatus(str, Enum):
    draft = "draft"
    open = "open"
    paid = "paid"
    void = "void"
    uncollectible = "uncollectible"

class PayoutStatus(str, Enum):
    pending = "pending"
    in_transit = "in_transit"
    paid = "paid"
    failed = "failed"

# AI 사용량/프로바이더
class ProductType(str, Enum):
    llm = "llm"
    embedding = "embedding"
    stt = "stt"

class ProviderName(str, Enum):
    openai = "openai"
    anthropic = "anthropic"
    google = "google"
    upstage = "upstage"
    friendli = "friendli"
    naver_clova = "naver_clova"
    azure_openai = "azure_openai"

# 대화 메시지
class MessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"

# 작업 공통 상태(배치/인제스트 등)
class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"

# 통화
class Currency(str, Enum):
    KRW = "KRW"
    USD = "USD"
    JPY = "JPY"
