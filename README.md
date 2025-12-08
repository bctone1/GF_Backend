# GrowFit Backend

FastAPI + SQLAlchemy + PostgreSQL + Alembic 기반. 초기 벡터 스토어는 **pgvector**, 추후 **Qdrant**로 전환 예정. 권한 티어는 **Supervisor → Org → Partner → Student/User**.

## 기술 스택

* Python **3.12** (현재 권장 버전)

  * Python **3.14**는 추후 업그레이드 타깃 (LangChain/Pydantic 생태계 안정화 이후)
* FastAPI, Uvicorn
* SQLAlchemy, Alembic
* PostgreSQL 16 (+ `pgvector`)
* LangChain, PyMuPDF 등 인제스트 파이프라인
* 프론트 샘플 화면 리소스 포함
  예: 파트너 대시보드(Partner Admin), 조직/사용자 관리, 사용자 관리 페이지 초기화 로그, 시스템 모니터링 인시던트 기록, AI 실습·문서 연계, 유틸리티 함수 모듈.

### Python 버전 관련 메모

현재 운영 기준:

* **기본 개발/운영 버전: Python 3.12**
* LangChain / langchain_core 일부 모듈이 Python 3.14에서
  `Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.`
  경고를 발생시키는 이슈가 있음.
* 이 경고를 회피하고 안정성을 우선하기 위해,
  당분간은 **3.12에서 개발/운영 → 이후 3.14로 업그레이드**하는 전략을 사용.
* 향후 계획:

  1. LangChain / OpenAI SDK / 관련 의존성들이 3.14 완전 지원을 명시하면
  2. CI에서 3.12 / 3.14 멀티 버전 테스트 추가
  3. 문제가 없으면 운영 환경을 3.14로 승격

---

## 권한 티어와 데이터 스코프

* **Supervisor**: 플랫폼 전역 운영

  * 조직/사용자 총괄, 과금·리포트, 시스템 설정·모니터링
  * 관련 화면: 플랫폼 설정(API/보안), 시스템 모니터링, 분석 리포트 예약/내보내기

* **Org(조직)**: 파트너/강사 풀 관리 및 과정 설계

  * Org 단위 코스(course) 개설, 파트너/강사 계정 연결, 정산 정책 관리

* **Partner(강사/운영자)**: 개별 조직 단위의 실질 운영

  * 강의(class) 개설, 초대 코드 발급, 학생/수강 관리, 실습/과금 모니터링
  * 관련 화면: 파트너 대시보드, 조직 관리 테이블·필터, 사용자 관리/활동 로그

* **Student/User**:

  * 학생(Student): 초대 코드 기반 수강, 실습/대화/문서 사용
  * 일반 User: 기본 계정, 프로젝트·문서·에이전트·AI 실습 사용
  * 기능: 문서 업로드 → 임베딩 → 대화 연계, 히스토리에서 실습/문서로 이동

---

## 폴더 구조

실제 코드 구조 기준(소문자 디렉터리):

```bash
├── app/                 # FastAPI 엔드포인트
├── core/                # 설정, 공통 유틸
├── crud/                # DB 접근 로직
├── database/            # Alembic 마이그레이션
├── langchain_service/
│   ├── chain/           # QA, 파일 처리 체인
│   ├── embedding/       # 벡터화
│   ├── llm/             # ChatOpenAI 등 LLM 어댑터
│   └── memory/          # 대화 메모리
├── models/              # SQLAlchemy ORM
├── schemas/             # Pydantic 스키마
└── service/             # 도메인 서비스 계층
```

프론트 샘플(문서·실습·에이전트 등)과 공통 자원:

* `my-documents.html` 문서 업로드·RAG 처리·실습 연계
* `practice.html` 모델별 응답 카드, 토큰·시간 지표
* `my-agents.html` 에이전트 빌더·공유·통계
* (있다면) 공통 유틸 `utils.js` 날짜·숫자·토스트 API

---

## 빠른 시작

### 1) 의존성

* Python **3.12**

  * Windows: `py -3.12`
  * macOS/Linux: `python3.12` 또는 기본 `python`이 3.12를 가리키도록 설정
* PostgreSQL 16
* 확장: `CREATE EXTENSION IF NOT EXISTS vector;`  (pgvector)
* 옵션: Redis 등 캐시(선택)

### 2) 가상환경 및 설치

#### Windows (권장)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\activate

python -m pip install -U pip
python -m pip install -r requirements.txt
```

#### macOS / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate

pip install -U pip
pip install -r requirements.txt
```

> 다른 Python 버전이 섞이지 않도록, IDE/CI에서도 3.12 인터프리터를 명시적으로 선택하는 것을 권장.

### 3) 환경 변수

`.env` 예시:

```env
APP_ENV=dev
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/growfit

# 벡터 스토어 선택
VECTOR_BACKEND=pgvector          # 추후 qdrant 로 전환 가능

# (선택) Qdrant 설정
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=...
```

### 4) DB 마이그레이션

```bash
# 최신 상태로 업그레이드
alembic upgrade head

# 스키마 변경 발생 시
alembic revision --autogenerate -m "desc"
alembic upgrade head
```

