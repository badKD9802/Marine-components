"""
RAG 검색 시스템 - Milvus 클라이언트 (리팩토링 버전)
주요 개선사항:
- 정규식 컴파일 캐싱으로 성능 개선
- 키워드 분석 로직 최적화
- 스코어 계산 로직 모듈화
- 설정값 상수화
- 코드 중복 제거
"""

import calendar
import json
import logging
import math
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

import numpy as np
import requests
from kiwipiepy import Kiwi
from kiwipiepy.utils import Stopwords
from openai import OpenAI
from pymilvus import AsyncMilvusClient, MilvusClient
from scipy.spatial.distance import cosine

from app.tasks.lib_justtype.common.just_env import JustEnv
from app.tasks.lib_justtype.common.global_clients import get_openai_client

# ==========================================================
# 전역 초기화
# ==========================================================

logger = logging.getLogger(__name__)

kiwi = Kiwi(model_type="sbg")
stopwords = Stopwords()

# ==========================================================
# 상수 정의
# ==========================================================

class DefaultScoringWeights:
    """스코어링 가중치"""
    # RRF 가중치 (Dense, Sparse)
    DEFAULT_RRF = [0.3, 0.7]
    
    # 최종 스코어 가중치
    HYBRID_KEYWORD = 0.2
    SEMANTIC = 0.8
    EXACT_MATCH = 0.0 # 0.05
    GROUP_RECENCY = 0.0 #0.05
    
    # 키워드 부스트
    KEYWORD_BOOST_FACTOR = 1.1 # 0.3
    MAX_KEYWORD_BOOST = 1.1 # 5.0
    
    # Exact Match
    EXACT_MATCH_BOOST = 1.1 # 3.0


class LegalTermPatterns:
    """법령/규정 패턴 및 가중치 (단순화 버전)"""
    
    # 실제로 효과가 있는 핵심 패턴만 유지
    ARTICLE = (re.compile(r'제\d+조'), 4.0)
    PARAGRAPH = (re.compile(r'제\d+항'), 3.0)
    ITEM = (re.compile(r'제\d+호'), 2.0)
    APPENDIX = (re.compile(r'별표\d+|별지\d+'), 2.0)
    
    @classmethod
    def get_all_patterns(cls) -> Dict[str, Tuple[re.Pattern, float]]:
        """모든 패턴 반환"""
        return {
            'ARTICLE': cls.ARTICLE,
            'PARAGRAPH': cls.PARAGRAPH,
            'ITEM': cls.ITEM,
            'APPENDIX': cls.APPENDIX,
        }


# ==========================================================
# 텍스트 정규화 유틸리티
# ==========================================================

class TextNormalizer:
    """텍스트 정규화 클래스 (단순화 버전)"""
    
    # 공백 제거만 수행 (과도한 정규화는 오히려 검색 성능 저하)
    _whitespace_pattern = re.compile(r'\s+')
    
    @classmethod
    def normalize_legal_terms(cls, text: str) -> str:
        """
        법령/규정 용어 정규화 (최소화)
        
        실제로는 Kiwi 형태소 분석기가 이미 잘 처리하므로,
        공백 제거만 수행합니다.
        
        Args:
            text: 원본 텍스트
        
        Returns:
            정규화된 텍스트
        """
        if not text or not isinstance(text, str):
            return ""
        
        # 공백만 제거
        return cls._whitespace_pattern.sub('', text)


# ==========================================================
# 키워드 분석기
# ==========================================================

class KeywordAnalyzer:
    """키워드 분석 클래스"""
    
    def __init__(self, query: str, base_keyword_weights: Dict[str, float]):
        """
        Args:
            query: 분석할 쿼리
            base_keyword_weights: 기본 키워드 가중치
        """
        self.query = query
        self.keyword_weights = dict(base_keyword_weights)
        self.high_priority_keywords = set()
        
        self._analyze()
    
    def _analyze(self):
        """키워드 분석 실행"""
        # 1. 법령/규정 키워드 추출 (우선순위 높음)
        self._extract_legal_keywords()
        
        # 2. 일반 키워드 추출
        self._extract_general_keywords()
        
        # logger.info(f"Analyzed keywords: {self.keyword_weights}")
    
    def _extract_legal_keywords(self):
        """법령/규정 키워드 추출"""
        normalized_query = TextNormalizer.normalize_legal_terms(self.query)
        
        for term_type, (pattern, weight) in LegalTermPatterns.get_all_patterns().items():
            matches = pattern.finditer(normalized_query)
            for match in matches:
                keyword = match.group(0)
                if keyword not in self.keyword_weights:
                    self.keyword_weights[keyword] = weight
                    self.high_priority_keywords.add(keyword)
                    logger.debug(f"Legal keyword: '{keyword}' (weight: {weight})")
    
    def _extract_general_keywords(self):
        """일반 키워드 추출"""
        tokens = kiwi.tokenize(self.query)
        important_tokens = []
        
        for token in tokens:
            # 명사, 동사, 형용사 등 중요 품사만 추출
            if token.tag.startswith(('NN', 'VV', 'VA', 'XR')) and len(token.form) > 1:
                # 이미 법령 키워드로 처리된 토큰은 제외
                if not any(token.form in kw for kw in self.high_priority_keywords):
                    important_tokens.append(token.form)
        
        # 빈도 계산 및 가중치 할당
        counts = Counter(important_tokens)
        for keyword, count in counts.items():
            if keyword not in self.keyword_weights:
                base_weight = 1.5 if len(keyword) >= 4 else 1.0
                self.keyword_weights[keyword] = base_weight + (0.1 * count)
    
    def calculate_boost(self, text: str) -> float:
        """
        텍스트에 대한 키워드 부스트 점수 계산
        
        Args:
            text: 평가할 텍스트
        
        Returns:
            부스트 점수 (0.0 ~ MAX_KEYWORD_BOOST)
        """
        if not text or not isinstance(text, str):
            return 0.0
        
        total_boost = 0.0
        normalized_text = TextNormalizer.normalize_legal_terms(text)
        
        for keyword, weight in self.keyword_weights.items():
            # 우선순위 키워드는 정규화된 텍스트에서, 일반 키워드는 원본에서 검색
            target_text = normalized_text if keyword in self.high_priority_keywords else text
            if keyword in target_text:
                total_boost += weight
        
        return min(total_boost, DefaultScoringWeights.MAX_KEYWORD_BOOST)


