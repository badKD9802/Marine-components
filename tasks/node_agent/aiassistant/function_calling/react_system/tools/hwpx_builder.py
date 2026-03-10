"""
HWPX 문서 빌드 엔진 — 텍스트 기반 치환 방식

hwpxskill의 접근 방식을 따라 section0.xml을 텍스트로 읽고
str.replace()로 {{플레이스홀더}}를 치환한다.

**lxml DOM 조작(tree.write)은 사용하지 않는다.**
lxml의 tree.write()가 네임스페이스 선언을 재배치하여
한글(Hancom)에서 파일을 열 수 없게 만들기 때문이다.
lxml은 XML 무결성 검증(read-only parse)에만 사용한다.
"""

import logging
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from lxml import etree  # XML 검증(read-only)에만 사용

try:
    from app.tasks.lib_justtype.common import util

    logger = util.TimeCheckLogger(logging.getLogger(__name__), "== HWPX BUILDER ==")
except Exception:
    logger = logging.getLogger(__name__)

# 템플릿 디렉토리 (이 파일 기준 상대 경로)
_THIS_FILE = Path(__file__).resolve()
TEMPLATES_DIR = _THIS_FILE.parent.parent / "hwpx_templates"
BASE_DIR = TEMPLATES_DIR / "base"


# ==========================================
# 유틸리티
# ==========================================


def _esc(text: str) -> str:
    """XML 텍스트 노드용 이스케이프 (&, <, >)."""
    if not text:
        return ""
    return xml_escape(str(text))


def _esc_attr(text: str) -> str:
    """XML 속성값용 이스케이프 (&, <, >, ", ')."""
    if not text:
        return ""
    return xml_escape(str(text), {'"': "&quot;", "'": "&apos;"})


def _split_sections(content: str) -> list[tuple[str, str]]:
    """텍스트를 (제목, 본문) 섹션 쌍으로 분리한다."""
    sections = []
    current_title = ""
    current_body = []
    for line in content.split("\n"):
        if re.match(r"^(Ⅰ|Ⅱ|Ⅲ|Ⅳ|Ⅴ|Ⅵ|Ⅶ|Ⅷ|Ⅸ|Ⅹ|\d+)\.\s+", line.strip()):
            if current_title:
                sections.append((current_title, "\n".join(current_body).strip()))
            current_title = line.strip()
            current_body = []
        else:
            current_body.append(line)
    if current_title:
        sections.append((current_title, "\n".join(current_body).strip()))
    return sections


# 로마숫자 매핑
_ROMAN_NUMERALS = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ"]
_ROMAN_PATTERN = re.compile(r"^(Ⅰ|Ⅱ|Ⅲ|Ⅳ|Ⅴ|Ⅵ|Ⅶ|Ⅷ|Ⅸ|Ⅹ)\.\s*(.*)")
_ARABIC_PATTERN = re.compile(r"^(\d+)\.\s*(.*)")

# RAW XML 마커 — _apply_replacements()에서 이 접두어로 시작하는 값은 XML 이스케이프하지 않음
_RAW_XML_PREFIX = "<!--RAW_XML-->"


