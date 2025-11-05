# GrowFit Backend

FastAPI + SQLAlchemy + PostgreSQL + Alembic 기반. 초기 벡터 스토어는 **pgvector**, 추후 **Qdrant**로 전환 예정. 티어는 **supervisor → Partner → User(Student)**.

## 기술 스택

* Python **3.14**
* FastAPI, Uvicorn
* SQLAlchemy, Alembic
* PostgreSQL 16 (+ `pgvector`)
* LangChain, PyMuPDF 등 인제스트 파이프라인
* 프론트 샘플 화면 리소스 포함
  예: 파트너 대시보드(Partner Admin), 조직/사용자 관리, 사용자 관리 페이지 초기화 로그, 시스템 모니터링 인시던트 기록, AI 실습·문서 연계, 유틸리티 함수 모듈.

## 권한 티어와 데이터 스코프

* **supervisor**: 플랫폼 전역 운영. 조직/사용자 총괄, 과금·리포트, 시스템 설정·모니터링. 관련 화면: 플랫폼 설정(API/보안), 시스템 모니터링, 분석 리포트 예약/내보내기.
* **Partner**: 개별 조직 단위 운영. 파트너 대시보드, 조직/사용자 관리. 관련 화면: 파트너 대시보드, 조직 관리 테이블·필터, 사용자 관리 데이터/성능 로그.
* **User(Student)**: 프로젝트·문서·에이전트·AI 실습 사용. 문서 업로드→임베딩→대화 연계, 히스토리에서 실습/문서로 이동.

## 폴더 구조

```
├── APP/                 # FastAPI 엔드포인트
├── CORE/                # 설정, 공통 유틸
├── CRUD/                # DB 접근 로직
├── DATABASE/            # Alembic 마이그레이션
├── LANGCHAIN_SERVICE/
│   ├── Chain/           # QA, 파일 처리 체인
│   ├── Embedding/       # 벡터화
│   ├── llm/             # ChatOpenAI 등 LLM 어댑터
│   └── Memory/          # 대화 메모리
├── MODELS/              # SQLAlchemy ORM
├── SCHEMAS/             # Pydantic 스키마
└── SERVICE/             # 도메인 서비스
```

프론트 샘플(문서·실습·에이전트 등)과 공통 자원:

* `my-documents.html` 문서 업로드·RAG 처리·실습 연계
* `practice.html` 모델별 응답 카드, 토큰·시간 지표
* `my-agents.html` 에이전트 빌더·공유·통계
* 공통 유틸 `utils.js` 날짜·숫자·토스트 API

## 빠른 시작

### 1) 의존성

* Python 3.14
* PostgreSQL 16
* 확장: `CREATE EXTENSION IF NOT EXISTS vector;`  (pgvector)
* 옵션: Redis 등 캐시(선택)

### 2) 가상환경 및 설치

```bash
python3.14 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
```

### 3) 환경 변수

`.env` 예시:

```
APP_ENV=dev
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/growfit
VECTOR_BACKEND=pgvector          # 추후 qdrant 로 전환 가능
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=...
```

### 4) DB 마이그레이션

```bash
alembic upgrade head         # 최초엔 alembic init 후 env.py 설정
# 변경 발생 시
alembic revision --autogenerate -m "desc"
alembic upgrade head
```

### 5) 서버 실행

가장 단순한 `main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="GrowFit API")

@app.get("/health")
def health():
    return {"status": "ok"}
```

실행:

```bash
uvicorn main:app --reload --port 8000
```

## 데이터베이스 가이드

* 스키마 권장: `supervisor`, `partner`, `user` 3단 구성.
* 외래키는 상위→하위 방향으로 제약. 전역 테이블(supervisor.*)은 상위 기준 관리.
* 스냅샷·로그성 테이블은 쓰기 전용, 조회 API 분리(추후 분석·리포트와 분리).

## 벡터 스토어 추상화와 **pgvector → Qdrant** 전환

전환 코스트를 낮추기 위해 **어댑터 계층**을 둔다.

### 1) 인터페이스

```python
class VectorStoreAdapter:
    def upsert_embeddings(self, items: list[tuple[doc_id, vector, metadata]]) -> None: ...
    def query(self, vector, top_k: int, filters: dict | None = None) -> list: ...
    def delete_by_doc_id(self, doc_id: str) -> None: ...
```

### 2) 구현체

* `PgVectorAdapter`

  * 테이블: `embeddings(doc_id uuid, embedding vector(1536), metadata jsonb, ...)`
  * GIN/HNSW 인덱스 전략 선택
* `QdrantAdapter`

  * 컬렉션: `growfit_docs`
  * 벡터 필드 + payload 메타데이터

런타임 스위치: `VECTOR_BACKEND=pgvector|qdrant`.

### 3) 마이그레이션 단계

1. **듀얼 라이트 준비**: 어댑터 주입으로 쓰기 경로를 양쪽에 기록.
2. **백필 배치**: 기존 pgvector → Qdrant로 백필(문서 ID 기준 upsert).
3. **읽기 전환**: 쿼리 우선순위를 Qdrant로 전환. 성능·정확도 검증.
4. **pgvector 단계적 정리**: 듀얼 라이트 중단, 백업 후 테이블 정리.

### 4) 쿼리 호환 지침

* 코사인/내적 거리 계산 차이를 어댑터에서 흡수.
* 필터(메타데이터) 표현은 공통 dict 스키마로 정규화.
* LangChain Retriever를 사용할 경우 `VectorStoreAdapter`를 감싼 커스텀 Retriever로 일원화.

## 인제스트 파이프라인

* 업로드 → 타입 검증 → 청크 → 임베딩 → 색인 → 사용
  프론트 샘플에도 동일 흐름을 노출(업로드·RAG 처리·대화 연계).

## 품질/운영

* 시스템 모니터링과 인시던트 기록 예시 제공.
* 분석/리포트 예약 및 내보내기 플로우 샘플 제공.
* 공통 유틸(날짜/숫자/토스트)로 UI·로그 일관성 유지.

## 코드 스타일/규칙

* Pydantic v2 기반 스키마.
* Alembic autogenerate 사용 시 제약/인덱스 네이밍 컨벤션 통일.
* 서비스 계층에서 트랜잭션 경계 명확화.
* 어댑터 주입으로 I/O 의존성 역전.

## 라이선스

사내/프로젝트 정책에 따름.

---

### 참고 리소스(샘플 화면)

* 파트너 대시보드: Partner Admin 타이틀
* 조직 관리 테이블·필터: 조직명/플랜/사용자수/상태
* 사용자 관리: 데이터/퍼포먼스 로그 표시
* 플랫폼 설정: API/보안 섹션
* 문서→실습 연계: practice.html 이동
* 공통 유틸: 날짜/숫자/토스트 함수