# ==========================================================
# 스코어 계산 유틸리티
# ==========================================================

class ScoreNormalizer:
    """스코어 계산 클래스"""
    
    @staticmethod
    def sigmoid_scale(score: float, k: float = 0.1) -> float:
        """Sigmoid 스케일링"""
        if score is None:
            return 0.0
        try:
            return 1 / (1 + math.exp(-k * score))
        except OverflowError:
            return 1.0 if score > 0 else 0.0
    
    @staticmethod
    def min_max_scale(scores: List[float]) -> List[float]:
        """Min-Max 정규화"""
        if not scores or len(scores) == 1:
            return [1.0] * len(scores)
        
        min_score = min(scores)
        max_score = max(scores)
        
        if min_score == max_score:
            return [1.0] * len(scores)
        
        return [(score - min_score) / (max_score - min_score) for score in scores]
    
    @staticmethod
    def normalize_scores(results: List[Dict], score_key: str = "hybrid_score") -> List[Dict]:
        """
        결과 리스트의 점수 정규화 (0-1 범위)
        
        Args:
            results: 결과 리스트
            score_key: 점수 키
        
        Returns:
            정규화된 결과 리스트
        """
        scores = [r.get(score_key, 0) for r in results]
        if not scores:
            return results
        
        min_score = min(scores)
        max_score = max(scores)
        score_range = max_score - min_score
        
        if score_range == 0:
            return results
        
        for result in results:
            original_score = result.get(score_key, 0)
            normalized_score = (original_score - min_score) / score_range
            result[score_key] = normalized_score
            result[f"original_{score_key}"] = original_score
        
        return results


# ==========================================================
# 필터 표현식 빌더
# ==========================================================

class FilterBuilder:
    """Milvus 필터 표현식 생성 클래스"""
    
    @staticmethod
    def build_date_filter(start_date: str, end_date: str) -> str:
        """날짜 범위 필터 생성"""
        start = start_date.replace('-', '')# + "-01"
        
        date_obj = datetime.strptime(end_date, "%Y-%m")
        # last_day = calendar.monthrange(date_obj.year, date_obj.month)[1]
        end = date_obj.strftime(f"%Y%m")#-{last_day}")
        
        return f'"{start}" <= regist_month <= "{end}"'
    
    @staticmethod
    def build_title_filter(title_filters: List[str]) -> str:
        """제목 필터 생성"""
        if not title_filters:
            return ""
        
        conditions = [f"title like '%{tf}%'" for tf in title_filters if tf]
        if not conditions:
            return ""
        
        return f"({' or '.join(conditions)})"
    
    @staticmethod
    def build_filter_expr(filters: Dict) -> str:
        """
        전체 필터 표현식 생성
        
        Args:
            filters: 필터 딕셔너리
        
        Returns:
            Milvus 필터 표현식
        """
        if not filters:
            return ""
        
        conditions = []
        
        if "lastest_expr" in filters:
            return filters["lastest_expr"]
        
        # 날짜 범위
        if "date_range" in filters:
            date_range = filters["date_range"]
            if date_range.get("start_date") and date_range.get("end_date"):
                conditions.append(
                    FilterBuilder.build_date_filter(
                        date_range["start_date"],
                        date_range["end_date"]
                    )
                )
        # elif "doc_range" in filters and :
        #     doc_range = filters["doc_range"]
        #     kms_items = next((item['list_item'] for item in doc_range if item['doc_type'] == 'kms'), [])
            # if len(kms_items) != 3:
            #     conditions.append([f"level1_tag == {s}" for s in kms_items])
        
        
        
        # 등록일 필터
        if "registdate" in filters and filters["registdate"]:
            conditions.append(f'registdate >= "{filters["registdate"]}"')
        
        # 제목 필터
        if "title_filters" in filters:
            title_filter = FilterBuilder.build_title_filter(filters["title_filters"])
            if title_filter:
                conditions.append(title_filter)
        
        # 기본 조건 (제목 필수)
        conditions.append("title is not null and title != ''") #  and token_count >= '150'
        
        return " and ".join(conditions)


# ==========================================================
# 그룹 최신성 스코어 계산
# ==========================================================

class RecencyScorer:
    """최신성 스코어 계산 클래스"""
    
    def __init__(self, decay_rate: float = 0.7):
        """
        Args:
            decay_rate: 감쇠율 (0~1)
        """
        self.decay_rate = decay_rate
    
    def calculate_scores(self, chunks: List[Dict]) -> Dict[str, float]:
        """
        그룹별 최신성 스코어 계산
        
        Args:
            chunks: 청크 리스트
        
        Returns:
            {chunk_id: recency_score}
        """
        grouped = defaultdict(list)
        
        # 제목별 그룹화
        for chunk in chunks:
            title = chunk.get("title") or chunk.get("title_og")
            if not title:
                continue
            
            try:
                registdate = datetime.fromisoformat(
                    chunk.get("registdate", "").replace(" ", "T")
                )
                grouped[title].append({
                    "id": chunk["chunk_id"],
                    "date": registdate
                })
            except (ValueError, TypeError, AttributeError):
                continue
        
        # 최신성 스코어 계산
        score_map = {}
        for items in grouped.values():
            if len(items) > 1:
                # 날짜순 정렬 (최신 -> 과거)
                items.sort(key=lambda x: x["date"], reverse=True)
                for rank, item in enumerate(items):
                    score_map[item["id"]] = self.decay_rate ** rank
            elif items:
                score_map[items[0]["id"]] = 1.0
        
        return score_map


# ==========================================================
# 메인 Milvus 클라이언트
# ==========================================================

