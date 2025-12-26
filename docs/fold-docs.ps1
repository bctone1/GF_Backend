param(
  [switch]$Overwrite
)

function Find-DocsJsonPath([string]$StartDir) {
  $p = Resolve-Path $StartDir
  while ($true) {
    $cand1 = Join-Path $p "docs.json"
    $cand2 = Join-Path $p "docs\docs.json"

    if (Test-Path $cand1) { return (Resolve-Path $cand1).Path }
    if (Test-Path $cand2) { return (Resolve-Path $cand2).Path }

    $parent = Split-Path $p -Parent
    if ($parent -eq $p -or [string]::IsNullOrWhiteSpace($parent)) { break }
    $p = $parent
  }
  throw "docs.json not found. Run this script in docs folder or repo root."
}

function Make-Title([string]$page) {
  $last = ($page -split "/")[-1]
  $last = $last -replace "-", " "
  if ([string]::IsNullOrWhiteSpace($last)) { return $page }
  return ($last.Substring(0,1).ToUpper() + $last.Substring(1))
}

function Get-PageMeta([string]$page) {
  $meta = @{
    title = (Make-Title $page)
    desc  = "작성 예정"
  }

  switch ($page) {
    # ---------- Getting started ----------
    "index"                      { $meta.title="GrowFit Docs"; $meta.desc="실습 중심 LLM 교육 플랫폼 GrowFit 문서" }
    "getting-started/local-dev"  { $meta.title="로컬에서 문서 실행"; $meta.desc="mint dev로 문서 로컬 실행" }
    "getting-started/env"        { $meta.title="환경변수/설정"; $meta.desc="백엔드/문서 공통 설정" }
    "getting-started/quickstart" { $meta.title="Quickstart"; $meta.desc="Practice/RAG/Agents를 빠르게 맛보기" }
    "faq"                        { $meta.title="FAQ"; $meta.desc="자주 묻는 질문" }
    "troubleshooting"            { $meta.title="Troubleshooting"; $meta.desc="문제 해결 가이드" }
    "glossary"                   { $meta.title="용어집"; $meta.desc="핵심 용어 정리" }

    # ---------- Practice ----------
    "practice/overview"          { $meta.title="Practice 개요"; $meta.desc="실습(Practice) 전체 흐름" }
    "practice/models"            { $meta.title="모델 선택"; $meta.desc="모델 선택/비교 기준" }
    "practice/parameters"        { $meta.title="LLM 파라미터"; $meta.desc="temperature/top_p/max_tokens 등 조절" }
    "practice/style-presets"     { $meta.title="스타일 프리셋"; $meta.desc="accurate/balanced/creative/custom 등" }
    "practice/few-shot"          { $meta.title="Few-shot 예시"; $meta.desc="few-shot 예시 추가/관리/효과" }
    "practice/agents"            { $meta.title="Practice에서 Agents 사용"; $meta.desc="실습에서 에이전트 적용" }
    "practice/evaluation"        { $meta.title="평가/기록"; $meta.desc="평가/비교/기록 방식" }
    "practice/cost-latency"      { $meta.title="비용/지연시간"; $meta.desc="token/latency/TTFT/cost 해석" }

    # ---------- RAG ----------
    "rag/overview"               { $meta.title="RAG 개요"; $meta.desc="Knowledge Base(RAG) 전체 흐름" }
    "rag/ingestion"              { $meta.title="문서 인제스천"; $meta.desc="업로드→청킹→임베딩→저장" }
    "rag/chunking"               { $meta.title="청킹(Chunking)"; $meta.desc="chunk_size/overlap 전략과 트레이드오프" }
    "rag/embeddings"             { $meta.title="임베딩(Embeddings)"; $meta.desc="임베딩 모델/차원/비용" }
    "rag/search"                 { $meta.title="검색(Search)"; $meta.desc="검색 동작과 결과 해석" }
    "rag/threshold-topk"         { $meta.title="Threshold & Top-k"; $meta.desc="top-k/threshold 조합 레시피" }
    "rag/rerank"                 { $meta.title="재랭킹(Rerank)"; $meta.desc="rerank on/off 영향" }
    "rag/sources-citations"      { $meta.title="출처/인용"; $meta.desc="출처 표시로 신뢰도 높이기" }

    # ---------- Agents ----------
    "agents/overview"            { $meta.title="Agents 개요"; $meta.desc="에이전트 개념과 전체 흐름" }
    "agents/system-prompt"       { $meta.title="System Prompt"; $meta.desc="시스템 프롬프트 작성 가이드" }
    "agents/templates"           { $meta.title="Agent 템플릿"; $meta.desc="자주 쓰는 템플릿 모음" }
    "agents/sharing"             { $meta.title="공유(Sharing)"; $meta.desc="Partner→Class 공유 흐름" }
    "agents/forking"             { $meta.title="포크(Forking)"; $meta.desc="공유 에이전트 포크 흐름" }
    "agents/versioning"          { $meta.title="버전 관리(Versioning)"; $meta.desc="재현성을 위한 정책" }
  }

  return $meta
}

