# 토픽별 병렬 검색 — 복잡 RAG 질문 정확도 개선 (v2.2)

> 작성일: 2026-03-09 | 카테고리: feat

## 배경
멀티 토픽 질문("연차 규정이랑 병가 규정 비교해줘")에서 reranker의 top-k 경쟁으로 한쪽 토픽 청크만 살아남아 답변 품질이 저하되는 문제. Retrieval allocation 문제를 해결하기 위해 토픽별 독립 검색+리랭크 → quota 보장 merge 파이프라인을 구현.

## 변경 사항
| 파일 | 변경 내용 |
|------|----------|
| `app/tasks/lib_justtype/rag/just_llm.py` | `MultiQueryResult` dataclass 추가, `MultiQueryResponse` 스키마에 `TopicGroup`/`is_multi_topic`/`topic_groups`/`shared_query_indices` 확장, 모든 return 경로를 5-tuple에서 `MultiQueryResult` 객체로 변경 |
| `app/tasks/node_agent/prompts/just_llm_prompts.py` | `GENERATE_MULTI_QUERIES_SYSTEM_PROMPT`에 5단계 토픽 분해 규칙 추가 |
| `app/tasks/node_agent/nodes/rag_pipeline/node_query_prep.py` | `MultiQueryResult` 객체 수신, `_validate_query_level`/`_validate_topic_level` 2단계 검증, `query_indices` → `embedding_indices` 변환(+1), pipeline에 `is_multi_topic`/`topic_groups`/`shared_query_indices` 저장 |
| `app/tasks/node_agent/nodes/rag_pipeline/node_collection_pipeline.py` | `_chunk_key()`/`_merge_source_topics()` 헬퍼, `_multi_topic_collection_pipeline()` — 토픽별 병렬 검색+후처리+리랭크+LLM검증+Latest Search+source_topics 부여 |
| `app/tasks/node_agent/nodes/rag_pipeline/node_merge_results.py` | `_quota_spillover_merge()` — 토픽별 quota 보장 + dedup + spillover, 멀티토픽 분기 |
| `app/tasks/node_agent/node_utils/ChunkInfoBuilder.py` | `metainfo`에 `chunk_id`, `source_topics`, `final_score` 필드 추가 |
| `app/tasks/node_agent/nodes/node_generate_stream.py` | `_topic_aware_chunk_select()` round-robin 선택, `_apply_token_budget`에 `is_multi_topic` 파라미터 |

## 핵심 코드

### MultiQueryResult (just_llm.py)
```python
@dataclass
class MultiQueryResult:
    refined_question: str
    generated_queries: list = field(default_factory=list)
    is_multi_topic: bool = False
    topic_groups: list = field(default_factory=list)    # [{topic, query_indices, validation_query}]
    shared_query_indices: list = field(default_factory=list)
    # ... 기타 필드
```

### 2단계 검증 (node_query_prep.py)
```python
# Query-level: 실패 → 완전 fallback (original question)
def _validate_query_level(mq) -> bool: ...

# Topic-level: 실패 → multi-topic만 disable (일반 multi-query 유지)
def _validate_topic_level(mq) -> bool: ...
```

### Quota + Spillover Merge (node_merge_results.py)
```python
def _quota_spillover_merge(topic_final, final_total):
    # 1단계: 토픽별 quota (base = final_total // n_topics)
    # 2단계: underfill → spillover (점수 내림차순)
    # 전체: dedup-aware + source_topics 병합
```

### Topic-Aware Token Budget (node_generate_stream.py)
```python
def _topic_aware_chunk_select(chunks, chunk_token_list, max_chunk_budget):
    # multi-topic chunk는 모든 관련 queue에 등록
    # round-robin으로 토픽 균형 선택
```

## 설계 결정
- `validation_query`: topic label보다 정밀한 검색/리랭크용 질문 (LLM이 생성)
- `shared_query_indices`: "비교/차이점" 쿼리는 독립 토픽이 아닌 보조 쿼리
- `source_topics: list[str]`: 같은 chunk가 여러 토픽에 속할 수 있음 → dedup 시 병합
- `_chunk_key()`: chunk 식별 통일 (chunk_id 우선, 없으면 composite key)
- 싱글 토픽 경로는 100% 기존 동일 (`is_multi_topic=False` 기본값)

## 후속 작업
- [ ] 통합 테스트 (멀티토픽 + 싱글토픽 회귀)
- [ ] shared query 가중치 차등 적용
- [ ] Latest Search 토픽 매핑 `doc_id` 기반 강화
- [ ] multi-topic telemetry 추가
