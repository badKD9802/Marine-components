"""
포트폴리오 RAG 검색 모듈
포트폴리오 내용을 임베딩하여 사용자 질문과 관련된 섹션만 검색
"""

import pandas as pd
import numpy as np
from openai import AsyncOpenAI
from typing import List, Dict
from portfolio_data import get_portfolio_dataframe
import asyncio
import pickle
import os

# 임베딩 캐시 파일 경로
EMBEDDING_CACHE_FILE = "portfolio_embeddings.pkl"

class PortfolioRAG:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.df = get_portfolio_dataframe()
        self.embeddings = None
        self.embedding_model = "text-embedding-3-small"

    async def generate_embeddings(self):
        """포트폴리오 섹션별로 임베딩 생성"""
        print("[Portfolio RAG] 임베딩 생성 중...")

        embeddings = []
        for idx, row in self.df.iterrows():
            # 제목 + 내용을 합쳐서 임베딩
            text = f"{row['title']}\n\n{row['content']}"

            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            embedding = response.data[0].embedding
            embeddings.append(embedding)

        self.embeddings = np.array(embeddings)
        print(f"[Portfolio RAG] 임베딩 생성 완료: {len(embeddings)}개 섹션")

        # 캐시 저장
        self._save_embeddings_cache()

        return self.embeddings

    def _save_embeddings_cache(self):
        """임베딩 캐시 저장"""
        cache_data = {
            'embeddings': self.embeddings,
            'df': self.df
        }
        with open(EMBEDDING_CACHE_FILE, 'wb') as f:
            pickle.dump(cache_data, f)
        print(f"[Portfolio RAG] 임베딩 캐시 저장 완료: {EMBEDDING_CACHE_FILE}")

    def _load_embeddings_cache(self):
        """임베딩 캐시 로드"""
        if os.path.exists(EMBEDDING_CACHE_FILE):
            try:
                with open(EMBEDDING_CACHE_FILE, 'rb') as f:
                    cache_data = pickle.load(f)
                self.embeddings = cache_data['embeddings']
                self.df = cache_data['df']
                print(f"[Portfolio RAG] 임베딩 캐시 로드 완료: {len(self.embeddings)}개 섹션")
                return True
            except Exception as e:
                print(f"[Portfolio RAG] 캐시 로드 실패: {e}")
                return False
        return False

    async def ensure_embeddings(self):
        """임베딩이 없으면 생성, 있으면 캐시 사용"""
        if self.embeddings is not None:
            return

        # 캐시에서 로드 시도
        if self._load_embeddings_cache():
            return

        # 캐시 없으면 생성
        await self.generate_embeddings()

    async def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        사용자 질문과 가장 유사한 포트폴리오 섹션 검색

        Args:
            query: 사용자 질문
            top_k: 반환할 섹션 개수

        Returns:
            List[Dict]: 유사도 순으로 정렬된 섹션 리스트
        """
        await self.ensure_embeddings()

        # 질문 임베딩
        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=query
        )
        query_embedding = np.array(response.data[0].embedding)

        # 코사인 유사도 계산
        similarities = np.dot(self.embeddings, query_embedding) / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # Top-K 인덱스
        top_indices = np.argsort(similarities)[::-1][:top_k]

        # 결과 구성
        results = []
        for idx in top_indices:
            row = self.df.iloc[idx]
            results.append({
                'category': row['category'],
                'title': row['title'],
                'content': row['content'],
                'similarity': float(similarities[idx])
            })

        print(f"[Portfolio RAG] 검색 완료: Top-{top_k} (유사도: {[f'{r['similarity']:.3f}' for r in results]})")
        return results

    async def get_relevant_context(self, query: str, top_k: int = 3, min_similarity: float = 0.3) -> str:
        """
        사용자 질문과 관련된 포트폴리오 컨텍스트를 문자열로 반환

        Args:
            query: 사용자 질문
            top_k: 검색할 섹션 개수
            min_similarity: 최소 유사도 (이 값보다 낮으면 제외)

        Returns:
            str: 관련 섹션들을 합친 텍스트
        """
        results = await self.search(query, top_k=top_k)

        # 최소 유사도 필터링
        filtered = [r for r in results if r['similarity'] >= min_similarity]

        if not filtered:
            print(f"[Portfolio RAG] 유사도 {min_similarity} 이상인 섹션 없음, 기본 정보 반환")
            # 기본 정보 (프로필 + 핵심 역량)
            filtered = [r for r in results[:2]]

        # 컨텍스트 구성
        context_parts = []
        for r in filtered:
            context_parts.append(f"## {r['title']}\n{r['content']}")

        return "\n\n".join(context_parts)


# 전역 인스턴스 (서버 시작 시 초기화)
_portfolio_rag: PortfolioRAG = None

def init_portfolio_rag(api_key: str):
    """포트폴리오 RAG 초기화"""
    global _portfolio_rag
    _portfolio_rag = PortfolioRAG(api_key)
    print("[Portfolio RAG] 초기화 완료")

async def search_portfolio(query: str, top_k: int = 3) -> str:
    """포트폴리오 검색 (외부 호출용)"""
    if _portfolio_rag is None:
        raise RuntimeError("Portfolio RAG가 초기화되지 않았습니다. init_portfolio_rag() 먼저 호출하세요.")

    return await _portfolio_rag.get_relevant_context(query, top_k=top_k)
