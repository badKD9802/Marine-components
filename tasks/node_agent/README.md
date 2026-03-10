# LLM 적응형 동시성 제어 및 배치 병렬화

## 개요

요약(summary)과 번역(translation) 작업에서 LLM 호출을 병렬 배치로 처리하되, GPU 부하에 따라 동시 요청 수를 자동 조절하는 시스템.

3가지 인프라 환경을 자동 감지하여 최적의 배치 크기를 결정한다.

| 환경 | 감지 방식 | 배치 전략 |
|------|-----------|-----------|
| **클러스터 (LB 뒤 다중 GPU)** | `/metrics` 조회 실패 또는 비신뢰 | 응답 지연(latency ratio) 기반 adaptive |
| **단일 GPU (vLLM)** | `/metrics` 정상 응답 | vLLM Prometheus 메트릭 기반 adaptive |
| **OpenAI API** | `base_url`에 `openai.com` 포함 또는 미설정 | 항상 최대 배치 |

---

## 수정 파일

| 파일 | 역할 |
|------|------|
| `node_utils/llm_concurrency.py` | 적응형 동시성 제어 모듈 (신규) |
| `summary.py` | 요약 배치 병렬화 + 총 요약 병렬화 |
| `translation.py` | 번역 배치 병렬화 |

---

## 핵심 모듈: `node_utils/llm_concurrency.py`

### 주요 함수

| 함수 | 설명 |
|------|------|
| `fetch_vllm_metrics(base_url)` | vLLM `/metrics` 엔드포인트에서 running/waiting/gpu_cache 조회. 2초 캐시 + Lock으로 thundering herd 방지 |
| `compute_batch_size(base_url, metrics, configured_max)` | 환경별 최적 배치 크기 계산 |
| `get_llm_semaphore(max_concurrent)` | 글로벌 LLM 동시성 제한 Semaphore 반환 (1회만 생성) |
| `record_latency(elapsed)` | LLM 호출 응답 시간 기록 |
| `get_avg_latency()` | 최근 20건 평균 응답 시간 반환 |

### 배치 크기 결정 로직

**vLLM /metrics 기반 (단일 GPU):**

| 조건 | 배치 크기 |
|------|-----------|
| `gpu_cache_pct > 0.9` 또는 `waiting > 5` | 1 |
| `waiting > 2` | max / 3 |
| `waiting > 0` | max / 2 |
| GPU 여유 | max (최대) |

**Latency ratio 기반 (클러스터 LB):**

`ratio = avg_latency / min(latency_history)`

| ratio | 배치 크기 |
|-------|-----------|
| > 3.0 | 1 |
| > 2.0 | max / 3 |
| > 1.5 | max * 2/3 |
| <= 1.5 | max (최대) |
| 첫 배치 (데이터 없음) | max / 2 (보수적) |

### dynamic_reload 안전성

모듈 상태(latency history, semaphore, metrics cache, httpx client)를 `app.core.config._llm_concurrency_state`에 저장.
`app.tasks.node_agent`는 dynamic_reload 대상이지만, `app.core`는 대상 밖이므로 상태가 보존된다.

### Semaphore 설계

- 워커당 1개 Semaphore, 1회만 생성 (재생성 시 in-flight permit 유실 방지)
- 총 동시 호출 = gunicorn 워커 수 x `llm_max_concurrent`
- 예: 워커 4개, `llm_max_concurrent=8` → 최대 32 동시 LLM 호출

---

## summary.py 변경사항

### Config 읽기

`llm_config`에서 다음 값을 읽음 (관리자 UI에서 설정 가능):

```python
summary_batch_max = int(llm_config.get("summary_batch_size", 6))
summary_page_int = int(llm_config.get("summary_page_int", 4))
llm_max_concurrent = int(llm_config.get("llm_max_concurrent", 8))
```

### Process A: 페이지별 요약

- 고정 `summary_batch_size=2` → adaptive `while` 루프
- 매 배치마다 `fetch_vllm_metrics()` + `compute_batch_size()`로 배치 크기 동적 결정
- `_process_single_summary()`: semaphore 래핑 + `record_latency()` 기록
- `asyncio.gather(*tasks, return_exceptions=True)`로 부분 실패 허용
- 실패 건은 `part_response`/`test_tokens_count`에 추가하지 않아 동기화 유지