def _split_sections_roman(content: str) -> list[dict]:
    """로마숫자(Ⅰ~Ⅹ) 기준으로 대섹션을 분리하고, 아라비아숫자로 소섹션을 분리한다.

    Returns:
        [{"roman": "Ⅰ", "title": "추진 배경", "subsections": [{"num": "1", "title": "...", "body": "..."}]}]
    """
    major_sections = []
    current_roman = None
    current_title = ""
    current_lines = []

    for line in content.split("\n"):
        m = _ROMAN_PATTERN.match(line.strip())
        if m:
            if current_roman is not None:
                major_sections.append(
                    {
                        "roman": current_roman,
                        "title": current_title,
                        "body_lines": current_lines,
                    }
                )
            current_roman = m.group(1)
            current_title = m.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_roman is not None:
        major_sections.append(
            {
                "roman": current_roman,
                "title": current_title,
                "body_lines": current_lines,
            }
        )

    # 로마숫자가 없는 경우: 전체를 하나의 섹션으로
    if not major_sections and content.strip():
        major_sections.append(
            {
                "roman": "Ⅰ",
                "title": "",
                "body_lines": content.split("\n"),
            }
        )

    # 각 대섹션 내에서 아라비아숫자 소섹션 분리
    for sec in major_sections:
        subsections = []
        current_num = None
        current_sub_title = ""
        current_sub_body = []

        for line in sec["body_lines"]:
            am = _ARABIC_PATTERN.match(line.strip())
            if am:
                if current_num is not None:
                    subsections.append(
                        {
                            "num": current_num,
                            "title": current_sub_title,
                            "body": "\n".join(current_sub_body).strip(),
                        }
                    )
                current_num = am.group(1)
                current_sub_title = am.group(2).strip()
                current_sub_body = []
            else:
                current_sub_body.append(line)

        if current_num is not None:
            subsections.append(
                {
                    "num": current_num,
                    "title": current_sub_title,
                    "body": "\n".join(current_sub_body).strip(),
                }
            )

        # 소섹션 없이 본문만 있는 경우
        if not subsections:
            remaining = "\n".join(sec["body_lines"]).strip()
            if remaining:
                subsections.append({"num": None, "title": "", "body": remaining})

        sec["subsections"] = subsections
        del sec["body_lines"]  # 임시 필드 제거

    return major_sections


def _build_symbol_paragraphs(
    body_text: str, pid_start: int = 2000000001
) -> tuple[str, int]:
    """□○―※ 기호별로 별도 <hp:p> XML 파라그래프를 생성한다.

    각 줄의 시작 기호에 따라 다른 charPrIDRef/paraPrIDRef을 적용한다.

    Returns:
        (xml_string, next_pid) — 생성된 XML 문자열과 다음 사용 가능한 paragraph ID
    """
    if not body_text or not body_text.strip():
        return "", pid_start

    paragraphs = []
    pid = pid_start

    for line in body_text.split("\n"):
        stripped = line.strip()

        if not stripped:
            # 빈 줄
            paragraphs.append(
                f'  <hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
                f'<hp:run charPrIDRef="0"><hp:t/></hp:run></hp:p>'
            )
            pid += 1
            continue

        # 기호 감지 및 charPr/paraPr 매핑
        char_pr = "0"
        para_pr = "0"

        if stripped.startswith("□"):
            char_pr = "12"
            para_pr = "29"
        elif stripped.startswith("○"):
            char_pr = "13"
            para_pr = "30"
        elif (
            stripped.startswith("―")
            or stripped.startswith("–")
            or stripped.startswith("- ")
        ):
            char_pr = "14"
            para_pr = "31"
        elif stripped.startswith("※"):
            char_pr = "15"
            para_pr = "32"

        escaped_text = _esc(stripped)
        paragraphs.append(
            f'  <hp:p id="{pid}" paraPrIDRef="{para_pr}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{char_pr}"><hp:t>{escaped_text}</hp:t></hp:run></hp:p>'
        )
        pid += 1

    return "\n".join(paragraphs), pid