# ----------------------------
# Practice template (KOR)
# ----------------------------
function Build-PracticeBody([string]$page) {
  $common = @(
    "## 이 문서에서 하는 것",
    "- 같은 질문을 여러 설정으로 실행해서 결과/비용/속도를 비교해.",
    "",
    "## 준비물",
    "- Practice 세션(새로 만들거나 기존 세션)",
    "- 모델 1개 선택",
    "",
    "## 조절 변수(핵심)",
    "- 모델: provider/model_name",
    "- 파라미터: temperature, top_p, max_tokens (및 response length preset을 쓰면 같이)",
    "- (선택) Agents: system prompt + few-shot 예시",
    "- (선택) RAG: top-k/threshold/rerank",
    "",
    "## 기록할 지표",
    "- 지연시간(latency) / TTFT",
    "- 토큰(prompt/completion/total)",
    "- 비용(추정치)",
    "- 품질(정확도/가독성/근거성)",
    "",
    "## 자주 터지는 실수",
    "- 변수를 한 번에 여러 개 바꿈(원인 분석 불가)",
    "- few-shot이 너무 김(비용/지연 급증)",
    "- temperature 과다(사실 QA에서 환각 위험)",
    ""
  )

  $pageSpecific = @()

  switch ($page) {
    "practice/overview" {
      $pageSpecific = @(
        "## 추천 실습 흐름",
        "1) 질문 세트(5~10개)부터 고정해.",
        "2) 기본 프리셋으로 1회 실행(베이스라인).",
        "3) 변수 1개만 바꾸고 재실행(예: temperature).",
        "4) 결과 + 지표 + 평가를 기록해.",
        "5) 다음 변수로 반복해.",
        "",
        "## 다음 문서",
        "- /practice/parameters",
        "- /practice/models",
        "- /practice/evaluation"
      )
    }
    "practice/models" {
      $pageSpecific = @(
        "## 모델 선택 기준",
        "- 빠른 반복용: 속도/비용 좋은 모델",
        "- 최종 답변용: 품질 좋은 모델",
        "",
        "## 비교 체크리스트",
        "- 프롬프트/질문/RAG 설정을 동일하게 유지해.",
        "- randomness(temperature>0)면 2~3회 반복해서 편차도 봐.",
        "",
        "## 다음 문서",
        "- /practice/parameters",
        "- /practice/cost-latency"
      )
    }
    "practice/parameters" {
      $pageSpecific = @(
        "## 파라미터 요약",
        "| 파라미터 | 의미 | 권장 범위(일반) | 메모 |",
        "|---|---|---:|---|",
        "| temperature | 다양성/랜덤성 | 0.0 ~ 1.0 | 높을수록 편차↑ |",
        "| top_p | 누적확률 샘플링 | 0.7 ~ 1.0 | 낮을수록 안정적 |",
        "| max_tokens | 출력 상한 | 상황별 | 너무 낮으면 끊김 |",
        "",
        "## 추천 실험",
        "1) temperature 0.2 vs 0.8 (나머지 고정)",
        "2) top_p 0.9 vs 1.0",
        "3) max_tokens 256 vs 1024 (끊김/비용 비교)",
        "",
        "## 다음 문서",
        "- /tutorials/01-params"
      )
    }
    "practice/style-presets" {
      $pageSpecific = @(
        "## 프리셋이 담당하면 좋은 것",
        "- 출력 형식(불릿/에세이/단계별 등)",
        "- 힌트 모드 vs 정답 모드",
        "- self-check on/off",
        "- persona 강도(선택)",
        "",
        "## 테스트 방법",
        "- 동일 질문 5개를 프리셋별로 실행해.",
        "- 구조 일관성 + 비용/지연을 같이 봐.",
        "",
        "## 다음 문서",
        "- /practice/evaluation"
      )
    }
    "practice/few-shot" {
      $pageSpecific = @(
        "## few-shot 베스트 프랙티스",
        "- 처음엔 1~3개만(짧고 형식 중심).",
        "- 내용이 길어질수록 비용/지연이 커져.",
        "",
        "## 추천 실험",
        "1) 0-shot vs 2-shot vs 5-shot",
        "2) 형식 예시 vs 내용 예시(비용/효과 차이)",
        "",
        "## 다음 문서",
        "- /tutorials/04-agent",
        "- /agents/system-prompt"
      )
    }
    "practice/agents" {
      $pageSpecific = @(
        "## 적용 흐름",
        "1) agent 선택(또는 생성)",
        "2) 세션에 적용",
        "3) 동일 질문으로 agent OFF/ON 비교",
        "",
        "## 관찰 포인트",
        "- 형식/톤/규칙 준수",
        "- 토큰/비용 증가폭(system prompt + 예시)",
        "",
        "## 다음 문서",
        "- /agents/overview",
        "- /agents/sharing",
        "- /agents/forking"
      )
    }
    "practice/evaluation" {
      $pageSpecific = @(
        "## 평가 루브릭(예시)",
        "- 정확도(0~5)",
        "- 근거성/출처 적합성(0~5)",
        "- 구조/가독성(0~5)",
        "- 안전/정책 준수(0~5)",
        "",
        "## 공정 비교 팁",
        "- 변수 1개만 바꾸기",
        "- 질문 세트 고정",
        "- 지표는 자동 기록되게(가능하면)",
        "",
        "## 다음 문서",
        "- /tutorials/05-ab-compare"
      )
    }
    "practice/cost-latency" {
      $pageSpecific = @(
        "## 지연시간이 늘어나는 이유",
        "- 모델 자체 속도/부하",
        "- 프롬프트 길이(히스토리+system+few-shot+RAG 컨텍스트)",
        "- RAG 단계(retrieval/rerank)",
        "",
        "## 비용이 늘어나는 이유",
        "- prompt tokens 증가(특히 RAG/예시/히스토리)",
        "- completion tokens 증가(긴 답변)",
        "",
        "## 최적화 체크리스트",
        "- 히스토리/컨텍스트 슬림화",
        "- top-k 줄이거나 threshold 올리기",
        "- rerank는 필요할 때만",
        "- 실습 반복 구간은 짧은 응답 프리셋 사용",
        "",
        "## 다음 문서",
        "- /rag/overview",
        "- /tutorials/03-rerank"
      )
    }
  }

  return ($common + $pageSpecific) -join "`n"
}

