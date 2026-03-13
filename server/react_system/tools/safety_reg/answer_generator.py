"""LLM 답변 생성 — 토큰 제어 포함.

10,000 토큰 기준 분기:
- ≤10K: Parent들을 그대로 LLM에 전달
- >10K: LLM 검증으로 필요한 Parent만 선별 후 답변 생성
"""

import logging
import re
from typing import List

from react_system.tools.safety_reg.constants import TOKEN_THRESHOLD
from react_system.tools.safety_reg.prompts import (
    DETAIL_INSTRUCTIONS,
    SAFETY_REG_ANSWER_TEMPLATE,
    SAFETY_REG_SYSTEM_PROMPT,
    SAFETY_REG_VALIDATION_PROMPT,
)
from react_system.tools.safety_reg.search_client import SearchHit

logger = logging.getLogger(__name__)

# 토큰 추정: 한글 1글자 ≈ 2~3 토큰, 영문 1단어 ≈ 1 토큰
# 간이 추정: 문자 수 * 1.5 (한글 중심)
CHARS_PER_TOKEN = 1.5


def _count_tokens(text: str) -> int:
    """간이 토큰 수 추정."""
    return int(len(text) * CHARS_PER_TOKEN)


def _build_context(parents: List[SearchHit]) -> str:
    """Parent 청크들을 컨텍스트 문자열로 결합."""
    parts = []
    for i, p in enumerate(parents, 1):
        header = f"### [{i}] {p.section_hierarchy}"
        parts.append(f"{header}\n{p.orig_text}")
    return "\n\n".join(parts)


def _build_numbered_list(parents: List[SearchHit]) -> str:
    """LLM 검증용 번호 매긴 목록."""
    parts = []
    for i, p in enumerate(parents, 1):
        excerpt = p.orig_text[:500] + "..." if len(p.orig_text) > 500 else p.orig_text
        parts.append(f"[{i}] {p.section_hierarchy}\n{excerpt}")
    return "\n\n".join(parts)


def _build_source_lookup(sources: List[dict]) -> dict:
    """sources를 (doc_name, article_ref) → source dict로 매핑."""
    lookup = {}
    for src in sources:
        key = (src["doc_name"], src["article_ref"])
        if key not in lookup:
            lookup[key] = src
    return lookup


def _make_inline_dialog_id(doc_name: str, article_ref: str) -> str:
    """인라인 dialog ID 생성 — 동일 조문은 같은 ID."""
    import hashlib
    key = f"{doc_name}_{article_ref}"
    return f"sr-inline-{hashlib.md5(key.encode()).hexdigest()[:8]}"


def _render_html(answer: str, sources: List[dict]) -> str:
    """답변 + 출처를 구조화된 HTML로 렌더링."""
    html_parts = ['<div class="safety-reg-answer" style="font-size:14px;line-height:1.8;color:#333;">']

    # source lookup 구성
    source_lookup = _build_source_lookup(sources) if sources else None

    # 답변 본문 — 마크다운 → HTML 변환 (인라인 조문 클릭 포함)
    dialog_collector = []
    html_parts.append('<div class="answer-content">')
    html_parts.append(_markdown_to_html(answer, source_lookup, dialog_collector))
    html_parts.append('</div>')

    # 인라인 조문 dialog 일괄 삽입 (중복 ID 제거)
    seen_dialog_ids = set()
    for dlg in dialog_collector:
        if dlg["id"] not in seen_dialog_ids:
            seen_dialog_ids.add(dlg["id"])
            escaped_text = dlg["full_text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_parts.append(
                f'<dialog id="{dlg["id"]}" class="sr-modal">'
                f'<div class="sr-modal-header">'
                f'<p class="sr-modal-title">「{dlg["doc_name"]}」 {dlg["article_ref"]}</p>'
                f'<button class="sr-modal-close" onclick="this.closest(\'dialog\').close()">&times;</button>'
                f'</div>'
                f'<div class="sr-modal-body">{escaped_text}</div>'
                f'</dialog>'
            )

    # 출처 카드
    if sources:
        html_parts.append(_render_sources_card(sources))

    html_parts.append('</div>')
    return '\n'.join(html_parts)