def _build_major_heading_xml(
    roman_num: str, title: str, tbl_id: int, p_id: int, inner_p_ids: tuple[int, int]
) -> str:
    """올리브그린 대제목 테이블 XML을 생성한다.

    proposal/section0.xml의 대제목 패턴을 그대로 재현:
    - borderFillIDRef="5" (올리브그린), borderFillIDRef="6" (연회색)
    - charPrIDRef="10" (번호, 흰색 볼드), charPrIDRef="8" (제목, 검정 볼드)
    """
    return f"""  <hp:p id="{p_id}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0">
      <hp:tbl id="{tbl_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="0" rowCnt="1" colCnt="2" cellSpacing="0" borderFillIDRef="3" noAdjust="0">
        <hp:sz width="42520" widthRelTo="ABSOLUTE" height="2800" heightRelTo="ABSOLUTE" protect="0"/>
        <hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>
        <hp:outMargin left="0" right="0" top="0" bottom="0"/>
        <hp:inMargin left="0" right="0" top="0" bottom="0"/>
        <hp:tr>
          <hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="1" borderFillIDRef="5">
            <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">
              <hp:p paraPrIDRef="21" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0" id="{inner_p_ids[0]}">
                <hp:run charPrIDRef="10"><hp:t>{_esc(roman_num)}</hp:t></hp:run>
              </hp:p>
            </hp:subList>
            <hp:cellAddr colAddr="0" rowAddr="0"/>
            <hp:cellSpan colSpan="1" rowSpan="1"/>
            <hp:cellSz width="3200" height="2800"/>
            <hp:cellMargin left="0" right="0" top="0" bottom="0"/>
          </hp:tc>
          <hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="1" borderFillIDRef="6">
            <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">
              <hp:p paraPrIDRef="22" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0" id="{inner_p_ids[1]}">
                <hp:run charPrIDRef="8"><hp:t>  {_esc(title)}</hp:t></hp:run>
              </hp:p>
            </hp:subList>
            <hp:cellAddr colAddr="1" rowAddr="0"/>
            <hp:cellSpan colSpan="1" rowSpan="1"/>
            <hp:cellSz width="39320" height="2800"/>
            <hp:cellMargin left="0" right="0" top="0" bottom="0"/>
          </hp:tc>
        </hp:tr>
      </hp:tbl>
    </hp:run>
  </hp:p>"""


def _build_minor_heading_xml(
    num: str, title: str, tbl_id: int, p_id: int, inner_p_ids: tuple[int, int]
) -> str:
    """파랑 소제목 테이블 XML을 생성한다.

    proposal/section0.xml의 소제목 패턴을 그대로 재현:
    - borderFillIDRef="7" (파랑), borderFillIDRef="8" (하단선)
    - charPrIDRef="11" (번호, 흰색 볼드), charPrIDRef="8" (제목, 검정 볼드)
    """
    return f"""  <hp:p id="{p_id}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0">
      <hp:tbl id="{tbl_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="0" rowCnt="1" colCnt="2" cellSpacing="0" borderFillIDRef="3" noAdjust="0">
        <hp:sz width="42520" widthRelTo="ABSOLUTE" height="2400" heightRelTo="ABSOLUTE" protect="0"/>
        <hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>
        <hp:outMargin left="0" right="0" top="0" bottom="0"/>
        <hp:inMargin left="0" right="0" top="0" bottom="0"/>
        <hp:tr>
          <hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="1" borderFillIDRef="7">
            <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">
              <hp:p paraPrIDRef="21" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0" id="{inner_p_ids[0]}">
                <hp:run charPrIDRef="11"><hp:t>{_esc(num)}</hp:t></hp:run>
              </hp:p>
            </hp:subList>
            <hp:cellAddr colAddr="0" rowAddr="0"/>
            <hp:cellSpan colSpan="1" rowSpan="1"/>
            <hp:cellSz width="2200" height="2400"/>
            <hp:cellMargin left="0" right="0" top="0" bottom="0"/>
          </hp:tc>
          <hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="1" borderFillIDRef="8">
            <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">
              <hp:p paraPrIDRef="22" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0" id="{inner_p_ids[1]}">
                <hp:run charPrIDRef="8"><hp:t>  {_esc(title)}</hp:t></hp:run>
              </hp:p>
            </hp:subList>
            <hp:cellAddr colAddr="1" rowAddr="0"/>
            <hp:cellSpan colSpan="1" rowSpan="1"/>
            <hp:cellSz width="40320" height="2400"/>
            <hp:cellMargin left="0" right="0" top="0" bottom="0"/>
          </hp:tc>
        </hp:tr>
      </hp:tbl>
    </hp:run>
  </hp:p>"""


def _build_empty_line(pid: int) -> str:
    """빈 줄 <hp:p> 생성."""
    return (
        f'  <hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="0"><hp:t/></hp:run></hp:p>'
    )


