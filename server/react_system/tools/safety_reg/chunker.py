"""Parent-Child 계층적 청킹 + Contextual Retrieval.

법령 XML 구조(조/항/호/목)를 활용한 계층적 청킹:
- Parent: 조(Article) 전체 → LLM 답변 생성용 컨텍스트
- Child: 항(Paragraph) 단위 → 검색 매칭용 임베딩

Contextual Retrieval: 모든 Child에 계층 경로 + 맥락 prepend하여
검색 정확도를 높인다.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import List

from react_system.tools.safety_reg.law_api_client import (
    Article,
    ArticleItem,
    SafetyDocument,
)

logger = logging.getLogger(__name__)

# 교차 참조 패턴: "제N조", "제N조의N", "제N조제N항"
CROSS_REF_PATTERN = re.compile(r'제(\d+)조(?:의(\d+))?(?:제(\d+)항)?')


@dataclass
class SafetyChunk:
    """검색/인덱싱용 청크 단위."""

    chunk_id: str = ""  # "LAW_산업안전보건법_제13조" (Parent) 또는 "_제1항" (Child)
    chunk_type: str = ""  # "parent" | "child"
    parent_chunk_id: str = ""  # Child인 경우 Parent의 chunk_id
    doc_name: str = ""  # "산업안전보건법"
    doc_type: str = ""  # "법령" | "행정규칙" | ...
    article_ref: str = ""  # "제13조제1항"
    section_hierarchy: str = ""  # "제2장 안전보건관리체제 > 제13조 안전보건총괄책임자"
    orig_text: str = ""  # 원본 텍스트 (답변 인용용)
    embed_text: str = ""  # 계층경로 + 맥락 + 원본 (임베딩용)
    source_url: str = ""  # law.go.kr 링크
    effective_date: str = ""  # 시행일
    references_to: str = "[]"  # JSON: 이 청크가 참조하는 조문들
    referenced_by: str = "[]"  # JSON: 이 청크를 참조하는 조문들 (후처리)


class SafetyChunker:
    """법령 문서 → Parent-Child 청크 변환."""

    def chunk_document(self, doc: SafetyDocument) -> List[SafetyChunk]:
        """SafetyDocument → SafetyChunk 리스트.

        Args:
            doc: 법령 문서

        Returns:
            Parent + Child 청크 리스트
        """
        chunks = []
        # 장/절 매핑 (조문번호 → 소속 장/절)
        chapter_map = self._build_chapter_map(doc)

        for article in doc.articles:
            if not article.article_no:
                continue

            article_ref = f"제{article.article_no}조"
            if article.article_title:
                article_ref_full = f"제{article.article_no}조({article.article_title})"
            else:
                article_ref_full = article_ref

            # 계층 경로
            hierarchy = self._build_hierarchy(doc.doc_name, chapter_map, article)

            # Parent 청크 (조 전체)
            parent_text = self._build_parent_text(article)
            parent_id = f"{doc.doc_type}_{doc.doc_name}_{article_ref}"

            parent_chunk = SafetyChunk(
                chunk_id=parent_id,
                chunk_type="parent",
                parent_chunk_id=parent_id,  # 자기 자신
                doc_name=doc.doc_name,
                doc_type=doc.doc_type,
                article_ref=article_ref_full,
                section_hierarchy=hierarchy,
                orig_text=parent_text,
                embed_text=self._build_embed_text(hierarchy, parent_text, "parent"),
                source_url=doc.source_url,
                effective_date=doc.effective_date,
                references_to=json.dumps(self._extract_cross_refs(parent_text), ensure_ascii=False),
            )
            chunks.append(parent_chunk)

            # Child 청크 (항 단위)
            if article.paragraphs:
                child_chunks = self._chunk_paragraphs(article, doc, parent_id, hierarchy)
                chunks.extend(child_chunks)
            else:
                # 항이 없는 단문 조문 → Child = Parent와 동일
                child_chunk = SafetyChunk(
                    chunk_id=f"{parent_id}_본문",
                    chunk_type="child",
                    parent_chunk_id=parent_id,
                    doc_name=doc.doc_name,
                    doc_type=doc.doc_type,
                    article_ref=article_ref_full,
                    section_hierarchy=hierarchy,
                    orig_text=article.article_content or parent_text,
                    embed_text=self._build_embed_text(
                        hierarchy, article.article_content or parent_text, "child"
                    ),
                    source_url=doc.source_url,
                    effective_date=doc.effective_date,
                    references_to=json.dumps(
                        self._extract_cross_refs(article.article_content or ""), ensure_ascii=False
                    ),
                )
                chunks.append(child_chunk)

        logger.info(f"청킹 완료: {doc.doc_name} → {len(chunks)}건 (Parent + Child)")
        return chunks

    def chunk_all(self, documents: List[SafetyDocument]) -> List[SafetyChunk]:
        """여러 문서 일괄 청킹 + 교차 참조 역방향 매핑.

        Args:
            documents: SafetyDocument 리스트

        Returns:
            전체 SafetyChunk 리스트
        """
        all_chunks = []
        for doc in documents:
            chunks = self.chunk_document(doc)
            all_chunks.extend(chunks)

        # 교차 참조 역방향 매핑 (referenced_by)
        self._build_reverse_references(all_chunks)

        logger.info(f"전체 청킹 완료: {len(documents)}문서 → {len(all_chunks)}청크")
        return all_chunks

    # ──────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────

    def _chunk_paragraphs(
        self, article: Article, doc: SafetyDocument, parent_id: str, hierarchy: str
    ) -> List[SafetyChunk]:
        """항 단위로 Child 청크 생성. 호/목이 많은 항은 분할."""
        children = []

        for para in article.paragraphs:
            para_ref = f"제{article.article_no}조"
            if para.number:
                para_ref += f"제{para.number}항"

            # 항 텍스트 구성
            para_text = para.content or ""

            # 호/목이 있으면 포함
            if para.sub_items:
                sub_texts = self._flatten_sub_items(para.sub_items)
                full_para_text = para_text + "\n" + "\n".join(sub_texts) if para_text else "\n".join(sub_texts)

                # 호가 많으면 (5개 이상) 호 단위로 분할
                if len(para.sub_items) >= 5:
                    # 항 본문 + 호 분할
                    children.extend(
                        self._split_by_sub_items(article, para, doc, parent_id, hierarchy)
                    )
                    continue
                else:
                    para_text = full_para_text

            child_id = f"{parent_id}_제{para.number}항" if para.number else f"{parent_id}_항"

            child = SafetyChunk(
                chunk_id=child_id,
                chunk_type="child",
                parent_chunk_id=parent_id,
                doc_name=doc.doc_name,
                doc_type=doc.doc_type,
                article_ref=para_ref,
                section_hierarchy=hierarchy,
                orig_text=para_text,
                embed_text=self._build_embed_text(hierarchy, para_text, "child"),
                source_url=doc.source_url,
                effective_date=doc.effective_date,
                references_to=json.dumps(self._extract_cross_refs(para_text), ensure_ascii=False),
            )
            children.append(child)

        return children

    def _split_by_sub_items(
        self, article: Article, para: ArticleItem, doc: SafetyDocument,
        parent_id: str, hierarchy: str,
    ) -> List[SafetyChunk]:
        """호가 많은 항 → 호 단위로 분할."""
        children = []

        # 항 본문 자체도 하나의 Child
        if para.content:
            para_ref = f"제{article.article_no}조제{para.number}항"
            child_id = f"{parent_id}_제{para.number}항_본문"
            child = SafetyChunk(
                chunk_id=child_id,
                chunk_type="child",
                parent_chunk_id=parent_id,
                doc_name=doc.doc_name,
                doc_type=doc.doc_type,
                article_ref=para_ref,
                section_hierarchy=hierarchy,
                orig_text=para.content,
                embed_text=self._build_embed_text(hierarchy, para.content, "child"),
                source_url=doc.source_url,
                effective_date=doc.effective_date,
                references_to=json.dumps(self._extract_cross_refs(para.content), ensure_ascii=False),
            )
            children.append(child)

        # 각 호를 Child로
        for sub in para.sub_items:
            sub_text = sub.content or ""
            if sub.sub_items:
                sub_sub_texts = self._flatten_sub_items(sub.sub_items)
                sub_text += "\n" + "\n".join(sub_sub_texts)

            sub_ref = f"제{article.article_no}조제{para.number}항제{sub.number}호"
            child_id = f"{parent_id}_제{para.number}항제{sub.number}호"

            child = SafetyChunk(
                chunk_id=child_id,
                chunk_type="child",
                parent_chunk_id=parent_id,
                doc_name=doc.doc_name,
                doc_type=doc.doc_type,
                article_ref=sub_ref,
                section_hierarchy=hierarchy,
                orig_text=sub_text,
                embed_text=self._build_embed_text(hierarchy, sub_text, "child"),
                source_url=doc.source_url,
                effective_date=doc.effective_date,
                references_to=json.dumps(self._extract_cross_refs(sub_text), ensure_ascii=False),
            )
            children.append(child)

        return children

    def _flatten_sub_items(self, items: List[ArticleItem], depth: int = 0) -> List[str]:
        """호/목 리스트 → 텍스트 리스트 (재귀).

        API 데이터의 content에 이미 번호(1., 가. 등)가 포함되어 있으므로
        번호를 중복 추가하지 않고 content를 그대로 사용한다.
        """
        texts = []
        for item in items:
            prefix = "  " * depth
            text = f"{prefix}{item.content}" if item.content else ""
            if text:
                texts.append(text)
            if item.sub_items:
                texts.extend(self._flatten_sub_items(item.sub_items, depth + 1))
        return texts

    def _build_parent_text(self, article: Article) -> str:
        """조 전체 텍스트 구성."""
        parts = []

        # 조문 제목
        header = f"제{article.article_no}조"
        if article.article_title:
            header += f"({article.article_title})"
        parts.append(header)

        # 조문 내용 (항이 없는 단문일 때만 추가 — 항이 있으면 중복됨)
        if article.article_content and not article.paragraphs:
            parts.append(article.article_content)

        # 항/호/목
        for para in article.paragraphs:
            # API 데이터의 content에 이미 ①② 등 번호가 포함되어 있으므로 그대로 사용
            para_text = para.content or ""
            if para_text:
                parts.append(para_text)

            if para.sub_items:
                sub_texts = self._flatten_sub_items(para.sub_items, depth=1)
                parts.extend(sub_texts)

        return "\n".join(parts)

    def _build_hierarchy(self, doc_name: str, chapter_map: dict, article: Article) -> str:
        """계층 경로 생성: 「법령명」 > 제N장 > 제N조(제목)."""
        parts = [f"「{doc_name}」"]

        chapter = chapter_map.get(article.article_no, "")
        if chapter:
            parts.append(chapter)

        ref = f"제{article.article_no}조"
        if article.article_title:
            ref += f" {article.article_title}"
        parts.append(ref)

        return " > ".join(parts)

    def _build_embed_text(self, hierarchy: str, text: str, chunk_type: str) -> str:
        """Contextual Retrieval용 임베딩 텍스트.

        [계층 경로]
        원본 텍스트
        """
        return f"[{hierarchy}]\n{text}"

    def _build_chapter_map(self, doc: SafetyDocument) -> dict:
        """조문번호 → 소속 장/절 매핑 구축.

        Note: law.go.kr API의 XML 구조는 편/장/절 내부에 조문을 중첩하지 않는 경우가 많으므로,
        장/절 제목 순서와 조문 번호 순서로 추정한다.
        """
        chapter_map = {}

        if not doc.chapters:
            return chapter_map

        # 장/절을 순서대로 정렬하고, 조문 번호 범위를 추정
        # 간단한 구현: 각 조문에 가장 가까운 이전 장/절을 할당
        chapter_titles = []
        for ch in doc.chapters:
            chapter_titles.append(ch.get("title", ""))

        # 조문 번호 순서대로 장을 할당
        if chapter_titles and doc.articles:
            # 장 수와 조문 수 비율로 할당 (단순 추정)
            articles_per_chapter = max(1, len(doc.articles) // max(1, len(chapter_titles)))
            for i, article in enumerate(doc.articles):
                chapter_idx = min(i // articles_per_chapter, len(chapter_titles) - 1)
                if article.article_no:
                    chapter_map[article.article_no] = chapter_titles[chapter_idx]

        return chapter_map

    def _extract_cross_refs(self, text: str) -> List[str]:
        """텍스트에서 교차 참조 조문 추출.

        "제5조", "제10조제2항" 등을 감지.
        """
        refs = []
        for match in CROSS_REF_PATTERN.finditer(text):
            ref = f"제{match.group(1)}조"
            if match.group(2):
                ref += f"의{match.group(2)}"
            if match.group(3):
                ref += f"제{match.group(3)}항"
            refs.append(ref)
        return list(set(refs))

    def _build_reverse_references(self, chunks: List[SafetyChunk]):
        """교차 참조 역방향 매핑 (referenced_by) 구축.

        A가 B를 참조하면 → B의 referenced_by에 A를 추가.
        """
        # 각 Parent의 references_to를 파싱하여 역방향 매핑
        reverse_map = {}  # target_article_ref → [source_chunk_ids]

        for chunk in chunks:
            if chunk.chunk_type != "parent":
                continue
            refs = json.loads(chunk.references_to)
            for ref in refs:
                if ref not in reverse_map:
                    reverse_map[ref] = []
                reverse_map[ref].append(chunk.chunk_id)

        # 역방향 매핑을 Parent 청크에 기록
        for chunk in chunks:
            if chunk.chunk_type != "parent":
                continue
            # 이 조문을 참조하는 다른 청크들
            article_ref_short = f"제{chunk.article_ref.split('조')[0].replace('제', '')}조" if "조" in chunk.article_ref else ""
            if article_ref_short and article_ref_short in reverse_map:
                # 자기 자신은 제외
                referenced_by = [cid for cid in reverse_map[article_ref_short] if cid != chunk.chunk_id]
                chunk.referenced_by = json.dumps(referenced_by, ensure_ascii=False)