# ----------------------------
# RAG template (KOR)
# ----------------------------
function Build-RagBody([string]$page) {
  $common = @(
    "## 이 문서에서 하는 것",
    "- 검색(Retrieval) 설정을 바꾸면서 품질/지연/비용이 어떻게 달라지는지 확인해.",
    "",
    "## RAG 파이프라인(큰 흐름)",
    "1) 인제스천: 업로드 → 파싱 → 청킹",
    "2) 임베딩: 청크 → 벡터",
    "3) 검색: 질의 → 벡터검색 → 후보(top-k)",
    "4) (선택) 재랭킹: 후보 재정렬",
    "5) 생성: 답변 + 출처",
    "",
    "## 핵심 변수",
    "- chunk_size / chunk_overlap / max_chunks",
    "- embedding 모델(및 dimension)",
    "- top_k / threshold(유사도 임계값)",
    "- rerank on/off",
    "",
    "## 기록할 지표",
    "- retrieved_count / score 분포",
    "- 답변 근거성(정말 관련 청크를 가져왔나?)",
    "- 지연/토큰/비용(컨텍스트가 길어지면 prompt가 커짐)",
    "",
    "## 자주 터지는 실수",
    "- top-k 과다(노이즈/비용/지연 증가)",
    "- threshold 과다(필요한 청크를 못 가져옴)",
    "- overlap 과다(중복 컨텍스트로 토큰 낭비)",
    ""
  )

  $pageSpecific = @()

  switch ($page) {
    "rag/overview" {
      $pageSpecific = @(
        "## 추천 시작값(일반론)",
        "- chunk_size: 400~800",
        "- chunk_overlap: 50~150",
        "- top_k: 3~8",
        "- threshold: 낮게 시작 → 노이즈 줄 때까지 서서히 올리기",
        "- rerank: OFF로 시작 → 필요하면 ON",
        "",
        "## 추천 실험",
        "1) RAG OFF vs ON",
        "2) top_k 3 vs 10",
        "3) threshold 낮게 vs 높게",
        "4) rerank OFF vs ON",
        "",
        "## 다음 문서",
        "- /rag/ingestion",
        "- /rag/chunking",
        "- /rag/search"
      )
    }
    "rag/ingestion" {
      $pageSpecific = @(
        "## 인제스천 단계",
        "1) 파일 업로드(PDF 등)",
        "2) 텍스트 파싱",
        "3) 청킹",
        "4) 임베딩 생성",
        "5) pages/chunks/vectors 저장",
        "",
        "## 저장 권장 필드(예시)",
        "- document 메타(name, size, mime, created_at)",
        "- pages(page_no, text)",
        "- chunks(chunk_id, page_range, text, tokens)",
        "- vectors(embedding, model, dimension)",
        "",
        "## 트러블슈팅",
        "- 파싱 실패: 포맷/파서 제한/암호화 PDF 등",
        "- 느림: 인제스천을 백그라운드 잡/큐로 분리",
        "",
        "## 다음 문서",
        "- /rag/chunking",
        "- /rag/embeddings"
      )
    }
    "rag/chunking" {
      $pageSpecific = @(
        "## 청킹 전략",
        "- recursive(문단/구조 기반) 권장",
        "- fixed-size는 구현은 쉽지만 의미 단위가 깨질 수 있음",
        "",
        "## 트레이드오프",
        "- 작은 청크: 정밀도↑ / 문맥연결↓",
        "- 큰 청크: 문맥연결↑ / 정밀도↓ + 토큰비용↑",
        "- overlap: 문맥연결↑ / 중복비용↑",
        "",
        "## 추천 실험",
        "1) chunk_size 300 vs 800",
        "2) overlap 0 vs 100",
        "3) max_chunks 상한으로 폭주 방지",
        "",
        "## 다음 문서",
        "- /rag/search",
        "- /rag/threshold-topk"
      )
    }
    "rag/embeddings" {
      $pageSpecific = @(
        "## 무엇이 중요한가",
        "- 도메인 적합도/품질",
        "- dimension(저장용량/성능)",
        "- 배치 처리/캐시",
        "",
        "## 운영 체크리스트",
        "- vector마다 embedding_model + dimension 저장",
        "- 서로 다른 임베딩 모델을 같은 인덱스에 섞지 않기",
        "",
        "## 다음 문서",
        "- /rag/search"
      )
    }
    "rag/search" {
      $pageSpecific = @(
        "## 검색 동작",
        "- 벡터검색은 후보와 score를 반환해.",
        "- 그 다음 top_k/threshold를 적용해서 컨텍스트를 만든다.",
        "",
        "## 로깅 추천",
        "- top_k, threshold",
        "- retrieved_count",
        "- score 분포(p50/p90 등)",
        "",
        "## 추천 실험",
        "1) top_k 3 vs 8 vs 15",
        "2) threshold를 올려가며 노이즈 제거",
        "",
        "## 다음 문서",
        "- /rag/threshold-topk",
        "- /rag/rerank"
      )
    }
    "rag/threshold-topk" {
      $pageSpecific = @(
        "## 조합 레시피",
        "- 정밀도 우선: top_k 작게(3~5) + threshold 높게",
        "- 재현율 우선: top_k 크게(8~15) + threshold 낮게",
        "",
        "## 튜닝 순서(권장)",
        "1) top_k=5, threshold 낮게 시작",
        "2) threshold를 올려서 노이즈를 줄여",
        "3) 놓치는 답이 많으면 top_k를 조금 늘려",
        "",
        "## 다음 문서",
        "- /rag/rerank"
      )
    }
    "rag/rerank" {
      $pageSpecific = @(
        "## rerank가 도움 되는 상황",
        "- 1차 검색 후보가 많고 비슷비슷해서 상위가 흔들릴 때",
        "- top_k를 크게 가져오고, 그 중에서 진짜 상위만 뽑고 싶을 때",
        "",
        "## 비용/지연 영향",
        "- 추가 스코어링 단계라 latency 증가",
        "- 대신 컨텍스트 품질이 좋아져 환각이 줄 수 있음",
        "",
        "## 추천 실험",
        "1) top_k=10에서 rerank OFF vs ON",
        "2) 근거성/지연/비용 나란히 비교",
        "",
        "## 다음 문서",
        "- /rag/sources-citations"
      )
    }
    "rag/sources-citations" {
      $pageSpecific = @(
        "## 출처에 표시하면 좋은 것",
        "- 문서명",
        "- 페이지/청크 ID",
        "- 스니펫 미리보기",
        "- (선택) 유사도 score",
        "",
        "## 신뢰 체크리스트",
        "- 답변 문장 ↔ 출처 청크가 자연스럽게 연결되나?",
        "- 설정이 같으면 출처도 크게 흔들리지 않나?",
        "",
        "## 다음 문서",
        "- /practice/cost-latency"
      )
    }
  }

  return ($common + $pageSpecific) -join "`n"
}