def _build_planning_report_placeholders(title, content, sender):
    """기획보고서 표지 + 본문 플레이스홀더를 생성한다.

    표지: {{기관명}}, {{제목}}, {{작성일}}, {{작성자}} — 일반 텍스트 치환
    본문: {{DYNAMIC_BODY}} — 동적 XML 생성 (raw 삽입)
    """
    today = datetime.now()
    name = sender.get("name", "")
    dept = sender.get("dept", "기관명")
    pos = sender.get("position", "")
    author = f"{name} {pos}".strip() if pos and pos != "-" else name
    author_line = f"{author} / {dept}" if dept else author

    # 표지 플레이스홀더 (일반 텍스트, XML 이스케이프 대상)
    ph = {
        "{{기관명}}": dept,
        "{{제목}}": title,
        "{{작성일}}": f"{today:%Y년 %m월 %d일}",
        "{{작성자}}": author_line,
    }

    # 본문 동적 XML 생성
    sections = _split_sections_roman(content)

    xml_parts = []
    tbl_id = 3000000001
    p_id = 2000000001
    inner_p_id = 2500000001  # 테이블 내부 paragraph ID 범위

    for sec in sections:
        # 대제목 테이블 (올리브그린)
        xml_parts.append(
            _build_major_heading_xml(
                sec["roman"], sec["title"], tbl_id, p_id, (inner_p_id, inner_p_id + 1)
            )
        )
        tbl_id += 1
        p_id += 1
        inner_p_id += 2

        # 빈 줄
        xml_parts.append(_build_empty_line(p_id))
        p_id += 1

        for sub in sec.get("subsections", []):
            if sub["num"] is not None:
                # 소제목 테이블 (파랑)
                xml_parts.append(
                    _build_minor_heading_xml(
                        sub["num"],
                        sub["title"],
                        tbl_id,
                        p_id,
                        (inner_p_id, inner_p_id + 1),
                    )
                )
                tbl_id += 1
                p_id += 1
                inner_p_id += 2

                # 빈 줄
                xml_parts.append(_build_empty_line(p_id))
                p_id += 1

            # 본문 기호 파라그래프
            if sub["body"]:
                body_xml, p_id = _build_symbol_paragraphs(sub["body"], p_id)
                if body_xml:
                    xml_parts.append(body_xml)

            # 섹션 간 빈 줄
            xml_parts.append(_build_empty_line(p_id))
            p_id += 1

    # 하단 페이지 번호
    xml_parts.append(
        f'  <hp:p id="{p_id}" paraPrIDRef="20" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="0"><hp:t>- 1 -</hp:t></hp:run></hp:p>'
    )

    dynamic_body = "\n".join(xml_parts)

    # {{DYNAMIC_BODY}}는 이미 XML 태그를 포함하므로 이스케이프 방지 마커 추가
    ph["{{DYNAMIC_BODY}}"] = _RAW_XML_PREFIX + dynamic_body

    return ph


# ==========================================
# 플레이스홀더 매핑 빌더
# ==========================================


def _build_gonmun_placeholders(title, content, sender, recipient=None, reference=None):
    """공문 템플릿 플레이스홀더."""
    today = datetime.now()
    name = sender.get("name", "")
    pos = sender.get("position", "")
    dept = sender.get("dept", "기관명")
    signer = f"{pos} {name}" if pos and pos != "-" else name

    paras = [p.strip() for p in content.split("\n") if p.strip()]
    body1 = paras[0] if len(paras) > 0 else ""
    body2 = paras[1] if len(paras) > 1 else ""
    detail = "\n".join(paras[2:]) if len(paras) > 2 else ""

    return {
        "{{기관명}}": dept,
        "{{수신자}}": recipient or "각 부서장",
        "{{경유}}": reference or "",
        "{{제목}}": title,
        "{{본문1}}": body1,
        "{{본문2}}": body2,
        "{{표 또는 상세내용}}": detail,
        "{{직위 성명}}": signer,
        "{{시행번호}}": f"{dept[:2]}-{today:%Y%m%d}-001",
        "{{시행일자}}": f"{today:%Y.%m.%d}",
        "{{우편번호}}": "04554",
        "{{주소}}": "서울특별시 중구 을지로 66",
        "{{홈페이지}}": "www.kamco.or.kr",
        "{{전화번호}}": sender.get("phone", "02-1234-5678"),
        "{{팩스번호}}": "02-1234-5679",
        "{{이메일}}": sender.get("email", ""),
    }