def _markdown_to_html(text: str, source_lookup: dict = None, dialog_collector: list = None) -> str:
    """마크다운 → HTML 변환 (법령 답변 특화)."""
    lines = text.split('\n')
    html_lines = []
    in_list = False
    in_ol = False

    def fmt(t):
        return _inline_format(t, source_lookup, dialog_collector)

    for line in lines:
        stripped = line.strip()

        # 헤딩
        if stripped.startswith('### '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            if in_ol:
                html_lines.append('</ol>')
                in_ol = False
            html_lines.append(f'<h4 style="margin:16px 0 8px;color:#1a5276;">{fmt(stripped[4:])}</h4>')
            continue
        if stripped.startswith('## '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            if in_ol:
                html_lines.append('</ol>')
                in_ol = False
            html_lines.append(f'<h3 style="margin:20px 0 10px;color:#1a5276;">{fmt(stripped[3:])}</h3>')
            continue

        # 번호 목록: "1. "
        ol_match = re.match(r'^(\d+)\.\s+(.+)', stripped)
        if ol_match:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            if not in_ol:
                html_lines.append('<ol style="margin:8px 0;padding-left:24px;">')
                in_ol = True
            html_lines.append(f'<li>{fmt(ol_match.group(2))}</li>')
            continue

        # 불렛 목록: "- " 또는 "* "
        if stripped.startswith('- ') or stripped.startswith('* '):
            if in_ol:
                html_lines.append('</ol>')
                in_ol = False
            if not in_list:
                html_lines.append('<ul style="margin:8px 0;padding-left:24px;">')
                in_list = True
            html_lines.append(f'<li>{fmt(stripped[2:])}</li>')
            continue

        # 빈 줄
        if not stripped:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            if in_ol:
                html_lines.append('</ol>')
                in_ol = False
            continue

        # 일반 텍스트
        if in_list:
            html_lines.append('</ul>')
            in_list = False
        if in_ol:
            html_lines.append('</ol>')
            in_ol = False
        html_lines.append(f'<p style="margin:6px 0;">{fmt(stripped)}</p>')

    if in_list:
        html_lines.append('</ul>')
    if in_ol:
        html_lines.append('</ol>')
    return '\n'.join(html_lines)


def _inline_format(text: str, source_lookup: dict = None, dialog_collector: list = None) -> str:
    """인라인 마크다운 포맷팅 — bold, 법령명, 조문 강조 + 클릭 팝업."""
    # **bold** → <strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    # 「법령명」 제N조 패턴 — source_lookup에 있으면 클릭 가능 링크
    if source_lookup:
        def _replace_law_ref(m):
            law_name = m.group(1)
            article = m.group(2)
            # source_lookup에서 매칭 (doc_name에 law_name 포함 + article_ref에 article 포함)
            matched_src = None
            for (dn, ar), src in source_lookup.items():
                if law_name in dn and article in ar:
                    matched_src = src
                    break
            if matched_src:
                dialog_id = _make_inline_dialog_id(matched_src["doc_name"], matched_src["article_ref"])
                if dialog_collector is not None:
                    dialog_collector.append({
                        "id": dialog_id,
                        "doc_name": matched_src["doc_name"],
                        "article_ref": matched_src["article_ref"],
                        "full_text": matched_src.get("full_text", matched_src.get("excerpt", "")),
                        "source_url": matched_src.get("source_url", ""),
                    })
                return (
                    f'<span class="sr-inline-ref" '
                    f"onclick=\"document.getElementById('{dialog_id}').showModal()\">"
                    f'「{law_name}」 {article}</span>'
                )
            # 매칭 안 되면 기존 스타일링만
            return (
                f'<strong style="color:#1a5276;">「{law_name}」</strong> '
                f'<span style="color:#2c3e50;font-weight:500;">{article}</span>'
            )

        text = re.sub(
            r'「(.+?)」\s*(제\d+조(?:의\d+)?(?:\([^)]+\))?)',
            _replace_law_ref,
            text,
        )
    else:
        # source_lookup 없으면 기존 스타일링
        text = re.sub(r'「(.+?)」', r'<strong style="color:#1a5276;">「\1」</strong>', text)

    # 나머지 제N조 강조 (이미 처리되지 않은 것)
    text = re.sub(
        r'(?<!">)(제\d+조(?:의\d+)?(?:\([^)]+\))?(?:제\d+항)?(?:제\d+호)?)',
        r'<span style="color:#2c3e50;font-weight:500;">\1</span>',
        text,
    )
    return text


def _render_sources_card(sources: List[dict]) -> str:
    """출처를 details/summary 접기 + dialog 팝업으로 렌더링."""
    parts = []

    # CSS 스타일 (<style> 블록은 MarkdownViewer에서 보존됨)
    parts.append(
        "<style>\n"
        ".sr-sources { margin-top:20px; padding:16px; background:#f8f9fa;\n"
        "  border-radius:8px; border:1px solid #e9ecef; }\n"
        ".sr-sources-title { font-size:13px; font-weight:600;\n"
        "  color:#495057; margin:0 0 12px; }\n"
        ".sr-card { margin-bottom:8px; background:#fff;\n"
        "  border-radius:6px; border-left:3px solid #3498db; overflow:hidden; }\n"
        ".sr-card details { padding:0; }\n"
        ".sr-card summary { padding:10px 12px; cursor:pointer;\n"
        "  list-style:none; display:flex;\n"
        "  justify-content:space-between; align-items:center; }\n"
        ".sr-card summary::-webkit-details-marker { display:none; }\n"
        ".sr-card summary::after { content:'\\25BC'; font-size:10px;\n"
        "  color:#adb5bd; transition:transform 0.2s; }\n"
        ".sr-card details[open] summary::after { transform:rotate(180deg); }\n"
        ".sr-card-name { font-size:13px; font-weight:500; color:#2c3e50;\n"
        "  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;\n"
        "  max-width:calc(100% - 24px); }\n"
        ".sr-card-excerpt { padding:8px 12px; font-size:12px;\n"
        "  color:#6c757d; line-height:1.6;\n"
        "  display:-webkit-box; -webkit-line-clamp:3;\n"
        "  -webkit-box-orient:vertical; overflow:hidden;\n"
        "  white-space:pre-wrap;\n"
        "  border-top:1px solid #f0f0f0; }\n"
        ".sr-card-actions { padding:8px 12px 12px;\n"
        "  display:flex; gap:8px;\n"
        "  border-top:1px solid #f0f0f0; }\n"
        ".sr-btn { font-size:12px; padding:4px 10px; border-radius:4px;\n"
        "  border:1px solid #dee2e6; background:#fff;\n"
        "  color:#495057; cursor:pointer; text-decoration:none; }\n"
        ".sr-btn:hover { background:#e9ecef; }\n"
        ".sr-btn-primary { border-color:#3498db; color:#2980b9; }\n"
        ".sr-btn-primary:hover { background:#ebf5fb; }\n"
        ".sr-modal { border:none; border-radius:12px; padding:0;\n"
        "  max-width:680px; width:90vw; max-height:80vh;\n"
        "  box-shadow:0 8px 32px rgba(0,0,0,0.18); }\n"
        ".sr-modal::backdrop { background:rgba(0,0,0,0.4); }\n"
        ".sr-modal-header { display:flex;\n"
        "  justify-content:space-between; align-items:center;\n"
        "  padding:16px 20px; border-bottom:1px solid #e9ecef;\n"
        "  position:sticky; top:0; background:#fff;\n"
        "  border-radius:12px 12px 0 0; z-index:1; }\n"
        ".sr-modal-title { font-size:15px; font-weight:600;\n"
        "  color:#1a5276; margin:0; }\n"
        ".sr-modal-close { background:none; border:none; font-size:20px;\n"
        "  color:#adb5bd; cursor:pointer;\n"
        "  padding:4px 8px; border-radius:4px; }\n"
        ".sr-modal-close:hover { background:#f8f9fa; color:#495057; }\n"
        ".sr-modal-body { padding:20px; overflow-y:auto;\n"
        "  max-height:calc(80vh - 60px); font-size:13px;\n"
        "  line-height:1.8; color:#333; white-space:pre-wrap; }\n"
        ".sr-inline-ref { color:#2980b9; cursor:pointer;\n"
        "  text-decoration:underline dotted; font-weight:500; }\n"
        ".sr-inline-ref:hover { color:#1a5276;\n"
        "  text-decoration:underline solid; }\n"
        "</style>"
    )

    parts.append('<div class="sr-sources">')
    parts.append('<p class="sr-sources-title">참조 법령</p>')

    for i, src in enumerate(sources):
        full_text = src.get("full_text", src.get("excerpt", ""))
        excerpt = src.get("excerpt", "")
        modal_id = f"sr-modal-{i}"

        # 원문 보기 링크
        link_html = ""
        if src.get("source_url"):
            link_html = (
                f'<a href="{src["source_url"]}" target="_blank" rel="noopener" '
                f'class="sr-btn sr-btn-primary">법제처 원문 ↗</a>'
            )

        parts.append('<div class="sr-card">')
        parts.append('<details>')
        parts.append(
            '<summary>'
            f'<span class="sr-card-name">「{src["doc_name"]}」 {src["article_ref"]}</span>'
            '</summary>'
        )
        # 접힌 내용: 3~4줄 미리보기 + 버튼
        parts.append(f'<div class="sr-card-excerpt">{excerpt}</div>')
        parts.append('<div class="sr-card-actions">')
        parts.append(
            f'<button class="sr-btn sr-btn-primary" '
            f"onclick=\"document.getElementById('{modal_id}').showModal()\">"
            '전체 원문 보기</button>'
        )
        if link_html:
            parts.append(link_html)
        parts.append('</div>')
        parts.append('</details>')
        parts.append('</div>')

        # dialog 팝업
        escaped_text = full_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        parts.append(
            f'<dialog id="{modal_id}" class="sr-modal">'
            f'<div class="sr-modal-header">'
            f'<p class="sr-modal-title">「{src["doc_name"]}」 {src["article_ref"]}</p>'
            f'<button class="sr-modal-close" onclick="this.closest(\'dialog\').close()">&times;</button>'
            f'</div>'
            f'<div class="sr-modal-body">{escaped_text}</div>'
            f'</dialog>'
        )

    parts.append('</div>')
    return '\n'.join(parts)


async def generate_answer(
    query: str,
    parents: List[SearchHit],
    children: List[SearchHit],
    sources: List[dict],
    detail_level: str = "standard",
    llm_fn=None,
) -> dict:
    """LLM 답변 생성 (토큰 기준 분기).

    Args:
        query: 사용자 질문
        parents: Parent 청크 리스트
        children: Child 청크 리스트 (Parent 없을 때 fallback)
        sources: 출처 목록
        detail_level: "brief" | "standard" | "detailed"
        llm_fn: async (system_prompt, user_prompt) -> str LLM 호출 함수

    Returns:
        {
            "html_content": "구조화된 HTML 답변",
            "text_summary": "LLM 후속 컨텍스트용 요약",
            "sources": [출처 목록],
        }
    """
    if not llm_fn:
        logger.error("LLM 함수가 제공되지 않았습니다.")
        return {
            "html_content": "<p>답변 생성에 실패했습니다. LLM 설정을 확인해주세요.</p>",
            "text_summary": "답변 생성 실패",
            "sources": sources,
        }

    # Parent가 없으면 Children을 Parent 대용으로 사용
    context_hits = parents if parents else children
    if not context_hits:
        return {
            "html_content": "<p>검색 결과가 없어 답변을 생성할 수 없습니다.</p>",
            "text_summary": "검색 결과 없음",
            "sources": [],
        }

    # 1. 토큰 계산
    total_tokens = sum(_count_tokens(p.orig_text) for p in context_hits)
    logger.info(f"컨텍스트 토큰: {total_tokens} (Parent {len(context_hits)}건)")

    detail_instruction = DETAIL_INSTRUCTIONS.get(detail_level, DETAIL_INSTRUCTIONS["standard"])

    if total_tokens <= TOKEN_THRESHOLD:
        # 10K 이하 → 바로 답변 생성
        context = _build_context(context_hits)
        user_prompt = SAFETY_REG_ANSWER_TEMPLATE.format(
            context=context, query=query, detail_instruction=detail_instruction
        )
        answer = await llm_fn(SAFETY_REG_SYSTEM_PROMPT, user_prompt)
    else:
        # 10K 초과 → LLM 검증으로 필요한 Parent만 선별
        logger.info(f"토큰 초과 ({total_tokens} > {TOKEN_THRESHOLD}), LLM 검증 실행")
        numbered_list = _build_numbered_list(context_hits)
        validation_prompt = SAFETY_REG_VALIDATION_PROMPT.format(
            query=query, numbered_parent_list=numbered_list
        )

        validation_result = await llm_fn(
            "당신은 법령 문서 분석 전문가입니다. 질문에 관련된 조문만 선별하세요.",
            validation_prompt,
        )

        # 선별된 번호 파싱
        selected_indices = _parse_selection(validation_result, len(context_hits))
        if selected_indices:
            filtered_hits = [context_hits[i] for i in selected_indices]
            logger.info(f"LLM 검증: {len(context_hits)}건 → {len(filtered_hits)}건 선별")
        else:
            # 파싱 실패 시 상위 5개만 사용
            filtered_hits = context_hits[:5]
            logger.warning("LLM 검증 파싱 실패, 상위 5건 사용")

        context = _build_context(filtered_hits)
        user_prompt = SAFETY_REG_ANSWER_TEMPLATE.format(
            context=context, query=query, detail_instruction=detail_instruction
        )
        answer = await llm_fn(SAFETY_REG_SYSTEM_PROMPT, user_prompt)

        # 선별된 Parent 기준으로 출처 업데이트
        sources = _build_filtered_sources(filtered_hits)

    # HTML 렌더링
    html_content = _render_html(answer, sources)

    # 텍스트 요약 (LLM 후속 컨텍스트용 — 답변 내용이 아닌 주제 요약)
    source_names = ", ".join(dict.fromkeys(f"「{s['doc_name']}」" for s in sources[:5]))
    text_summary = (
        f"'{query}'에 대해 {source_names} 등을 근거로 답변을 화면에 표시했습니다. "
        f"총 {len(sources)}건의 출처를 포함합니다."
    )

    return {
        "html_content": html_content,
        "text_summary": text_summary,
        "sources": sources,
    }


def _parse_selection(text: str, max_idx: int) -> List[int]:
    """LLM 검증 결과에서 선택된 번호 파싱.

    "1, 3, 5" 또는 "1,3,5" → [0, 2, 4] (0-indexed)
    """
    numbers = re.findall(r'\d+', text)
    indices = []
    for n in numbers:
        idx = int(n) - 1  # 1-indexed → 0-indexed
        if 0 <= idx < max_idx:
            indices.append(idx)
    return sorted(set(indices))


def _build_filtered_sources(hits: List[SearchHit]) -> List[dict]:
    """필터링된 Parent에서 출처 목록 생성."""
    seen = set()
    sources = []
    for hit in hits:
        key = f"{hit.doc_name}_{hit.article_ref}"
        if key in seen:
            continue
        seen.add(key)
        sources.append({
            "doc_name": hit.doc_name,
            "article_ref": hit.article_ref,
            "source_url": hit.source_url,
            "excerpt": hit.orig_text[:200] + "..." if len(hit.orig_text) > 200 else hit.orig_text,
            "full_text": hit.orig_text,
        })
    return sources