# ----------------------------
# Agents template (KOR)
# ----------------------------
function Build-AgentsBody([string]$page) {
  $common = @(
    "## 이 문서에서 하는 것",
    "- 에이전트를 만들어 출력 형식/행동을 안정적으로 제어하고, 공유/포크로 교육 운영에 활용해.",
    "",
    "## agent 구성(권장)",
    "- system prompt: 역할/규칙/출력 형식",
    "- few-shot 예시(선택): 1~3개(짧고 형식 중심)",
    "- 기본 옵션(선택): 스타일 프리셋/파라미터 기본값",
    "",
    "## 비용/지연에 영향 주는 지점",
    "- system prompt 길이",
    "- few-shot 예시 길이",
    "- 세션에서 RAG/도구를 함께 켜면 prompt가 더 커짐",
    "",
    "## 자주 터지는 실수",
    "- 규칙이 너무 많아 충돌(모델이 제멋대로 우선순위 해석)",
    "- 금지/허용 기준이 모호함",
    "- 내용 위주의 few-shot(비싸고 과적합)",
    ""
  )

  $pageSpecific = @()

  switch ($page) {
    "agents/overview" {
      $pageSpecific = @(
        "## 라이프사이클(추천)",
        "1) agent 생성(system prompt 작성)",
        "2) Practice에서 질문 세트로 테스트",
        "3) 필요하면 few-shot 1~3개 추가",
        "4) 클래스에 공유(Partner)",
        "5) 학생은 포크해서 개인화",
        "",
        "## system prompt 권장 구조",
        "- 역할(Role)",
        "- 목표(Goal)",
        "- 제약(Do/Don't)",
        "- 출력 형식(Output format: 매우 구체적으로)",
        "",
        "## 다음 문서",
        "- /agents/system-prompt",
        "- /agents/sharing",
        "- /agents/forking"
      )
    }
    "agents/system-prompt" {
      $pageSpecific = @(
        "## 시스템 프롬프트 템플릿",
        "```text",
        "역할: 너는 ...",
        "목표: ...",
        "제약:",
        "- 해야 할 것: ...",
        "- 하면 안 되는 것: ...",
        "출력 형식:",
        "- 제목",
        "- 핵심 요약(불릿 3개)",
        "- 근거/단계(필요 시)",
        "```",
        "",
        "## 작성 팁",
        "- 출력 형식을 최대한 구체적으로(섹션/순서/길이)",
        "- 규칙은 최소로, 충돌 없게",
        "",
        "## 빠른 테스트",
        "1) system prompt OFF/ON 비교",
        "2) 엣지 케이스 입력으로 스트레스 테스트",
        "",
        "## 다음 문서",
        "- /agents/templates",
        "- /practice/agents"
      )
    }
    "agents/templates" {
      $pageSpecific = @(
        "## 추천 템플릿",
        "- 튜터(힌트 모드)",
        "- 코드 리뷰어",
        "- 구조화 요약기",
        "- RAG 기반 근거 QA",
        "",
        "## 운영 팁",
        "- 템플릿은 짧고 명확하게",
        "- 변경 시 changelog(왜 바꿨는지) 남기기",
        "",
        "## 다음 문서",
        "- /agents/sharing",
        "- /agents/versioning"
      )
    }
    "agents/sharing" {
      $pageSpecific = @(
        "## 공유 모델(권장)",
        "- Partner가 특정 Class에 agent를 공유",
        "- Student는 실행 가능 + (정책에 따라) 포크 가능",
        "",
        "## 운영 제어 포인트",
        "- 누가 공유할 수 있나(Partner only)",
        "- 공유 대상 class",
        "- 활성/비활성 토글",
        "- (선택) 만료일",
        "",
        "## 재현성 경고",
        "- 공유 agent가 바뀌면 예전 실험 재현이 어려워져.",
        "- 버전/스냅샷 정책을 같이 가져가야 해.",
        "",
        "## 다음 문서",
        "- /agents/forking",
        "- /agents/versioning"
      )
    }
    "agents/forking" {
      $pageSpecific = @(
        "## 포크 의미(권장)",
        "- 공유 agent를 학생 개인 공간으로 복사",
        "- (선택) parent_agent_id로 계보를 남김",
        "",
        "## 정책 결정(중요)",
        "- 부모 업데이트를 포크에 자동 반영할까?",
        "- 권장: 자동 반영 NO(재현성 유지), 대신 수동 업데이트 제공",
        "",
        "## 다음 문서",
        "- /agents/versioning",
        "- /practice/evaluation"
      )
    }
    "agents/versioning" {
      $pageSpecific = @(
        "## 왜 필요해?",
        "- agent가 바뀌면 A/B 비교/실험 재현이 깨져.",
        "",
        "## 최소 버전 정책(권장)",
        "- updated_at + updated_by",
        "- change_summary(무엇을 왜 바꿨는지 한 문단)",
        "- (선택) 공유 시 스냅샷 고정(클래스 운영에 특히 좋음)",
        "",
        "## 추천 워크플로",
        "1) 수정 → 새 버전/스냅샷 생성",
        "2) 질문 세트로 검증",
        "3) 공유 버전 승격",
        "",
        "## 다음 문서",
        "- /practice/evaluation",
        "- /ops/monitoring-logs"
      )
    }
  }

  return ($common + $pageSpecific) -join "`n"
}