### Process B: 총 요약

- 순차 `for` 루프 → `asyncio.gather` 병렬 처리
- `split_by_token_limit` 결과(`list[list[str]]`)를 `"\n\n".join()`으로 문자열 변환 후 LLM에 전달
- 실패 건은 skip, 성공 건만 순서대로 병합
- `part_response`가 비어있으면 총 요약 건너뜀 (NameError 방지)
- `final_main` 항상 초기화 보장

---

## translation.py 변경사항

### _translate_single_page

- `get_llm_semaphore()` + `record_latency()` 추가
- 함수 전체를 `async with semaphore:` 블록으로 래핑
- `record_latency`는 `try/finally`로 예외 시에도 항상 기록

### 배치 루프

- 고정 `for` 루프 → adaptive `while` 루프
- 매 배치마다 `compute_batch_size()`로 동적 크기 결정
- 기존 에러 복구 로직 유지 (`return_exceptions=True`)

---

## Config 키 (관리자 UI → llm config)

| 키 | 기본값 | 설명 |
|----|--------|------|
| `summary_batch_size` | 6 | 요약 최대 배치 크기 |
| `summary_page_int` | 4 | 원본 몇 페이지를 1개 요약 단위로 묶을지 |
| `trans_batch_size` | 3 | 번역 최대 배치 크기 |
| `llm_max_concurrent` | 8 | 워커당 LLM 최대 동시 호출 수 (Semaphore) |

### 환경별 권장 값

| 환경 | `summary_batch_size` | `trans_batch_size` | `llm_max_concurrent` |
|------|---------------------|--------------------|---------------------|
| 클러스터 6대 (LB) | 6 | 5 | 8 |
| 단일 GPU | 3 | 2 | 4 |
| OpenAI API | 10 | 8 | 15 |

---

## 결함 감사 및 수정 이력

배치 병렬화 구현 후 정밀 감사를 수행하여 **8건의 결함**을 발견 및 수정하였다.

### BUG 1: CRITICAL — `part_response`/`test_tokens_count` 길이 불일치

**파일**: `summary.py` (페이지별 요약 결과 수집부)

**원인**: LLM 1회 호출 시 `test_tokens_count`에 1개만 추가하고, `part_response`에는 N개(summaries 수)를 추가.
`split_by_token_limit`은 `zip(data, token_counts)`으로 동작하므로 짧은 쪽에서 잘림 → 데이터 유실.

```
예시: LLM 3회 호출, 각각 2개 summary 반환
  part_response: 6개 (2+2+2)
  test_tokens_count: 3개
  zip → 3개만 처리, 나머지 3개 유실
```

**수정**: `test_tokens_count`도 summary 수만큼 균등 분배.

```python
num_summaries = len(response_msg["summaries"]) or 1
tokens_per_summary = response.usage.completion_tokens // num_summaries
for s in response_msg["summaries"]:
    part_response.append(content_str)
    test_tokens_count.append(tokens_per_summary)
```

### BUG 2: CRITICAL — 총 요약에 리스트가 문자열로 전달

**파일**: `summary.py` (총 요약 입력 데이터)

**원인**: `SummaryItem.content`는 `list` 타입. `part_response.append(s["content"])`로 리스트가 들어가면 `split_by_token_limit` → `groups_response`가 `list[list[list]]`가 되어, `TOTAL_SUMMARY_PROMPT_TEMPLATE.format(document=...)`에 `"[['item1'], ['item2']]"` 형태로 전달.

**수정**: `part_response`에 넣을 때 문자열로 변환.

```python
content_str = "\n".join(f"- {item}" for item in s["content"]) if isinstance(s["content"], list) else str(s["content"])
part_response.append(content_str)
```

### BUG 2+: HIGH — `groups_response`의 리스트를 join하지 않고 format에 전달

**파일**: `summary.py` (총 요약 프롬프트 구성)

**원인**: BUG 2 수정 후에도 `split_by_token_limit`은 `list[list[str]]`을 반환하므로, 각 그룹(`list[str]`)을 그대로 `format(document=group_text)`에 전달하면 `"['문자열1', '문자열2']"` 형태로 렌더링.

