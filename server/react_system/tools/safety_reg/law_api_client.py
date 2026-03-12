"""국가법령정보센터 Open API 클라이언트.

법령 18건(법령 15건 + 행정규칙 3건)을 자동 수집한다.
- Step 1: lawSearch.do → 법령일련번호(MST) 획득
- Step 2: lawService.do → 조/항/호/목 구조화된 XML 수신

폐쇄망 대응: API 결과를 JSON으로 저장 → JSON에서 로드.
"""

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from xml.etree import ElementTree as ET

import aiohttp

from react_system.tools.safety_reg.constants import LAW_LIST

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data" / "laws"


@dataclass
class ArticleItem:
    """항/호/목 단위 구조."""

    number: str = ""  # 항번호, 호번호, 목번호
    content: str = ""  # 내용
    sub_items: List["ArticleItem"] = field(default_factory=list)  # 하위 호/목


@dataclass
class Article:
    """조(Article) 단위 구조."""

    article_no: str = ""  # 조문번호 (예: "13")
    article_title: str = ""  # 조문제목 (예: "안전보건총괄책임자")
    article_content: str = ""  # 조문내용 (항이 없는 단문 조문)
    paragraphs: List[ArticleItem] = field(default_factory=list)  # 항 목록


@dataclass
class SafetyDocument:
    """법령/행정규칙 전체 문서 구조."""

    doc_name: str = ""  # 법령명
    doc_type: str = ""  # "법령" | "행정규칙"
    mst: str = ""  # 법령일련번호
    proclamation_date: str = ""  # 공포일자
    effective_date: str = ""  # 시행일자
    law_id: str = ""  # 법령ID (법제처)
    chapters: List[dict] = field(default_factory=list)  # [{title, articles}]
    articles: List[Article] = field(default_factory=list)  # 전체 조문 (flat)
    source_url: str = ""  # law.go.kr URL