# ----------------------------
# Other templates (KOR)
# ----------------------------
function Build-ApiBody([string]$page) {
  return @(
    "## 엔드포인트",
    "- (작성 예정)",
    "",
    "## Request 예시",
    "```json",
    "{}",
    "```",
    "",
    "## Response 예시",
    "```json",
    "{}",
    "```",
    "",
    "## 에러 케이스",
    "- (작성 예정)",
    ""
  ) -join "`n"
}

function Build-TutorialBody([string]$page) {
  return @(
    "## 목표",
    "- (작성 예정)",
    "",
    "## 준비물",
    "- (작성 예정)",
    "",
    "## 단계",
    "1) (작성 예정)",
    "",
    "## 체크포인트",
    "- (작성 예정)",
    ""
  ) -join "`n"
}

function Build-DefaultBody([string]$page) {
  return @(
    "## 개요",
    "- (작성 예정)",
    "",
    "## 포함할 내용",
    "- (작성 예정)",
    "",
    "## 참고",
    "- (작성 예정)",
    ""
  ) -join "`n"
}

function Build-Content([string]$page) {
  $meta = Get-PageMeta $page

  $front = @(
    "---",
    "title: `"$($meta.title)`"",
    "description: `"$($meta.desc)`"",
    "---",
    ""
  ) -join "`n"

  if ($page -like "practice/*") { return $front + (Build-PracticeBody $page) + "`n" }
  if ($page -like "rag/*")      { return $front + (Build-RagBody $page) + "`n" }
  if ($page -like "agents/*")   { return $front + (Build-AgentsBody $page) + "`n" }
  if ($page -like "api/*")      { return $front + (Build-ApiBody $page) + "`n" }
  if ($page -like "tutorials/*"){ return $front + (Build-TutorialBody $page) + "`n" }

  return $front + (Build-DefaultBody $page) + "`n"
}