> Python 버전 변경(3.12 ↔ 3.14)은 DB 스키마를 바꾸지 않기 때문에,
> **모델 변경이 없으면 Alembic upgrade는 불필요**.
> 다만 새 환경에서 최초 실행 시 `alembic current` / `alembic upgrade head`로 동기 상태를 확인하는 것을 권장.

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

---

## 데이터베이스 가이드

* 기본 스키마: `supervisor`, `partner`, `user` 3단 구성

  * `supervisor.*` : 플랫폼 전역 설정/메트릭/리포트/백업 등
  * `partner.*`    : 조직·파트너·코스·강의·학생·LLM 설정·Usage
  * `user.*`       : 개인 계정, 프로젝트, 실습 세션, 문서, 에이전트 등

* 외래키는 상위 → 하위 방향으로 제약

  * 예: `partner.students.user_id → user.app_user.user_id`
  * 예: `partner.classes.partner_id → partner.partners.partner_id`

* 스냅샷·로그성 테이블은 쓰기 전용, 조회용 API 분리

  * 예: usage, metrics, events, alerts 등
  * 추후 분석/리포트용 API와 별도 도메인으로 분리 가능

---

## 벡터 스토어 추상화와 **pgvector → Qdrant** 전환

전환 코스트를 낮추기 위해 **어댑터 계층**을 둔다.

### 1) 인터페이스

```python
class VectorStoreAdapter:
    def upsert_embeddings(
        self,
        items: list[tuple[str, list[float], dict]],
    ) -> None:
        ...

    def query(
        self,
        vector: list[float],
        top_k: int,
        filters: dict | None = None,
    ) -> list[dict]:
        ...

    def delete_by_doc_id(self, doc_id: str) -> None:
        ...
```

### 2) 구현체

* `PgVectorAdapter`

  * 테이블 예: `embeddings(doc_id uuid, embedding vector(1536), metadata jsonb, ...)`
  * GIN/HNSW 인덱스 전략 선택

* `QdrantAdapter`

  * 컬렉션 예: `growfit_docs`
  * 벡터 필드 + payload 메타데이터
  * Qdrant 클러스터/샤딩/replica 설정은 인프라 레벨에서 관리

런타임 스위치: 환경 변수로 제어

```env
VECTOR_BACKEND=pgvector  # or qdrant
```

### 3) 마이그레이션 단계

1. **듀얼 라이트 준비**

   * 서비스 계층에서 `VectorStoreAdapter`를 주입받도록 변경
   * pgvector + Qdrant 둘 다에 쓰기 가능하도록 구현

2. **백필 배치**

   * 기존 pgvector 데이터 → Qdrant로 백필
   * 문서 ID 기준으로 upsert

3. **읽기 전환**

   * 쿼리 우선순위를 Qdrant로 전환
   * 검색 품질/성능 검증

4. **pgvector 단계적 정리**

   * 듀얼 라이트 중단
   * 백업 후 pgvector 테이블 및 인덱스 정리

### 4) 쿼리 호환 지침

* 코사인/내적 거리 계산 차이는 어댑터 내부에서 흡수
* 필터(메타데이터)는 공통 dict 스키마로 정규화
* LangChain Retriever 사용 시:

  * `VectorStoreAdapter`를 감싼 커스텀 Retriever 구현
  * 상위 레이어에서는 백엔드 종류(pgvector/Qdrant)를 알 필요 없도록 설계

---

## 인제스트 파이프라인

기본 흐름:

1. 업로드
2. 타입 검증 (PDF, DOCX, TXT, 이미지 등)
3. 청크 분할 (텍스트/페이지 단위)
4. 임베딩 생성 (LangChain + 지정 모델)
5. 벡터 색인 (pgvector/Qdrant)
6. RAG/실습 세션에서 검색·대화 연계

프론트 샘플에서도 동일 흐름을 표시:
---

## 품질/운영

* 시스템 모니터링 + 인시던트 기록 화면 샘플 제공
* 분석/리포트 예약 및 내보내기 플로우 샘플 제공
* 공통 유틸(날짜/숫자/토스트)로 UI·로그 일관성 유지
* Python 3.12 / 3.14 멀티 버전 대응을 염두에 둔 테스트 전략:

  * 최소 smoke test: health check, DB 연결, 주요 API 호출
  * RAG/LLM 경로: 토큰 사용량/지연시간/에러율 모니터링

---

## 코드 스타일/규칙

* **Pydantic v2 기반 스키마**

  * `model_config = ConfigDict(from_attributes=True)` 등 일관 사용
* Alembic autogenerate 사용 시:

  * 제약/인덱스 네이밍 컨벤션 통일
  * 읽기 전용 집계 테이블에는 Create/Update 스키마 생성 금지
* 서비스 계층에서 트랜잭션 경계 명확화

  * `crud`는 DB I/O, `service`는 비즈니스 로직/권한/트랜잭션 조합
* 어댑터 주입으로 I/O 의존성 역전

  * 예: LLM provider, VectorStore, Storage(S3 등) 모두 인터페이스 기반 주입

---

## 라이선스

사내/프로젝트 정책에 따름.