class JustMilvusKamco:
    """Milvus 검색 클라이언트 (리팩토링 버전)"""
    
    def __init__(self, stat):
        """초기화"""
        just_env = JustEnv(stat)
        
        # 설정 로드
        retrieval_config = just_env.get_config("retrieval")
        self.milvus_config = retrieval_config.get("milvus_config", {})
        self.embedding_config = retrieval_config.get("embedding_config", {})
        self.multi_query_config = retrieval_config.get("multi_query_config", {})
        self.rerank_config = retrieval_config.get("rerank_config", {})
        self.search_config = retrieval_config.get("search_config", {})
        
        # 하이브리드 검색 설정
        self.hybrid_config = {
            'retry_attempts': self.milvus_config.get("retry_attempts", 1),
            'batch_sparse': True,
            'rrf_k': self.milvus_config.get("rrf_k", 50),
            'score_normalization': self.milvus_config.get("score_normalization", True),
            'timeout': self.milvus_config.get("timeout", 15),
            'enable_distance_scoring': self.milvus_config.get("enable_distance_scoring", True),
            'distance_weight': self.milvus_config.get("distance_weight", 0.4),
        }

        # Milvus 클라이언트 초기화
        self.client, self.sync_client = self._init_milvus_client()
        
        # 임베딩 클라이언트 초기화
        self.embedding_client = self._init_embedding_client()
        
        # 리랭커 설정
        self.reranker_url = self.rerank_config.get("reranker_base_url")
        self.reranker_model = self.rerank_config.get("reranker_model")
        
        # RRF 가중치
        self.rrf_weights = self._load_rrf_weights()
        
        # 키워드 가중치
        keyword_weights_raw = self.search_config.get("keyword_weights")
        if keyword_weights_raw is None:
            logger.warning("keyword_weights not found in search_config, using empty dict")
            self.keyword_weights = {}
        else:
            self.keyword_weights = dict(keyword_weights_raw)
        self.keyword_boost_factor = self.search_config.get("keyword_boost_factor", DefaultScoringWeights.KEYWORD_BOOST_FACTOR)
        
        # 최신성 스코어 설정
        group_recency_config = self.search_config.get("group_recency_config", {})
        self.recency_scorer = RecencyScorer(
            decay_rate=group_recency_config.get("decay_rate", 0.7)
        )
        
        # 최종 스코어 가중치
        self.final_scoring_weights = self._load_final_weights()
        
        # Exact Match 설정
        self.exact_match_config = self.search_config.get("exact_match_config", {
            "fields": ["embed_text"],
            "boost_factor": DefaultScoringWeights.EXACT_MATCH_BOOST
        })
        
        # 쿼리 저장 및 분석
        client_info = stat["client_info"]
        req_data = client_info.req_data
        self.question = req_data.messages[0].content
        self.preprocessed_question = TextNormalizer.normalize_legal_terms(self.question)
        
        # 키워드 분석기 초기화
        self.keyword_analyzer = KeywordAnalyzer(self.question, self.keyword_weights)
        self.keyword_weights = self.keyword_analyzer.keyword_weights
        self.high_priority_keywords = self.keyword_analyzer.high_priority_keywords
        # logger.debug(self.high_priority_keywords)
        
        # logger.info("JustMilvusKamco initialized")
    
    def _init_milvus_client(self) -> Optional[AsyncMilvusClient]:
        """Milvus 클라이언트 초기화"""
        try:
            url = self.milvus_config.get("milvus_url", "localhost")
            port = self.milvus_config.get("milvus_port", "19530")
            sync_client = MilvusClient(uri=f"{url}:{port}")
            client = AsyncMilvusClient(uri=f"{url}:{port}")
            # logger.info(f"Milvus client connected to {url}:{port}")
            return client, sync_client
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}", exc_info=True)
            return None
    
    def _init_embedding_client(self) -> Optional[OpenAI]:
        """임베딩 클라이언트 초기화"""
        try:
            client = get_openai_client(self.embedding_config)
            if client:
                # logger.info("Embedding client initialized")
                return client
            else:
                raise ConnectionError("Failed to get OpenAI client")
        except Exception as e:
            logger.error(f"Failed to initialize embedding client: {e}", exc_info=True)
            return None
    
    def _load_rrf_weights(self) -> List[float]:
        """RRF 가중치 로드 및 정규화"""
        weights = self.search_config.get("rrf_weights", DefaultScoringWeights.DEFAULT_RRF)
        
        if not isinstance(weights, (list, tuple)) or len(weights) != 2:
            logger.warning(f"Invalid rrf_weights: {weights}. Using default.")
            weights = DefaultScoringWeights.DEFAULT_RRF
        
        total = sum(weights)
        if total <= 0:
            weights = DefaultScoringWeights.DEFAULT_RRF
            total = sum(weights)
        
        normalized = [w / total for w in weights]
        # logger.info(f"RRF weights (normalized): {normalized}")
        return normalized
    
    def _load_final_weights(self) -> Dict[str, float]:
        """최종 스코어 가중치 로드 및 정규화"""
        weights = self.search_config.get("final_weights", 
            {
                "hybrid_keyword": DefaultScoringWeights.HYBRID_KEYWORD,
                "semantic": DefaultScoringWeights.SEMANTIC,
                "exact_match": DefaultScoringWeights.EXACT_MATCH,
                "group_recency": DefaultScoringWeights.GROUP_RECENCY,
            }
        )
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        # logger.info(f"Final scoring weights: {weights}")
        return weights
    
    # ==========================================================
    # 임베딩 및 토큰화
    # ==========================================================
    
    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        텍스트 리스트를 임베딩 벡터로 변환
        
        Args:
            texts: 텍스트 리스트
        
        Returns:
            임베딩 벡터 리스트
        """
        if not self.embedding_client:
            raise ConnectionError("Embedding client not initialized")
        
        # 빈 텍스트를 공백으로 대체
        texts_to_embed = [str(t).strip() if t and str(t).strip() else " " for t in texts]
        
        if not texts_to_embed:
            raise ValueError("No valid texts to embed")
        
        try:
            model_name = self.embedding_config.get("embedding_model", "bge-m3-ko")
            dims = self.embedding_config.get("embedding_dimensions", 2048)
            
            start_time = time.time()
            result = self.embedding_client.embeddings.create(
                input=texts_to_embed,
                model=model_name
            )
            
            elapsed = time.time() - start_time
            # logger.info(f"Encoded {len(texts_to_embed)} texts in {elapsed:.2f}s")
            
            return [x.embedding for x in result.data]
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}", exc_info=True)
            dims = self.embedding_config.get("embedding_dimensions", 2048)
            return [[0.0] * dims for _ in texts_to_embed]
    
    def tokenize(self, text: str) -> str:
        """
        단일 텍스트 토큰화
        
        Args:
            text: 원본 텍스트
        
        Returns:
            토큰화된 텍스트
        """
        if not text or not isinstance(text, str):
            return ""
        
        try:
            tokens = kiwi.tokenize(text, stopwords=stopwords)
            return " ".join([token.form for token in tokens])
        except Exception as e:
            logger.error(f"Tokenization failed: {e}", exc_info=True)
            return " ".join(text.split())
    
    def tokenize_batch(self, texts: List[str]) -> List[str]:
        """배치 토큰화"""
        return [self.tokenize(t) for t in texts]
    
    # ==========================================================
    # 하이브리드 검색
    # ==========================================================
    
    async def hybrid_search_chunks_batch(
        self,
        dense_embeddings: List,
        dense_collection_name: str,
        sparse_tokens: List[str],
        sparse_collection_name: str,
        top_k: int = 30,
        output_fields: Optional[List] = None,
        filters: Optional[Dict] = None,
        extracted_rule: Optional[str] = None
    ) -> List[Dict]:
        """
        배치 하이브리드 검색
        
        Args:
            dense_embeddings: Dense 임베딩 리스트
            dense_collection_name: Dense 컬렉션 이름
            sparse_tokens: Sparse 토큰 리스트
            sparse_collection_name: Sparse 컬렉션 이름
            top_k: 상위 K개 결과
            output_fields: 출력 필드
            filters: 필터 조건
        
        Returns:
            검색 결과 리스트
        """
        start_time = time.time()
        search_id = f"search_{int(start_time)}"
        
        try:
            return await self._perform_hybrid_search(
                dense_embeddings,
                dense_collection_name,
                sparse_tokens,
                sparse_collection_name,
                top_k,
                output_fields,
                filters,
                search_id,
                extracted_rule
            )
        except Exception as e:
            logger.error(f"[{search_id}] Hybrid search failed: {e}", exc_info=True)
            return []
        finally:
            elapsed = time.time() - start_time
            # logger.debug(f"[{search_id}] Completed in {elapsed:.2f}s")
    
    async def _perform_hybrid_search(
        self,
        dense_embeddings: List,
        dense_collection_name: str,
        sparse_tokens: List[str],
        sparse_collection_name: str,
        top_k: int,
        output_fields: Optional[List],
        filters: Optional[Dict],
        search_id: str,
        extracted_rule: Optional[str] = None
    ) -> List[Dict]:
        """하이브리드 검색 실행"""
        
        if not self.client:
            raise ConnectionError("Milvus client not initialized")
        
        num_queries = len(dense_embeddings)
        if num_queries == 0:
            logger.warning(f"[{search_id}] Empty query list")
            return []
        
        if len(sparse_tokens) != num_queries:
            logger.warning(f"[{search_id}] Length mismatch: dense={num_queries}, sparse={len(sparse_tokens)}")
            return []
        
        # 필터 표현식 생성
        expr = FilterBuilder.build_filter_expr(filters) if filters else ""
        # logger.info(expr) # registdate >= "2022-01-01" and registdate <= "2025-08-31" and title is not null and title != ''
        # self.high_priority_keywords

        ### 규정 관련 내용이 milvus에 실제로 있는지 검증 ###
        if extracted_rule is not None:
            if extracted_rule:
                rule_expr = f" and title LIKE '%{extracted_rule}%'"
                eval_expr = expr
                eval_expr += rule_expr
                
                from pymilvus import connections, Collection
                import pandas as pd
                
                milvus_url = self.milvus_config.get("milvus_url", "localhost").replace("http://", "")
                milvus_port = self.milvus_config.get("milvus_port", "19530")
                check_kms_dense_collection = self.milvus_config.get("kms_dense_collection_name", "")
                
                connections.connect("default", host = milvus_url, port= milvus_port)

                # 2. Collection 불러오기
                collection = Collection(check_kms_dense_collection)

                results = collection.query(
                    expr=eval_expr,
                    output_fields=["title"],
                    limit = 2000,
                    sort=["registdate", "desc"]
                )
                
                logger.info(len(results))
                if not len(results) == 0:
                    logger.debug("규정관련문서로 검색을 시작합니다.")
                    expr += rule_expr
        ###
        
        if 'approval' in dense_collection_name or 'approval' in sparse_collection_name:
            exclude_title = ['업무택시', '재택근무', '출장결과보고', '출장명령서', '출장비용 전표 승인', '외부강의 허가 신청', '계정처리서', '숙박비 지급 요청', '국외출장 여비', '지급요청', '요청 승인']
            exclude_formid = list(set(['HGW6X152733299750000', 'HGW6X092540644994000', 'JHOMS201951174458000', 'HGW6X163633253626000', 'JHOMS201951174458000',
                              'JHOMS201951174542000', 'JHOMS202942392105000', 'JHOMS223182178442000', 'HGW6X150270726015000', 'HGW6X103052054843000',
                              'HGW6X113214388187000', 'HGW6X092540645007000', 'HGW6X092540644994000', 'HGW6X163272838104000', 'HGW6X120754745904000', 
                              'HGW6X090080053631000', 'HGW6X140881144319000', 'HGW6X152733299750000', 'JHOMS202331651039000', 'HGW6X092540645007000', 
                              'HGW6X092540644983000', 'HGW6X092540644994000', 'HGW6X152733299750000', 'JHOMS202391723581000', 'JHOMS202391723523000', 
                              'HGW6X171154397472000']))
                        
            title_conditions = [f'title like "%{kw}%"' for kw in exclude_title]
            formid_conditions = [f'formid == "{kw}"' for kw in exclude_title]

            add_conditions = []
            add_conditions = title_conditions + formid_conditions
            
            add_expr = f' AND NOT ({" OR ".join(add_conditions)})'
            expr += add_expr
            # top_k = top_k * 3

        elif 'kms' in dense_collection_name or 'kms' in sparse_collection_name:
            if "doc_range" in filters:
                category_display_map = {
                    '지식 허브': '지식허브',
                    '내규 법령 센터': '법률질의',
                    'Q&A 데스크': '업무Q&A'
                }
                doc_range = filters["doc_range"]
                kms_items = [
                    category_display_map.get(item.strip(), item)   # 매핑되지 않으면 원본 반환
                    for d in doc_range if d['doc_type'] == 'kms'
                    for item in d['list_item']
                ]
                add_expr = f" AND level1_tag IN {kms_items} AND status == '3000'" # 상태값 3000인 경우만 추출
                expr += add_expr
        elif 'bheader' in dense_collection_name or 'bheader' in sparse_collection_name:
            current_date = datetime.now().strftime('%Y-%m-%d')
            add_expr = f"end_date >= '{current_date}' AND " # 게시 종료일 추가
            add_expr += expr
            expr = add_expr
            
        # logger.info(f"[{search_id}] Starting hybrid search: {num_queries} queries, top_k={top_k}")
        # logger.debug(f"[{search_id}] Filter: {expr[:100]}...")
        
        # Dense 검색
        dense_results = await self._search_dense(
            dense_embeddings,
            dense_collection_name,
            top_k,
            expr,
            search_id
        )
        
        # Sparse 검색
        sparse_results = await self._search_sparse(
            sparse_tokens,
            sparse_collection_name,
            top_k,
            expr,
            search_id
        )
        
        # 결과 통합
        final_results = self._integrate_results(
            dense_results,
            sparse_results,
            num_queries,
            search_id
        )
        
        # logger.info(f"[{search_id}] Final results: {len(final_results)}")
        return final_results
    
    async def _search_dense(
        self,
        embeddings: List,
        collection_name: str,
        top_k: int,
        expr: str,
        search_id: str
    ) -> List:
        """Dense 검색"""
        
        if not collection_name:
            logger.warning(f"[{search_id}] No dense collection name")
            return [[] for _ in embeddings]
        
        for attempt in range(self.hybrid_config["retry_attempts"] + 1):
            try:
                start_time = time.time()
                if 'approval' in collection_name:
                    search_params = {"metric_type": "COSINE", "params": {"ef": 8192}}
                else:
                    search_params = {"metric_type": "COSINE", "params": {"nprobe": 1024}}

                # results = await self.client.search(
                #     collection_name=collection_name,
                #     data=embeddings,
                #     limit=top_k,
                #     output_fields=["*"],
                #     filter=expr,
                #     timeout=self.hybrid_config["timeout"],
                #     search_params = search_params
                # )
                
                results = await self.client.search(
                    collection_name=collection_name,
                    data=embeddings,
                    limit=top_k,
                    output_fields=["*"],
                    filter=expr,
                    timeout=self.hybrid_config["timeout"],
                    search_params = search_params
                    # search_params = {
                    #     "metric_type": "COSINE",
                    #     "params": {
                    #         "nprobe": 16384
                    #     }
                    # }
                )
                
                elapsed = time.time() - start_time
                total_result = sum([len(result) for result in results])
                # logger.info(f"[{collection_name}] Num queries: {len(results)} Dense search completed: {total_result} queries, {elapsed:.2f}s")
                
                return results
                
            except Exception as e:
                logger.error(f"[{collection_name}] Dense search failed (attempt {attempt + 1}): {e}")
                
                if attempt < self.hybrid_config["retry_attempts"]:
                    time.sleep(0.5 * (attempt + 1))
                else:
                    return [[] for _ in embeddings]
    
    async def _search_sparse(
        self,
        tokens: List[str],
        collection_name: str,
        top_k: int,
        expr: str,
        search_id: str
    ) -> List:
        """Sparse 검색"""
        
        if not collection_name:
            logger.warning(f"[{search_id}] No sparse collection name")
            return [[] for _ in tokens]
        
        valid_tokens = [t for t in tokens if t and t.strip()]
        if not valid_tokens:
            logger.warning(f"[{search_id}] No valid sparse tokens")
            return [[] for _ in tokens]
        
        # 배치 검색 시도
        # if self.high_priority_keywords:
        #     text_match_list = []
        #     for kw in self.high_priority_keywords:
        #         text_match_list.append(f"TEXT_MATCH(tokenized_text, '{kw}')")

        #     text_match = ' OR '.join(text_match_list)
        #     expr = f"{text_match} AND ({expr})"

        if self.hybrid_config["batch_sparse"] and len(valid_tokens) > 1:
            return await self._search_sparse_batch(tokens, collection_name, top_k, expr, search_id)
        else:
            return await self._search_sparse_individual(tokens, collection_name, top_k, expr, search_id)
    
    async def _search_sparse_batch(
        self,
        tokens: List[str],
        collection_name: str,
        top_k: int,
        expr: str,
        search_id: str
    ) -> List:
        """Sparse 배치 검색"""
        
        try:
            valid_tokens = [t for t in tokens if t and t.strip()]
            
            start_time = time.time()
            batch_results = await self.client.search(
                collection_name=collection_name,
                data=valid_tokens,
                limit=top_k,
                output_fields=["*"],
                filter=expr,
                timeout=self.hybrid_config["timeout"],
                search_params={"metric_type": "BM25"}
            )
            
            elapsed = time.time() - start_time
            total_result = sum([len(result) for result in batch_results])
            # logger.info(f"[{collection_name}] Num queries: {len(batch_results)} Sparse batch search completed: {total_result} results, {elapsed:.2f}s")
            
            # 결과 정렬
            aligned_results = []
            batch_idx = 0
            
            for token in tokens:
                if token and token.strip():
                    if batch_idx < len(batch_results):
                        aligned_results.append(batch_results[batch_idx])
                        batch_idx += 1
                    else:
                        aligned_results.append([])
                else:
                    aligned_results.append([])
            
            return aligned_results
            
        except Exception as e:
            logger.warning(f"[{collection_name}] Sparse batch search failed, fallback to individual: {e}")
            return self._search_sparse_individual(tokens, collection_name, top_k, expr, search_id)
    
    async def _search_sparse_individual(
        self,
        tokens: List[str],
        collection_name: str,
        top_k: int,
        expr: str,
        search_id: str
    ) -> List:
        """Sparse 개별 검색"""
        
        results = []
        success_count = 0
        
        for i, token in enumerate(tokens):
            if not token or not token.strip():
                results.append([])
                continue
            
            for attempt in range(self.hybrid_config["retry_attempts"] + 1):
                try:
                    result = await self.client.search(
                        collection_name=collection_name,
                        data=[token],
                        limit=top_k,
                        output_fields=["*"],
                        filter=expr,
                        timeout=self.hybrid_config["timeout"],
                        search_params={"metric_type": "BM25"}
                    )
                    
                    results.append(result)
                    success_count += 1
                    break
                    
                except Exception as e:
                    if attempt < self.hybrid_config["retry_attempts"]:
                        time.sleep(0.1 * (attempt + 1))
                    else:
                        logger.error(f"[{collection_name}] Sparse query {i+1} failed: {e}")
                        results.append([])
        
        # logger.info(f"[{search_id}] Sparse individual search completed: {success_count}/{len(tokens)} succeeded")
        return results

    async def get_lastest_conds(self, collection_name: str, filter_expr:str) -> List[str]:
        try:
            # result = await self.client.query(
            #     collection_name=collection_name,
            #     output_fields=["title", "registdate", "original_chunk"],
            #     filter=filter_expr,
            #     timeout=self.hybrid_config["timeout"],
            # )

            iterator = self.sync_client.query_iterator(
                collection_name=collection_name,
                output_fields=["title", "regist_month", "original_chunk"],
                filter=filter_expr,
                timeout=self.hybrid_config["timeout"],
                batch_size=100,
                offset=0,
            )
            result = []
            while True:
                # offset += limit
                try:
                    batch = iterator.next()

                    if not batch:
                        logger.debug("모든 데이터 조회 완료")
                        break
                        
                    result.extend(batch)
                except StopIteration:
                    logger.error("Iterator 완료")
                    break

            return result

        except Exception as e:
            logger.error(f"Error in {collection_name} search: {e}", exc_info=True)
            return []


    def _integrate_results(
        self,
        dense_results: List,
        sparse_results: List,
        num_queries: int,
        search_id: str
    ) -> List[Dict]:
        """검색 결과 통합 및 RRF 적용"""
        
        all_results_dict = {}
        
        for i in range(num_queries):
            dense_hits = dense_results[i] if i < len(dense_results) else []
            sparse_hits = (sparse_results[i][0]
                          if i < len(sparse_results) and sparse_results[i]
                          else [])
            
            # 결과 추출
            dense_extracted = self._extract_results(dense_hits)
            sparse_extracted = self._extract_results(sparse_hits)
            
            # RRF 적용
            query_results = self._apply_rrf(
                dense_extracted,
                sparse_extracted,
                self.rrf_weights,
            )
            
            # 결과 통합 (최고 점수 유지)
            for chunk in query_results:
                chunk_id = chunk.get("chunk_id")
                if chunk_id is None:
                    continue
                
                current_score = chunk.get("hybrid_score", 0.0)
                
                if (chunk_id not in all_results_dict or
                    current_score > all_results_dict[chunk_id].get("hybrid_score", 0.0)):
                    all_results_dict[chunk_id] = chunk
        
        # 최종 정렬 및 정규화
        final_results = list(all_results_dict.values())
        
        if self.hybrid_config["score_normalization"] and final_results:
            final_results = ScoreNormalizer.normalize_scores(final_results, "hybrid_score")
        
        final_results.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)
        
        return final_results
    
    def _extract_results(self, search_results: Any) -> List[Dict]:
        """검색 결과에서 데이터 추출"""
        
        extracted = []
        if not search_results:
            return extracted
        
        # 결과 평탄화
        all_hits = []
        if isinstance(search_results, list) and search_results and isinstance(search_results[0], list):
            for query_hits in search_results:
                if isinstance(query_hits, list):
                    all_hits.extend(query_hits)
        else:
            all_hits = search_results
        
        # 각 히트 처리
        for hit in all_hits:
            try:
                result_dict = {}
                
                # ID 및 Distance
                if hasattr(hit, "id"):
                    result_dict["id"] = hit.id
                if hasattr(hit, "distance"):
                    result_dict["distance"] = hit.distance
                
                # Entity 추출
                if hasattr(hit, "entity") and hit.entity is not None:
                    result_dict.update(vars(hit.entity))
                elif isinstance(hit, dict):
                    result_dict.update(hit)
                    if "entity" in hit and isinstance(hit["entity"], dict):
                        result_dict.update(hit["entity"])
                        del result_dict["entity"]
                
                # chunk_id 생성
                if result_dict.get("chunk_id") is None and result_dict.get("id"):
                    result_dict["chunk_id"] = str(result_dict["id"])
                
                # chunk_id가 있는 경우만 추가
                if "chunk_id" in result_dict:
                    extracted.append(result_dict)
                    
            except Exception as e:
                logger.error(f"Error extracting data: {e}", exc_info=True)
                continue
        
        return extracted
    
    def _apply_rrf(
        self,
        dense_results: List[Dict],
        sparse_results: List[Dict],
        weights: Tuple[float, float],
    ) -> List[Dict]:
        """RRF 알고리즘 적용"""
        
        dense_weight, sparse_weight = weights
        rrf_scores = defaultdict(lambda: {"hybrid_score": 0.0})
        k = self.hybrid_config["rrf_k"]
        
        # Dense 결과 처리 (Distance 정보 포함)
        # if dense_results and self.hybrid_config["enable_distance_scoring"]:
            # distances = [r.get("distance", 0) for r in dense_results if r.get("distance") is not None]
            
            # if distances:
            #     min_dist = min(distances)
            #     max_dist = max(distances)
            #     dist_range = max_dist - min_dist if max_dist != min_dist else 1.0
            # else:
            #     min_dist = max_dist = dist_range = 0
        if dense_results:  
            for rank, result in enumerate(dense_results):
                chunk_id = result.get("chunk_id")
                if chunk_id is None:
                    continue
                
                # RRF 점수
                rrf_score = 1 / (k + rank + 1)
                
                
                # TODO distance를 쓸지말지 테스트 -> 쓰니까 결과 안좋아짐
                # # Distance 기반 유사도 점수
                # if (self.hybrid_config["enable_distance_scoring"] and
                #     result.get("distance") is not None and dist_range > 0):
                #     distance = result.get("distance", 0)
                #     similarity_score = 1 - ((distance - min_dist) / dist_range)
                    
                #     # RRF와 Distance 결합
                #     combined_score = (
                #         (1 - self.hybrid_config["distance_weight"]) * rrf_score +
                #         self.hybrid_config["distance_weight"] * similarity_score
                #     )
                #     final_score = dense_weight * combined_score
                # else:
                #     final_score = dense_weight * rrf_score
                final_score = dense_weight * rrf_score
                
                rrf_scores[chunk_id].update(result)
                rrf_scores[chunk_id]["hybrid_score"] += final_score
        
        # Sparse 결과 처리
        if sparse_results:
            for rank, result in enumerate(sparse_results):
                chunk_id = result.get("chunk_id")
                if chunk_id is None:
                    continue
                
                rrf_score = 1 / (k + rank + 1)
                final_score = sparse_weight * rrf_score
                
                if chunk_id not in rrf_scores:
                    rrf_scores[chunk_id].update(result)
                
                rrf_scores[chunk_id]["hybrid_score"] += final_score
        
        return list(rrf_scores.values())
    
    # ==========================================================
    # 키워드 부스트
    # ==========================================================
    
    def _calculate_keyword_boost(self, text: str) -> float:
        """
        키워드 부스트 점수 계산 (래퍼 메서드)
        
        Args:
            text: 평가할 텍스트
        
        Returns:
            부스트 점수
        """
        return self.keyword_analyzer.calculate_boost(text)
    
    # ==========================================================
    # 리랭킹 및 최종 스코어링
    # ==========================================================
    
    def rerank_and_score_final(
        self,
        base_query: str,
        chunks: List[Dict],
        category_top_k: int = 5,
        top_k: int = 5,
    ) -> List[Dict]:
        """
        최종 리랭킹 및 스코어링
        
        Args:
            base_query: 기본 쿼리
            chunks: 청크 리스트
            category_top_k: 카테고리별 상위 K개
            top_k: 상위 K개
        
        Returns:
            최종 스코어가 계산된 청크 리스트
        """
        if not chunks:
            return []
        
        # 1. 청크 데이터 추출
        processed_chunks = []
        
        for chunk in chunks:
            if chunk.get('title'):
                entity = chunk
            else:
                entity = chunk.get('data', chunk.get('entity', {}))
                if isinstance(entity, dict):
                    entity = entity.get('entity', entity)
                entity['hybrid_score'] = chunk.get('hybrid_score', 0.0)
                entity['distance'] = chunk.get('distance', 0.0)
                entity['original_hybrid_score'] = chunk.get('original_hybrid_score', 0.0)
                entity['hybrid_score_with_keyword'] = chunk.get('hybrid_score_with_keyword', 0.0)
            
            processed_chunks.append(entity)

        # 2. Semantic 점수 계산
        semantic_scores, semantic_method = self._calculate_semantic_scores(
            base_query,
            processed_chunks
        )
        
        # 3. 가중치 조정 (semantic 점수 실패 시)
        weights = self._adjust_weights(semantic_method != "None")
        # logger.info(f'weights: {weights}')
        
        # # 4. 그룹 최신성 점수 계산
        # recency_scores = self.recency_scorer.calculate_scores(processed_chunks)
        
        # 5. 최종 스코어 계산
        final_scored_list = []
        for i, chunk in enumerate(processed_chunks):
            chunk_id = chunk.get("chunk_id")
            
            # 하이브리드 + 키워드 점수 (Sigmoid 스케일링)
            hybrid_raw = chunk.get("hybrid_score_with_keyword", 0.0)
            # logger.info(f'hybrid_raw: {hybrid_raw}')
            hybrid_score = ScoreNormalizer.sigmoid_scale(hybrid_raw, k=0.3) # 0.1
            # hybrid_score = hybrid_raw
            # logger.info(f'hybrid_score: {hybrid_score}')
            
            # Semantic 점수
            semantic_score = semantic_scores[i]
            # logger.info(f'semantic_score: {semantic_score}\n')
            
            # Exact Match 점수
            # exact_match_score = self._calculate_exact_match_score(chunk)
            exact_match_score = 0.0
            
            # 그룹 최신성 점수
            # recency_score = recency_scores.get(chunk_id, 0.0)
            recency_score = 0.0
            
            # 최종 점수 계산
            # final_score = (semantic_score)
            final_score = (
                weights["hybrid_keyword"] * hybrid_score +
                weights["semantic"] * semantic_score +
                weights["exact_match"] * exact_match_score +
                weights["group_recency"] * recency_score
            )

            # level1_tag = chunk.get("level1_tag")
            # if level1_tag == '전자결재':
            #     final_score = final_score*0.90
            # elif level1_tag == '게시판':
            #     final_score = final_score*0.95
            # else:
            #     final_score = final_score*1.00

            final_scored_list.append({
                **chunk,
                "score_details": {
                    "hybrid_keyword_score": float(hybrid_score),
                    "semantic_score": float(semantic_score),
                    "exact_match_score": float(exact_match_score),
                    "group_recency_score": float(recency_score),
                    "semantic_method": semantic_method
                },
                "final_score": float(final_score)
            })
        
        # 카테고리 별 최대 K개 추출
        from itertools import groupby
        sorted_data = sorted(final_scored_list, key=lambda x: (x['level1_tag'], -x['final_score']))
        result = []

        for tag, group in groupby(sorted_data, key=lambda x: x['level1_tag']):
            top_items = list(group)[:category_top_k]
            result.extend(top_items)
            
        result.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
        
        return result[:top_k]
        # final_scored_list.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
        # return final_scored_list[:top_k]
    
    def _calculate_semantic_scores(
        self,
        query: str,
        chunks: List[Dict]
    ) -> Tuple[List[float], str]:
        """
        Semantic 점수 계산 (Cross-Encoder 또는 Bi-Encoder)
        
        Args:
            query: 쿼리
            chunks: 청크 리스트
        
        Returns:
            (점수 리스트, 사용된 방법)
        """
        chunk_texts = [c.get("embed_text", c.get("orig_text", "")) for c in chunks]
        semantic_scores = [0.0] * len(chunk_texts)
        method = "None"
        
        # Cross-Encoder 시도
        if self.reranker_url and self.reranker_model:
            try:
                cross_scores = self._call_reranker_api(query, chunk_texts)
                if len(cross_scores) == len(chunk_texts):
                    semantic_scores = cross_scores
                    method = "Cross-Encoder"
                    # logger.info("Successfully used Cross-Encoder for semantic scoring")
            except Exception as e:
                logger.error(f"Cross-Encoder failed: {e}", exc_info=True)
        
        # Bi-Encoder fallback
        if method == "None":
            try:
                vectors = self.encode([query] + chunk_texts)
                if len(vectors) == len(chunk_texts) + 1:
                    query_vec = vectors[0]
                    chunk_vecs = vectors[1:]
                    
                    # Cosine 유사도 계산 및 정규화
                    bi_scores = [(1 - cosine(query_vec, doc_vec)) / 2.0 for doc_vec in chunk_vecs]
                    semantic_scores = bi_scores
                    method = "Bi-Encoder"
                    # logger.info("Cross-Encoder failed, But Successfully used Bi-Encoder for semantic scoring")
            except Exception as e:
                logger.error(f"Bi-Encoder failed: {e}", exc_info=True)
    
        # Min-Max 정규화
        semantic_scores = ScoreNormalizer.min_max_scale(semantic_scores)
        
        return semantic_scores, method
    
    def _call_reranker_api(self, query: str, documents: List[str]) -> List[float]:
        """리랭커 API 호출"""
        if not self.reranker_url or not self.reranker_model:
            raise ValueError("Reranker API not configured")
        
        if not query or not documents:
            return [0.0] * len(documents)
        
        try:
            # 모델별 포맷팅
            if self.reranker_model == "telepix-pixie-spell-reranker":
                query, documents = self._format_pixie_spell(query, documents)
            
            payload = {
                "model": self.reranker_model,
                "text_1": query,
                "text_2": documents
            }

            response = requests.post(
                self.reranker_url,
                headers={"User-Agent": "Rerank Client"},
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            scores = [result["score"] for result in response.json()["data"]]
            
            if len(scores) != len(documents):
                logger.warning(f"Score count mismatch: {len(scores)} != {len(documents)}")
                return [0.0]# * len(documents)
            
            return scores
            
        except Exception as e:
            logger.error(f"Reranker API call failed: {e}", exc_info=True)
            return [0.0]# * len(documents)
    
    def _format_pixie_spell(
        self,
        query: str,
        documents: List[str]
    ) -> Tuple[str, List[str]]:
        """Pixie-Spell 리랭커용 포맷팅"""
        
        def format_query(q: str, instruction: str = None) -> str:
            prefix = (
                '<|im_start|>system\n'
                'Judge whether the Document meets the requirements based on the Query and the Instruct provided. '
                'Note that the answer can only be "yes" or "no".<|im_end|>\n'
                '<|im_start|>user\n'
            )
            if instruction is None:
                instruction = "Given a web search query, retrieve relevant passages that answer the query"
            return f"{prefix}<Instruct>: {instruction}\n<Query>: {q}\n"
        
        def format_document(doc: str) -> str:
            suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
            return f"<Document>: {doc}{suffix}"
        
        task = "Given a web search query, retrieve relevant passages that answer the query"
        formatted_query = format_query(query, task)
        formatted_docs = [format_document(doc) for doc in documents]
        
        return [formatted_query] * len(documents), formatted_docs
    
    def _adjust_weights(self, semantic_success: bool) -> Dict[str, float]:
        """가중치 조정 (semantic 실패 시)"""
        weights = self.final_scoring_weights.copy()
        
        if not semantic_success:
            semantic_weight = weights.get("semantic", 0)
            weights["semantic"] = 0.0
            
            # semantic 가중치를 hybrid_keyword에 재분배
            if "hybrid_keyword" in weights:
                weights["hybrid_keyword"] += semantic_weight
            
            # 정규화
            total = sum(weights.values())
            if total > 0:
                weights = {k: v / total for k, v in weights.items()}
        
        return weights
    
    def _calculate_exact_match_score(self, chunk: Dict) -> float:
        """
        Exact Match 점수 계산
        
        Args:
            chunk: 청크 데이터
        
        Returns:
            Exact Match 점수 (0.0 ~ boost_factor)
        """
        if not self.high_priority_keywords:
            return 0.0
        
        # 필드 텍스트 추출 및 정규화
        fields = self.exact_match_config.get("fields", ["embed_text"])
        combined_text = "".join([str(chunk.get(field, "")) for field in fields])
        normalized_text = TextNormalizer.normalize_legal_terms(combined_text)
        
        if not normalized_text:
            return 0.0
        
        # 매칭 카운트
        match_count = sum(1 for kw in self.high_priority_keywords if kw in normalized_text)
        
        # 비율 계산 및 부스트 적용
        score = match_count / len(self.high_priority_keywords)
        boost_factor = self.exact_match_config.get("boost_factor", 1.1)
        
        return min(score * boost_factor, 1.0)


# ==========================================================
# End of file
# ==========================================================