# ----------------------------
# Main
# ----------------------------
$docsJsonPath = Find-DocsJsonPath -StartDir $PSScriptRoot
$docsRoot = Split-Path $docsJsonPath -Parent

Write-Host "docs.json :" $docsJsonPath
Write-Host "docs root :" $docsRoot

$cfg = Get-Content -Raw -Path $docsJsonPath -Encoding UTF8 | ConvertFrom-Json

$allPages = @()
foreach ($tab in $cfg.navigation.tabs) {
  foreach ($grp in $tab.groups) {
    $allPages += $grp.pages
  }
}
$allPages = $allPages | Where-Object { $_ -and $_.Trim().Length -gt 0 } | Select-Object -Unique

foreach ($page in $allPages) {
  $rel = $page
  if ($rel -notmatch '\.(md|mdx)$') { $rel = "$rel.mdx" }

  $outPath = Join-Path $docsRoot $rel
  $dir = Split-Path $outPath -Parent
  if (!(Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
  }

  if ((Test-Path $outPath) -and (-not $Overwrite)) {
    Write-Host "SKIP  :" $rel
    continue
  }

  $content = Build-Content $page
  Set-Content -Path $outPath -Value $content -Encoding utf8
  Write-Host "WRITE :" $rel
}

Write-Host "DONE"