class LawApiClient:
    """국가법령정보센터 Open API 클라이언트."""

    BASE_SEARCH = "http://www.law.go.kr/DRF/lawSearch.do"
    BASE_SERVICE = "http://www.law.go.kr/DRF/lawService.do"
    REQUEST_DELAY = 0.5  # 요청 간 0.5초 간격

    def __init__(self, oc: str = None):
        """
        Args:
            oc: Open API 인증키 (OC). 환경변수 LAW_API_OC에서도 읽음.
        """
        self.oc = oc or os.getenv("LAW_API_OC", "")

    async def search_law(self, query: str, target: str = "law") -> List[dict]:
        """법령명 검색 → MST(법령일련번호) 획득.

        Args:
            query: 법령명 (공백 제거된 형태)
            target: "law" (법령) | "admrul" (행정규칙)

        Returns:
            [{"mst": "...", "법령명한글": "...", "시행일자": "...", ...}, ...]
        """
        params = {
            "OC": self.oc,
            "target": target,
            "type": "XML",
            "query": query,
            "display": "5",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_SEARCH, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    text = await resp.text()
                    return self._parse_search_result(text)
        except Exception as e:
            logger.error(f"법령 검색 실패 [{query}]: {e}")
            return []

    async def get_law_full(self, mst: str, doc_name: str = "", doc_type: str = "법령") -> Optional[SafetyDocument]:
        """본문 전체 조회 → SafetyDocument 변환.

        Args:
            mst: 법령일련번호
            doc_name: 법령명
            doc_type: 문서 유형

        Returns:
            SafetyDocument 또는 None (실패 시)
        """
        target = "admrul" if doc_type == "행정규칙" else "law"
        params = {
            "OC": self.oc,
            "target": target,
            "type": "XML",
        }
        # 행정규칙은 ID 파라미터, 법령은 MST 파라미터 사용
        if target == "admrul":
            params["ID"] = mst
        else:
            params["MST"] = mst
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_SERVICE, params=params, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    text = await resp.text()
                    return self._parse_law_xml(text, doc_name, doc_type, mst)
        except Exception as e:
            logger.error(f"법령 본문 조회 실패 [MST={mst}]: {e}")
            return None

    async def collect_all(self, law_list: List[tuple] = None) -> List[SafetyDocument]:
        """전체 법령 수집 → JSON 저장.

        Args:
            law_list: [(검색명, target, doc_type), ...]. None이면 LAW_LIST 사용.

        Returns:
            수집된 SafetyDocument 리스트
        """
        if law_list is None:
            law_list = LAW_LIST

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        documents = []

        for query, target, doc_type in law_list:
            logger.info(f"수집 중: {query} (target={target})")

            # Step 1: 검색
            results = await self.search_law(query, target)
            if not results:
                logger.warning(f"검색 결과 없음: {query}")
                await asyncio.sleep(self.REQUEST_DELAY)
                continue

            mst = results[0].get("mst", "")
            if not mst:
                logger.warning(f"MST 없음: {query}")
                await asyncio.sleep(self.REQUEST_DELAY)
                continue

            await asyncio.sleep(self.REQUEST_DELAY)

            # Step 2: 본문 조회
            doc = await self.get_law_full(mst, query, doc_type)
            if doc:
                documents.append(doc)
                # JSON 저장
                self._save_to_json(doc)
                logger.info(f"수집 완료: {doc.doc_name} (조문 {len(doc.articles)}건)")
            else:
                logger.warning(f"본문 조회 실패: {query}")

            await asyncio.sleep(self.REQUEST_DELAY)

        logger.info(f"전체 수집 완료: {len(documents)}건 / {len(law_list)}건")
        return documents

    def load_from_json(self, path: str = None) -> List[SafetyDocument]:
        """폐쇄망: JSON 파일에서 로드.

        Args:
            path: JSON 디렉토리 경로. None이면 기본 data/laws/ 사용.

        Returns:
            SafetyDocument 리스트
        """
        load_dir = Path(path) if path else DATA_DIR
        documents = []

        if not load_dir.exists():
            logger.warning(f"JSON 디렉토리 없음: {load_dir}")
            return documents

        for json_file in sorted(load_dir.glob("*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                doc = self._dict_to_document(data)
                documents.append(doc)
                logger.info(f"JSON 로드: {doc.doc_name} (조문 {len(doc.articles)}건)")
            except Exception as e:
                logger.error(f"JSON 로드 실패 [{json_file}]: {e}")

        logger.info(f"JSON 로드 완료: {len(documents)}건")
        return documents

    # ──────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────

    def _parse_search_result(self, xml_text: str) -> List[dict]:
        """검색 결과 XML 파싱."""
        results = []
        try:
            root = ET.fromstring(xml_text)
            # Note: Element.__bool__은 자식 없으면 False → or 사용 금지, is not None 사용
            items = root.findall(".//law")
            if not items:
                items = root.findall(".//admrul")
            for item in items:
                mst_el = item.find("법령일련번호")
                if mst_el is None:
                    mst_el = item.find("행정규칙일련번호")
                name_el = item.find("법령명한글")
                if name_el is None:
                    name_el = item.find("행정규칙명")
                eff_el = item.find("시행일자")
                if mst_el is not None and mst_el.text:
                    results.append({
                        "mst": mst_el.text.strip(),
                        "법령명한글": name_el.text.strip() if name_el is not None and name_el.text else "",
                        "시행일자": eff_el.text.strip() if eff_el is not None and eff_el.text else "",
                    })
        except ET.ParseError as e:
            logger.error(f"검색 결과 XML 파싱 실패: {e}")
        return results

    def _parse_law_xml(self, xml_text: str, doc_name: str, doc_type: str, mst: str) -> Optional[SafetyDocument]:
        """법령 본문 XML 파싱 → SafetyDocument."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.error(f"본문 XML 파싱 실패: {e}")
            return None

        doc = SafetyDocument(
            doc_name=doc_name,
            doc_type=doc_type,
            mst=mst,
        )

        # 기본 정보 — 법령: <기본정보>, 행정규칙: <행정규칙기본정보>
        info = root.find("기본정보")
        if info is None:
            info = root.find("행정규칙기본정보")
        if info is None:
            info = root

        # 법령명 — 법령: <법령명_한글>/<법령명한글>, 행정규칙: <행정규칙명>
        name_el = info.find("법령명_한글")
        if name_el is None:
            name_el = info.find("법령명한글")
        if name_el is None:
            name_el = info.find("행정규칙명")
        if name_el is not None and name_el.text:
            doc.doc_name = name_el.text.strip()

        eff_el = info.find("시행일자")
        if eff_el is not None and eff_el.text:
            doc.effective_date = eff_el.text.strip()

        proc_el = info.find("공포일자")
        if proc_el is None:
            proc_el = info.find("발령일자")
        if proc_el is not None and proc_el.text:
            doc.proclamation_date = proc_el.text.strip()

        law_id_el = info.find("법령ID")
        if law_id_el is None:
            law_id_el = info.find("행정규칙ID")
        if law_id_el is not None and law_id_el.text:
            doc.law_id = law_id_el.text.strip()

        # law.go.kr URL
        if doc_type == "행정규칙":
            doc.source_url = f"https://www.law.go.kr/행정규칙/{doc.doc_name}"
        else:
            doc.source_url = f"https://www.law.go.kr/법령/{doc.doc_name}"

        # 조문 파싱 — 법령: <조문단위> 구조, 행정규칙: flat <조문내용> 태그
        for article_el in root.iter("조문단위"):
            article = self._parse_article(article_el)
            if article:
                doc.articles.append(article)

        # 행정규칙: <조문단위>가 없으면 flat <조문내용> 태그에서 파싱
        if not doc.articles:
            doc.articles = self._parse_flat_articles(root)

        # 편/장/절 구조 파싱
        for chapter_el in root.iter("편"):
            title = ""
            title_el = chapter_el.find("편제목") or chapter_el.find("장제목")
            if title_el is not None and title_el.text:
                title = title_el.text.strip()
            if title:
                doc.chapters.append({"title": title, "type": "편"})

        for chapter_el in root.iter("장"):
            title_el = chapter_el.find("장제목")
            if title_el is not None and title_el.text:
                doc.chapters.append({"title": title_el.text.strip(), "type": "장"})

        for section_el in root.iter("절"):
            title_el = section_el.find("절제목")
            if title_el is not None and title_el.text:
                doc.chapters.append({"title": title_el.text.strip(), "type": "절"})

        return doc

    def _parse_article(self, article_el) -> Optional[Article]:
        """<조문단위> 파싱 → Article."""
        article = Article()

        no_el = article_el.find("조문번호")
        if no_el is not None and no_el.text:
            article.article_no = no_el.text.strip()

        title_el = article_el.find("조문제목")
        if title_el is not None and title_el.text:
            article.article_title = title_el.text.strip()

        content_el = article_el.find("조문내용")
        if content_el is not None and content_el.text:
            article.article_content = content_el.text.strip()

        # 항 파싱
        for para_el in article_el.findall("항"):
            para = self._parse_item(para_el, "항")
            if para:
                article.paragraphs.append(para)

        if not article.article_no and not article.article_content:
            return None

        return article

    def _parse_item(self, el, level: str) -> Optional[ArticleItem]:
        """항/호/목 재귀 파싱."""
        item = ArticleItem()

        no_el = el.find(f"{level}번호")
        if no_el is not None and no_el.text:
            item.number = no_el.text.strip()

        content_el = el.find(f"{level}내용")
        if content_el is not None and content_el.text:
            item.content = content_el.text.strip()

        # 하위 레벨 파싱
        sub_level_map = {"항": "호", "호": "목"}
        sub_level = sub_level_map.get(level)
        if sub_level:
            for sub_el in el.findall(sub_level):
                sub_item = self._parse_item(sub_el, sub_level)
                if sub_item:
                    item.sub_items.append(sub_item)

        if not item.content and not item.number:
            return None

        return item

    def _parse_flat_articles(self, root) -> List[Article]:
        """행정규칙 flat <조문내용> 태그 파싱.

        행정규칙 XML은 <조문단위> 없이 최상위에 <조문내용> 태그가 나열됨.
        각 <조문내용>에 "제N조(제목) 본문" 형태로 텍스트가 포함됨.
        장/절 제목도 <조문내용>으로 들어옴 (예: "제1장 총칙").
        """
        articles = []
        article_pattern = re.compile(r'^제(\d+)조(?:의(\d+))?\s*(?:\(([^)]+)\))?\s*(.*)', re.DOTALL)
        chapter_pattern = re.compile(r'^제\d+장\s+.+$')

        for content_el in root.findall("조문내용"):
            if content_el.text is None:
                continue
            text = content_el.text.strip()
            if not text:
                continue

            # 장/절 제목은 건너뜀
            if chapter_pattern.match(text):
                continue

            m = article_pattern.match(text)
            if m:
                article_no = m.group(1)
                sub_no = m.group(2)  # 조의2 등
                title = m.group(3) or ""
                content = m.group(4).strip()

                if sub_no:
                    article_no = f"{article_no}의{sub_no}"

                article = Article(
                    article_no=article_no,
                    article_title=title,
                    article_content=content,
                )
                articles.append(article)
            else:
                # 제N조 형태가 아닌 텍스트 (부칙, 기타) — 내용이 있으면 추가
                if len(text) > 10:
                    article = Article(
                        article_no="",
                        article_title="",
                        article_content=text,
                    )
                    articles.append(article)

        return articles

    def _save_to_json(self, doc: SafetyDocument):
        """SafetyDocument → JSON 파일 저장."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        filename = re.sub(r'[^\w가-힣]', '_', doc.doc_name) + ".json"
        filepath = DATA_DIR / filename

        data = self._document_to_dict(doc)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _document_to_dict(self, doc: SafetyDocument) -> dict:
        """SafetyDocument → dict (JSON 직렬화용)."""

        def article_item_to_dict(item: ArticleItem) -> dict:
            return {
                "number": item.number,
                "content": item.content,
                "sub_items": [article_item_to_dict(si) for si in item.sub_items],
            }

        def article_to_dict(article: Article) -> dict:
            return {
                "article_no": article.article_no,
                "article_title": article.article_title,
                "article_content": article.article_content,
                "paragraphs": [article_item_to_dict(p) for p in article.paragraphs],
            }

        return {
            "doc_name": doc.doc_name,
            "doc_type": doc.doc_type,
            "mst": doc.mst,
            "proclamation_date": doc.proclamation_date,
            "effective_date": doc.effective_date,
            "law_id": doc.law_id,
            "chapters": doc.chapters,
            "articles": [article_to_dict(a) for a in doc.articles],
            "source_url": doc.source_url,
        }

    async def check_updates(self, law_list: List[tuple] = None) -> List[dict]:
        """기존 JSON과 API 최신 데이터 비교 → 변경된 법령 목록 반환.

        Returns:
            [{"name": "산업안전보건법", "target": "law", "doc_type": "법령",
              "old_effective_date": "20240101", "new_effective_date": "20250701",
              "mst": "..."}, ...]
        """
        if law_list is None:
            law_list = LAW_LIST

        updates = []
        for name, target, doc_type in law_list:
            # 기존 JSON에서 시행일 읽기
            json_path = DATA_DIR / (re.sub(r'[^\w가-힣]', '_', name) + ".json")
            old_date = ""
            if json_path.exists():
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        old_data = json.load(f)
                        old_date = old_data.get("effective_date", "")
                except Exception:
                    pass

            # API에서 최신 시행일 조회
            try:
                results = await self.search_law(name, target=target)
                if results:
                    new_date = results[0].get("시행일자", "")
                    if new_date and new_date != old_date:
                        updates.append({
                            "name": name,
                            "target": target,
                            "doc_type": doc_type,
                            "old_effective_date": old_date,
                            "new_effective_date": new_date,
                            "mst": results[0].get("mst", ""),
                        })
                        logger.info(f"법령 변경 감지: {name} ({old_date} → {new_date})")
            except Exception as e:
                logger.warning(f"법령 업데이트 확인 실패: {name} — {e}")

            await asyncio.sleep(self.REQUEST_DELAY)

        logger.info(f"법령 업데이트 확인 완료: {len(updates)}건 변경")
        return updates

    def _dict_to_document(self, data: dict) -> SafetyDocument:
        """dict → SafetyDocument (JSON 역직렬화)."""

        def dict_to_article_item(d: dict) -> ArticleItem:
            return ArticleItem(
                number=d.get("number", ""),
                content=d.get("content", ""),
                sub_items=[dict_to_article_item(si) for si in d.get("sub_items", [])],
            )

        def dict_to_article(d: dict) -> Article:
            return Article(
                article_no=d.get("article_no", ""),
                article_title=d.get("article_title", ""),
                article_content=d.get("article_content", ""),
                paragraphs=[dict_to_article_item(p) for p in d.get("paragraphs", [])],
            )

        return SafetyDocument(
            doc_name=data.get("doc_name", ""),
            doc_type=data.get("doc_type", ""),
            mst=data.get("mst", ""),
            proclamation_date=data.get("proclamation_date", ""),
            effective_date=data.get("effective_date", ""),
            law_id=data.get("law_id", ""),
            chapters=data.get("chapters", []),
            articles=[dict_to_article(a) for a in data.get("articles", [])],
            source_url=data.get("source_url", ""),
        )