**수정**: 총 요약 호출 시 `"\n\n".join(s)`으로 문자열 병합.

```python
total_tasks = [_process_total_summary("\n\n".join(s), i) for i, s in enumerate(groups_response)]
```

### BUG 3: HIGH — `compute_batch_size`가 `configured_max`보다 큰 값 반환

**파일**: `node_utils/llm_concurrency.py`

**원인**: `max(2, configured_max // 2)` — `configured_max=1`이면 `max(2, 0) = 2`. 관리자가 `summary_batch_size=1`로 설정해도 첫 배치에서 2로 동작.

**수정**: `configured_max = max(1, configured_max)` 방어 + `max(2, ...)` → `max(1, ...)`.

### BUG 4: HIGH — `fetch_vllm_metrics` double-check에서 stale `now`

**파일**: `node_utils/llm_concurrency.py`

**원인**: `now`를 Lock 획득 전에 캡처. Lock 대기 후 stale `now`가 `state["cache_time"]`에 저장 → 다음 호출이 캐시를 expired로 판단하여 불필요한 재요청.

**수정**: Lock 내부에서 `now = time.monotonic()` 재캡처.

### BUG 5: HIGH — httpx 클라이언트 dynamic_reload 시 연결 누수

**파일**: `node_utils/llm_concurrency.py`

**원인**: `_http_client`가 모듈 레벨 global이면 `dynamic_reload` 시 모듈 삭제 → 새 모듈 로드 시 `None`으로 재초기화 → 이전 클라이언트 미정리.

**수정**: httpx 클라이언트도 `app.core.config._llm_concurrency_state`에 저장.

### BUG 6: MEDIUM — `result_order` 계산이 불안정

**파일**: `summary.py` (요약 결과 SummarySchema 생성)

**원인**: `result_order=(idx+i+1)` — `idx`는 내부 `for idx, item in enumerate(content)` 루프의 마지막 값. content 길이에 따라 불규칙한 순서.

**수정**: 글로벌 카운터 `global_order`로 교체, 순차 증가.

### BUG 7: MEDIUM — translation.py에서 `record_latency` 호출이 예외 시 건너뜀

**파일**: `translation.py` (`_translate_single_page`)

**원인**: `record_latency()`가 LLM 응답 파싱 후에 위치. `json.loads()` 등에서 예외 발생 시 latency 기록 누락 → 적응형 배치 크기 계산 부정확.

**수정**: `try/finally`로 latency를 항상 기록.

### 오탐(False Positive) 분석

| 보고 내용 | 판정 | 이유 |
|-----------|------|------|
| Semaphore가 워커 간 공유 → RuntimeError | 오탐 | gunicorn fork → 각 워커 독립 프로세스/메모리/event loop |
| `pdf_parser` 미정의 (type != first/repeat) | 오탐 | 비즈니스 로직상 type은 "first" 또는 "repeat"만 존재 |
| `scoped_session` NameError in finally (translation) | 오탐 | try 블록 바깥에서 초기화 (line 381) |
| `percentage` 미정의 (빈 results) | 오탐 | `compute_batch_size`가 최소 1을 반환하므로 results 항상 1개 이상 |

---

## 검증 체크리스트

1. 다페이지 PDF 요약 → 로그에서 `[요약] adaptive batch_size=N/M` 확인
2. 총 요약 결과가 정상 문자열인지 확인 (리스트 표현 `['...']` 없음)
3. `part_response` 개수와 `test_tokens_count` 개수 동일 확인
4. OpenAI API 사용 시 → metrics skip, 항상 최대 배치
5. 동시 요약 2건 실행 → latency ratio 증가 시 batch 자동 축소 로그 확인
6. 페이지 요약 실패 → skip, 나머지 정상 처리 + `split_by_token_limit` 오류 없음
7. 전체 실패 → "요약 생성에 실패했습니다" 메시지, 에러 없음
8. `summary_batch_size=1` → 기존 순차 동작과 동일 (회귀 테스트)
9. 총 요약 → groups 병렬 처리 확인
10. `dynamic_reload on` → 상태 보존 확인 (latency history 유지, httpx 누수 없음)
11. 번역 → `[번역] adaptive batch_size=N/M` 로그 확인
12. 번역 중 JSON 파싱 실패 시 → latency 기록 누락 없음