def _build_report_placeholders(title, content, sender):
    """보고서 템플릿 플레이스홀더."""
    today = datetime.now()
    name = sender.get("name", "")
    dept = sender.get("dept", "")
    author = f"{name} / {dept}" if dept else name

    sections = _split_sections(content)

    ph = {
        "{{보고서 제목}}": title,
        "{{작성일: YYYY년 MM월 DD일}}": f"작성일: {today:%Y년 %m월 %d일}",
        "{{작성자/부서}}": author,
        "{{표 삽입 위치}}": "",
    }

    if len(sections) >= 1:
        ph["1. {{섹션 제목}}"] = sections[0][0]
        ph["{{본문 내용}}"] = sections[0][1]
    else:
        ph["1. {{섹션 제목}}"] = "1. 개요"
        ph["{{본문 내용}}"] = content

    ph["2. {{섹션 제목}}"] = sections[1][0] if len(sections) >= 2 else ""

    if len(sections) >= 3:
        ph["3. {{결론}}"] = sections[2][0]
        ph["{{결론 내용}}"] = sections[2][1]
    else:
        ph["3. {{결론}}"] = "3. 결론"
        ph["{{결론 내용}}"] = ""

    return ph


def _build_minutes_placeholders(title, content, sender):
    """회의록 템플릿 플레이스홀더."""
    today = datetime.now()

    buckets = {"안건": [], "논의": [], "결정": [], "후속": []}
    current = "안건"
    for line in content.split("\n"):
        lower = line.strip().lower()
        if "논의" in lower or "토의" in lower:
            current = "논의"
        elif "결정" in lower or "결의" in lower:
            current = "결정"
        elif "후속" in lower or "조치" in lower or "향후" in lower:
            current = "후속"
        buckets[current].append(line)

    return {
        "{{회의록 제목}}": title,
        "{{YYYY년 MM월 DD일 HH:MM}}": f"{today:%Y년 %m월 %d일}",
        "{{장소}}": "",
        "{{참석자 목록}}": "",
        "{{작성자}}": sender.get("name", ""),
        "{{안건 내용}}": "\n".join(buckets["안건"]).strip() or content,
        "{{논의 내용}}": "\n".join(buckets["논의"]).strip(),
        "{{결정 사항}}": "\n".join(buckets["결정"]).strip(),
        "{{향후 조치 사항}}": "\n".join(buckets["후속"]).strip(),
    }


def _build_proposal_placeholders(title, content, sender):
    """제안서 템플릿 (고정 레이아웃 — 플레이스홀더 없음)."""
    return {}


def _build_placeholders(
    template_name, title, content, sender, recipient=None, reference=None
):
    """템플릿 이름에 따라 플레이스홀더 매핑을 생성한다."""
    builders = {
        "gonmun": lambda: _build_gonmun_placeholders(
            title, content, sender, recipient, reference
        ),
        "report": lambda: _build_report_placeholders(title, content, sender),
        "minutes": lambda: _build_minutes_placeholders(title, content, sender),
        "proposal": lambda: _build_proposal_placeholders(title, content, sender),
        "planning_report": lambda: _build_planning_report_placeholders(
            title, content, sender
        ),
    }
    builder = builders.get(template_name)
    if not builder:
        logger.warning(f"[HWPX] 알 수 없는 템플릿: {template_name}")
        return {}
    return builder()


# ==========================================
# 치환 엔진 (핵심 — lxml 없이 텍스트만 사용)
# ==========================================


def _apply_replacements(xml_text: str, placeholders: dict) -> str:
    """XML 텍스트에서 {{플레이스홀더}}를 치환한다.

    값은 XML 이스케이프하여 안전하게 삽입한다.
    _RAW_XML_PREFIX로 시작하는 값은 이미 XML이므로 이스케이프 없이 raw 삽입한다.
    중복 플레이스홀더({{본문 내용}} 등)는 첫 번째만 내용으로, 나머지는 비운다.
    """
    result = xml_text

    # 중복 가능한 플레이스홀더 목록
    duplicates = {"{{본문 내용}}"}

    for placeholder, value in placeholders.items():
        # RAW XML 마커가 있으면 이스케이프 하지 않고 raw 삽입
        if isinstance(value, str) and value.startswith(_RAW_XML_PREFIX):
            raw_value = value[len(_RAW_XML_PREFIX) :]
            result = result.replace(placeholder, raw_value)
        elif placeholder in duplicates:
            result = result.replace(placeholder, _esc(value), 1)  # 첫 번째만
        else:
            result = result.replace(placeholder, _esc(value))

    # 남은 중복 플레이스홀더 제거
    for dup in duplicates:
        result = result.replace(dup, "")

    return result


def _update_metadata_text(hpf_text: str, title: str | None, creator: str | None) -> str:
    """content.hpf 메타데이터를 텍스트 치환으로 업데이트한다.

    lxml tree.write() 없이 순수 텍스트 치환만 사용하여 XML 구조를 보존한다.
    """
    result = hpf_text

    # <opf:title/> → <opf:title>제목</opf:title>
    if title:
        result = result.replace("<opf:title/>", f"<opf:title>{_esc(title)}</opf:title>")

    now = datetime.now(timezone.utc)
    iso_now = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    date_kr = now.strftime("%Y년 %m월 %d일")

    # content 속성 치환: name="xxx" content="text" → name="xxx" content="실제값"
    attr_map = {
        "CreatedDate": iso_now,
        "ModifiedDate": iso_now,
        "date": date_kr,
    }
    if creator:
        attr_map["creator"] = _esc_attr(creator)
        attr_map["lastsaveby"] = _esc_attr(creator)

    for name, value in attr_map.items():
        old = f'name="{name}" content="text"'
        new = f'name="{name}" content="{value}"'
        result = result.replace(old, new)

    return result


# ==========================================
# ZIP 패키징 / 검증
# ==========================================


def _pack_hwpx(input_dir: Path, output_path: Path) -> None:
    """HWPX ZIP 아카이브 생성. mimetype = 첫 번째 엔트리, ZIP_STORED."""
    mimetype_file = input_dir / "mimetype"
    if not mimetype_file.is_file():
        raise FileNotFoundError(f"mimetype 파일 없음: {input_dir}")

    all_files = sorted(
        p.relative_to(input_dir).as_posix() for p in input_dir.rglob("*") if p.is_file()
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(output_path, "w", ZIP_DEFLATED) as zf:
        # mimetype은 반드시 첫 번째, 비압축(STORED)
        zf.write(mimetype_file, "mimetype", compress_type=ZIP_STORED)
        for rel_path in all_files:
            if rel_path == "mimetype":
                continue
            zf.write(input_dir / rel_path, rel_path, compress_type=ZIP_DEFLATED)


def _validate_hwpx(hwpx_path: Path) -> list[str]:
    """생성된 HWPX 파일 구조를 검증한다."""
    errors = []
    required = [
        "mimetype",
        "Contents/content.hpf",
        "Contents/header.xml",
        "Contents/section0.xml",
    ]

    try:
        zf = ZipFile(hwpx_path, "r")
    except Exception:
        return [f"ZIP 열기 실패: {hwpx_path}"]

    with zf:
        names = zf.namelist()
        for r in required:
            if r not in names:
                errors.append(f"누락: {r}")

        if "mimetype" in names:
            mt = zf.read("mimetype").decode("utf-8").strip()
            if mt != "application/hwp+zip":
                errors.append(f"잘못된 mimetype: {mt}")
            if names[0] != "mimetype":
                errors.append("mimetype이 첫 번째 엔트리가 아님")

        # XML 무결성 검사
        for name in names:
            if name.endswith(".xml") or name.endswith(".hpf"):
                try:
                    etree.fromstring(zf.read(name))
                except etree.XMLSyntaxError as e:
                    errors.append(f"XML 오류 {name}: {e}")

    size = hwpx_path.stat().st_size
    if size < 3000:
        errors.append(f"파일 크기 비정상: {size}B (최소 3KB 이상)")

    return errors


# ==========================================
# 메인 빌드 함수
# ==========================================


def build_hwpx_from_content(
    template_name: str,
    content: str,
    title: str,
    creator: str,
    sender: dict,
    output_path: str,
    recipient: str | None = None,
    reference: str | None = None,
) -> str:
    """HWPX 파일을 생성한다.

    Args:
        template_name: "gonmun" | "report" | "minutes" | "proposal" | "planning_report"
        content: LLM 생성 텍스트
        title: 문서 제목
        creator: 작성자명
        sender: 발신자 정보 dict (name, position, dept, phone, email)
        output_path: 출력 파일 경로
        recipient: 수신자 (공문용)
        reference: 참조 (공문용)

    Returns:
        생성된 파일 경로
    """
    logger.info(f"[HWPX] 빌드 시작: template={template_name}, title={title}")
    logger.info(f"[HWPX] TEMPLATES_DIR={TEMPLATES_DIR} exists={TEMPLATES_DIR.is_dir()}")
    logger.info(f"[HWPX] BASE_DIR={BASE_DIR} exists={BASE_DIR.is_dir()}")
    logger.info(f"[HWPX] output_path={output_path}")

    if not BASE_DIR.is_dir():
        raise FileNotFoundError(f"Base 템플릿 없음: {BASE_DIR}")

    overlay_dir = TEMPLATES_DIR / template_name
    has_overlay = overlay_dir.is_dir()
    if not has_overlay:
        logger.warning(f"[HWPX] 오버레이 '{template_name}' 없음, base만 사용")

    output = Path(output_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        work = Path(tmpdir) / "build"

        # 1. base 템플릿 → 작업 디렉토리 복사
        shutil.copytree(BASE_DIR, work)

        # 2. 오버레이 적용 (header.xml, section0.xml 덮어쓰기)
        if has_overlay:
            for f in overlay_dir.iterdir():
                if f.is_file() and f.suffix == ".xml":
                    shutil.copy2(f, work / "Contents" / f.name)
                    logger.info(f"[HWPX] 오버레이: {f.name}")

        section_xml = work / "Contents" / "section0.xml"
        content_hpf = work / "Contents" / "content.hpf"

        # 3. section0.xml — 텍스트 기반 플레이스홀더 치환
        #    lxml 파싱/저장을 하지 않아 네임스페이스가 보존된다.
        if section_xml.is_file():
            xml_text = section_xml.read_text(encoding="utf-8")
            logger.info(f"[HWPX] section0.xml 원본: {len(xml_text)}B")

            placeholders = _build_placeholders(
                template_name, title, content, sender, recipient, reference
            )
            logger.info(f"[HWPX] 플레이스홀더 {len(placeholders)}개")

            xml_text = _apply_replacements(xml_text, placeholders)
            section_xml.write_text(xml_text, encoding="utf-8")
            logger.info(f"[HWPX] section0.xml 치환 후: {len(xml_text)}B")
        else:
            logger.error("[HWPX] section0.xml 없음!")

        # 4. content.hpf — 메타데이터 텍스트 치환
        if content_hpf.is_file():
            hpf_text = content_hpf.read_text(encoding="utf-8")
            hpf_text = _update_metadata_text(hpf_text, title, creator)
            content_hpf.write_text(hpf_text, encoding="utf-8")
            logger.info("[HWPX] content.hpf 메타데이터 업데이트 완료")

        # 5. XML 무결성 검증 (read-only — etree.parse만 사용)
        for xf in list(work.rglob("*.xml")) + list(work.rglob("*.hpf")):
            try:
                etree.parse(str(xf))
            except etree.XMLSyntaxError as e:
                logger.error(f"[HWPX] XML 오류 {xf.name}: {e}")

        # 6. ZIP 패키징
        _pack_hwpx(work, output)

    # 7. 최종 검증
    errors = _validate_hwpx(output)
    if errors:
        for e in errors:
            logger.error(f"[HWPX] 검증: {e}")
    else:
        logger.info("[HWPX] 검증 통과")

    file_size = output.stat().st_size
    logger.info(f"[HWPX] 완료: {output} ({file_size}B)")

    if file_size < 3000:
        raise ValueError(f"HWPX 파일 크기 비정상: {file_size}B — 빌드 실패")

    return str(output)
