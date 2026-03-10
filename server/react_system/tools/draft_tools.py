"""
메일/문서 초안 작성 도구
업무 메일 및 공식 문서의 초안을 생성합니다.

주요 기능:
- draft_email: 업무 메일 초안 작성
- draft_document: 공식 문서(보고서, 기획서, 공공기관 문서) 초안 작성
  공공기관 문서는 행정안전부 공문서 작성 규정을 준수하며 LLM을 통해 실제 내용을 생성합니다.
  HWPX(한글) 파일 다운로드를 지원합니다.
"""

import html as html_mod
import logging
import os
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


# ==========================================
# 공공기관 문서 템플릿 정의 (7종 + 기획보고서 4종)
# ==========================================

# 기획보고서 공통 기호 체계 규칙 (system_prompt에 포함)
_PLANNING_REPORT_SYMBOL_RULES = """
[필수 기호 체계 규칙 -- 반드시 준수]
- 대제목은 로마숫자로 구분: \u2160. \u2161. \u2162. \u2163. \u2164. (줄 맨 앞에 위치)
- 소제목은 아라비아숫자로 구분: 1. 2. 3. (줄 맨 앞에 위치)
- 기호 체계: \u25a1 \u2192 \u25cb \u2192 \u2015 \u2192 \u203b (반드시 이 순서로 계층 표현)
  \u25a1 대항목(1단계): 주요 주제/항목을 나타냄
  \u25cb 중항목(2단계): 세부 설명, 구체적 내용
  \u2015 소항목(3단계): 상세 내용, 수치, 데이터
  \u203b 참고/비고: 부연 설명, 근거, 출처, 법적 근거

[작성 스타일]
- 경어체(합쇼체) 사용: "~합니다", "~바랍니다"
- 개조식 스타일, 핵심 키워드 먼저 제시
- 수치/데이터 기반 서술 (금액, 비율, 인원 등 포함)
- 본문 마지막에 반드시 "끝." 으로 마감
- 각 기호는 줄 맨 앞에 위치시킬 것 (들여쓰기로 표현하지 않음)

[본문 구조 예시]
\u2160. (대제목)
1. (소제목)
\u25a1 (대항목) 주요 주제
\u25cb (중항목) 세부 설명
  \u2015 (소항목) 상세 수치나 데이터
\u25cb (중항목) 또 다른 세부 설명
\u203b 관련 법적 근거: (근거 내용)
2. (소제목)
\u25a1 (대항목)
\u25cb (중항목)

끝."""

_PUBLIC_DOC_TEMPLATES = {
    "공문": {
        "aliases": ["협조전"],
        "label": "공문(협조전)",
        "hwpx_template": "gonmun",
        "system_prompt": """당신은 대한민국 공공기관 공문서 작성 전문가입니다.
행정안전부 「공문서 작성 규정」을 정확히 준수하여 공문(협조전)을 작성합니다.

[필수 형식 규칙]
- 경어체(합쇼체) 사용: "~합니다", "~바랍니다", "~주시기 바랍니다"
- 계층 번호 체계: 1. \u2192 가. \u2192 1) \u2192 가)
- 본문 첫 항목은 반드시 "1. 관련: (관련 근거/문서)" 또는 "1. (주제)에 대하여"로 시작
- 본문 마지막에 반드시 "끝." 으로 마감
- 간결하고 명확한 문장, 불필요한 수식어 배제
- 붙임 문서가 있으면 "붙임  1. (문서명) 1부." 형식

[본문 구조 예시]
1. 관련: \u25cb\u25cb부 \u25cb\u25cb과-제\u25cb\u25cb호(2026.03.09.)
2. 위와 관련하여 다음과 같이 협조 요청드립니다.
  가. (세부 내용 1)
  나. (세부 내용 2)
    1) (상세 내용)
    2) (상세 내용)
3. 기타 사항
  가. (기타 내용)

붙임  1. (문서명) 1부.  끝.""",
        "sections": ["수신", "참조", "본문", "붙임"],
        "header_fields": ["기관명", "문서번호", "시행일자"],
        "has_footer": True,
    },
    "업무보고서": {
        "aliases": [],
        "label": "업무보고서",
        "hwpx_template": "report",
        "system_prompt": """당신은 대한민국 공공기관 업무보고서 작성 전문가입니다.
행정안전부 공문서 작성 규정을 준수하여 업무보고서를 작성합니다.

[필수 형식 규칙]
- 경어체(합쇼체) 사용
- 계층 번호 체계: 1. \u2192 가. \u2192 1) \u2192 가)
- 개조식(bullet point) 스타일 위주로 작성
- 핵심 내용을 먼저, 세부 사항은 하위 항목으로 배치
- 본문 마지막에 "끝." 으로 마감
- 현황은 가능하면 수치/데이터 기반으로 작성

[본문 구조]
1. 보고 배경
2. 추진 현황
  가. (현황 항목)
  나. (현황 항목)
3. 문제점 및 분석
4. 개선 대책
  가. (대책 항목)
5. 건의사항

끝.""",
        "sections": [
            "보고 배경",
            "추진 현황",
            "문제점 및 분석",
            "개선 대책",
            "건의사항",
        ],
        "header_fields": ["기관명", "문서번호", "시행일자"],
        "has_footer": True,
    },
    "기획안": {
        "aliases": [],
        "label": "기획안",
        "hwpx_template": "report",
        "system_prompt": """당신은 대한민국 공공기관 기획안 작성 전문가입니다.
행정안전부 공문서 작성 규정을 준수하여 기획안을 작성합니다.

[필수 형식 규칙]
- 경어체(합쇼체) 사용
- 계층 번호 체계: \u2160. \u2192 1. \u2192 가. \u2192 1)
- 개조식 스타일, 핵심 키워드 먼저 제시
- 일정은 표 형식 권장, 예산은 항목별 산출 근거 포함
- 본문 마지막에 "끝." 으로 마감

[본문 구조]
\u2160. 추진 배경
\u2161. 목적 및 목표
\u2162. 추진 방안
  1. (방안 항목)
    가. (세부 내용)
\u2163. 추진 일정 및 예산
\u2164. 기대 효과

끝.""",
        "sections": [
            "추진 배경",
            "목적 및 목표",
            "추진 방안",
            "추진 일정 및 예산",
            "기대 효과",
        ],
        "header_fields": ["기관명", "문서번호", "시행일자"],
        "has_footer": True,
    },
    "회의록": {
        "aliases": [],
        "label": "회의록",
        "hwpx_template": "minutes",
        "system_prompt": """당신은 대한민국 공공기관 회의록 작성 전문가입니다.
행정안전부 공문서 작성 규정을 준수하여 회의록을 작성합니다.

[필수 형식 규칙]
- 경어체(합쇼체) 사용
- 회의 개요(일시, 장소, 참석자)를 표 형식으로 정리
- 논의 내용은 발언자별 또는 안건별로 구분
- 결정사항은 명확하게, 후속조치는 담당자/기한 포함
- 계층 번호: 1. \u2192 \u25cb \u2192 -

[본문 구조]
1. 회의 개요
  \u25cb 일  시: YYYY.MM.DD(요일) HH:MM~HH:MM
  \u25cb 장  소:
  \u25cb 참석자:
2. 주요 논의 사항
  \u25cb (안건 1)
    - (논의 내용)
  \u25cb (안건 2)
3. 결정 사항
  \u25cb (결정 내용)
4. 후속 조치 사항
  \u25cb (조치 내용) / 담당: \u25cb\u25cb / 기한: YYYY.MM.DD""",
        "sections": ["회의 개요", "주요 논의 사항", "결정 사항", "후속 조치 사항"],
        "header_fields": ["기관명", "시행일자"],
        "has_footer": False,
    },
    "결과보고서": {
        "aliases": [],
        "label": "결과보고서",
        "hwpx_template": "report",
        "system_prompt": """당신은 대한민국 공공기관 결과보고서 작성 전문가입니다.
행정안전부 공문서 작성 규정을 준수하여 결과보고서를 작성합니다.

[필수 형식 규칙]
- 경어체(합쇼체) 사용
- 계층 번호 체계: 1. \u2192 가. \u2192 1) \u2192 가)
- 추진실적은 가능하면 수치/데이터 기반으로 기술
- 성과 분석 시 목표 대비 달성률 포함
- 본문 마지막에 "끝." 으로 마감

[본문 구조]
1. 추진 경위
2. 추진 실적
  가. (실적 항목)
  나. (실적 항목)
3. 성과 분석
  가. 목표 대비 달성 현황
  나. 주요 성과
4. 향후 계획

끝.""",
        "sections": ["추진 경위", "추진 실적", "성과 분석", "향후 계획"],
        "header_fields": ["기관명", "문서번호", "시행일자"],
        "has_footer": True,
    },
    "사업계획서": {
        "aliases": [],
        "label": "사업계획서",
        "hwpx_template": "proposal",
        "system_prompt": """당신은 대한민국 공공기관 사업계획서 작성 전문가입니다.
행정안전부 공문서 작성 규정을 준수하여 사업계획서를 작성합니다.

[필수 형식 규칙]
- 경어체(합쇼체) 사용
- 계층 번호 체계: \u2160. \u2192 1. \u2192 가. \u2192 1)
- 예산은 항목별 산출 근거 포함
- 추진 일정은 단계별로 명확히 구분
- 본문 마지막에 "끝." 으로 마감

[본문 구조]
\u2160. 사업 개요
  1. 사업 배경 및 필요성
  2. 사업 목적
\u2161. 추진 전략
\u2162. 세부 추진 계획
  1. (단계/항목)
    가. (세부 내용)
\u2163. 소요 예산
\u2164. 기대 효과

끝.""",
        "sections": [
            "사업 개요",
            "추진 전략",
            "세부 추진 계획",
            "소요 예산",
            "기대 효과",
        ],
        "header_fields": ["기관명", "문서번호", "시행일자"],
        "has_footer": True,
    },
    "검토보고서": {
        "aliases": [],
        "label": "검토보고서",
        "hwpx_template": "report",
        "system_prompt": """당신은 대한민국 공공기관 검토보고서 작성 전문가입니다.
행정안전부 공문서 작성 규정을 준수하여 검토보고서를 작성합니다.

[필수 형식 규칙]
- 경어체(합쇼체) 사용
- 계층 번호 체계: 1. \u2192 가. \u2192 1) \u2192 가)
- 검토 의견은 찬반/장단점을 객관적으로 기술
- 결론에 명확한 의견(원안동의/수정동의/재검토 등) 제시
- 본문 마지막에 "끝." 으로 마감

[본문 구조]
1. 검토 배경
2. 현황 분석
  가. (현황 항목)
  나. (현황 항목)
3. 검토 의견
  가. 긍정적 측면
  나. 부정적 측면 / 보완 필요 사항
4. 결론 및 건의

끝.""",
        "sections": ["검토 배경", "현황 분석", "검토 의견", "결론 및 건의"],
        "header_fields": ["기관명", "문서번호", "시행일자"],
        "has_footer": True,
    },
    # ==========================================
    # 기획보고서 4종 (기호 체계, planning_report 템플릿)
    # ==========================================
    "정책제안보고서": {
        "aliases": ["정책제안", "정책보고서"],
        "label": "정책제안보고서",
        "hwpx_template": "planning_report",
        "system_prompt": f"""당신은 대한민국 공공기관 정책제안보고서 작성 전문가입니다.
행정안전부 공문서 작성 규정을 준수하여 정책 제안 보고서를 작성합니다.
{_PLANNING_REPORT_SYMBOL_RULES}

[정책제안보고서 섹션 구성]
\u2160. 추진 배경 및 필요성
  1. 추진 배경
  2. 정책 필요성
\u2161. 현황 분석
  1. 국내외 현황
  2. 문제점 분석
\u2162. 정책 제안
  1. 기본 방향
  2. 세부 추진 과제
\u2163. 기대 효과
\u2164. 추진 일정 및 예산

끝.""",
        "sections": [
            "추진 배경 및 필요성",
            "현황 분석",
            "정책 제안",
            "기대 효과",
            "추진 일정 및 예산",
        ],
        "header_fields": ["기관명", "문서번호", "시행일자"],
        "has_footer": True,
    },
    "사업계획보고서": {
        "aliases": ["사업계획보고", "사업추진계획"],
        "label": "사업계획보고서",
        "hwpx_template": "planning_report",
        "system_prompt": f"""당신은 대한민국 공공기관 사업계획보고서 작성 전문가입니다.
행정안전부 공문서 작성 규정을 준수하여 사업 추진 계획 보고서를 작성합니다.
{_PLANNING_REPORT_SYMBOL_RULES}

[사업계획보고서 섹션 구성]
\u2160. 사업 개요
  1. 사업 배경 및 필요성
  2. 사업 목적
\u2161. 추진 전략
  1. 기본 방향
  2. 추진 체계
\u2162. 세부 추진 계획
  1. 단계별 추진 내용
  2. 추진 일정
\u2163. 소요 예산
\u2164. 기대 효과

끝.""",
        "sections": [
            "사업 개요",
            "추진 전략",
            "세부 추진 계획",
            "소요 예산",
            "기대 효과",
        ],
        "header_fields": ["기관명", "문서번호", "시행일자"],
        "has_footer": True,
    },
    "실적보고서": {
        "aliases": ["실적보고", "성과보고서"],
        "label": "실적보고서",
        "hwpx_template": "planning_report",
        "system_prompt": f"""당신은 대한민국 공공기관 실적보고서 작성 전문가입니다.
행정안전부 공문서 작성 규정을 준수하여 사업/업무 실적 보고서를 작성합니다.
{_PLANNING_REPORT_SYMBOL_RULES}

[실적보고서 섹션 구성]
\u2160. 사업 개요
  1. 사업명 및 기간
  2. 추진 목적
\u2161. 추진 실적
  1. 주요 추진 내용
  2. 실적 현황 (수치 기반)
\u2162. 성과 분석
  1. 목표 대비 달성률
  2. 주요 성과
\u2163. 문제점 및 개선 방안
\u2164. 향후 계획

끝.""",
        "sections": [
            "사업 개요",
            "추진 실적",
            "성과 분석",
            "문제점 및 개선 방안",
            "향후 계획",
        ],
        "header_fields": ["기관명", "문서번호", "시행일자"],
        "has_footer": True,
    },
    "현안보고서": {
        "aliases": ["현안보고", "현안분석보고서"],
        "label": "현안보고서",
        "hwpx_template": "planning_report",
        "system_prompt": f"""당신은 대한민국 공공기관 현안보고서 작성 전문가입니다.
행정안전부 공문서 작성 규정을 준수하여 현안 분석 및 대응 방안 보고서를 작성합니다.
{_PLANNING_REPORT_SYMBOL_RULES}

[현안보고서 섹션 구성]
\u2160. 현안 개요
  1. 현안 사항
  2. 보고 목적
\u2161. 현황 및 문제점
  1. 현 상황
  2. 주요 문제점
\u2162. 대응 방안
  1. 기본 방향
  2. 세부 대응 계획
\u2163. 추진 일정
\u2164. 기대 효과

끝.""",
        "sections": [
            "현안 개요",
            "현황 및 문제점",
            "대응 방안",
            "추진 일정",
            "기대 효과",
        ],
        "header_fields": ["기관명", "문서번호", "시행일자"],
        "has_footer": True,
    },
}

# 기획보고서 유형 판별용 (planning_report 템플릿 사용 문서)
_PLANNING_REPORT_TYPES = {
    "정책제안보고서",
    "사업계획보고서",
    "실적보고서",
    "현안보고서",
}

# 일반 문서 템플릿 (기존 하위호환)
_GENERAL_DOC_TEMPLATES = {
    "보고서": [
        "1. 개요",
        "2. 추진 배경 및 목적",
        "3. 주요 내용",
        "4. 추진 결과",
        "5. 향후 계획",
        "6. 결론",
    ],
    "기획서": [
        "1. 기획 배경",
        "2. 목적 및 목표",
        "3. 추진 전략",
        "4. 세부 실행 계획",
        "5. 일정 및 예산",
        "6. 기대 효과",
    ],
    "제안서": [
        "1. 제안 배경",
        "2. 제안 내용",
        "3. 기술적 접근 방법",
        "4. 예산 및 일정",
        "5. 기대 효과",
        "6. 결론",
    ],
}


def guide_document_draft(
    step: str = "select_type", document_type: str = None, _auth=None
) -> dict:
    """문서 초안 작성을 단계별로 안내합니다.

    Args:
        step: "select_type" (문서 유형 목록) 또는 "show_requirements" (선택된 유형의 필요 정보)
        document_type: show_requirements 단계에서 필수. 문서 유형명 (예: 공문, 정책제안보고서)
    """
    if step == "select_type":
        return _guide_select_type()
    elif step == "show_requirements":
        return _guide_show_requirements(document_type)
    else:
        return {
            "status": "error",
            "message": f"알 수 없는 step입니다: {step}. 'select_type' 또는 'show_requirements'를 사용하세요.",
        }


def _guide_select_type() -> dict:
    """문서 유형 목록을 그룹별 버튼 리스트 HTML로 생성한다."""
    uid = uuid.uuid4().hex[:8]

    admin_docs = []
    planning_docs = []

    for key, tmpl in _PUBLIC_DOC_TEMPLATES.items():
        label = tmpl.get("label", key)
        if tmpl.get("hwpx_template") == "planning_report":
            planning_docs.append((key, label))
        else:
            admin_docs.append((key, label))

    all_docs = admin_docs + planning_docs

    show_req_tpl = (
        "var c=this.closest('.dg-container');"
        "c.querySelector('.dg-type-list').style.display='none';"
        "var ps=c.querySelectorAll('.dg-req-panel');"
        "for(var i=0;i<ps.length;i++)ps[i].style.display='none';"
        "var idx=this.getAttribute('data-idx');"
        "if(ps[idx]){ps[idx].style.display='block';ps[idx].className='dg-req-panel dg-fade-in';}"
    )
    back_js = (
        "var c=this.closest('.dg-container');"
        "var ps=c.querySelectorAll('.dg-req-panel');"
        "for(var i=0;i<ps.length;i++)ps[i].style.display='none';"
        "var l=c.querySelector('.dg-type-list');"
        "if(l){l.style.display='block';l.className='dg-type-list dg-fade-in';}"
    )

    admin_buttons = ""
    for i, (_key, label) in enumerate(admin_docs, 1):
        idx = i - 1
        escaped_label = html_mod.escape(label)
        admin_buttons += (
            f'      <button class="dg-type-btn" data-idx="{idx}" onclick="{show_req_tpl}">'
            f"{i}. {escaped_label}</button>\n"
        )

    planning_buttons = ""
    offset = len(admin_docs)
    for i, (_key, label) in enumerate(planning_docs, 1):
        idx = offset + i - 1
        escaped_label = html_mod.escape(label)
        planning_buttons += (
            f'      <button class="dg-type-btn" data-idx="{idx}" onclick="{show_req_tpl}">'
            f"{offset + i}. {escaped_label}</button>\n"
        )

    req_panels = ""
    for key, _label in all_docs:
        tmpl = _PUBLIC_DOC_TEMPLATES[key]
        req_panels += _build_requirements_panel(key, tmpl, back_js)

    html = f"""<style>
.dg-container {{ font-family: 'Pretendard','Malgun Gothic',sans-serif; max-width: 100%; margin: 4px 0; }}
.dg-header {{ font-size: 1.05em; font-weight: 700; color: #1e293b; margin-bottom: 12px; }}
.dg-group {{ margin-bottom: 14px; }}
.dg-group-title {{ font-size: 0.95em; font-weight: 600; color: #1e40af; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 2px solid #7B8B3D; }}
.dg-type-btn {{ cursor: pointer; display: block; width: 100%; padding: 9px 14px; margin-bottom: 6px; border: 1px solid #e0e0e0; border-radius: 8px; background: #fff; text-align: left; font-size: 0.92em; color: #334155; transition: background 0.2s, border-color 0.2s; font-family: inherit; }}
.dg-type-btn:hover {{ background: #f0f4e8; border-color: #7B8B3D; }}
.dg-footer {{ font-size: 0.85em; color: #64748b; margin-top: 10px; font-style: italic; }}
.dg-req-panel {{ display: none; }}
.dg-back-btn {{ cursor: pointer; color: #1976d2; background: none; border: none; font-size: 0.9em; padding: 4px 0; margin-bottom: 12px; font-family: inherit; }}
.dg-back-btn:hover {{ text-decoration: underline; }}
.dg-req-type {{ display: inline-block; font-size: 0.88em; font-weight: 600; color: #1e40af; background: #eff6ff; padding: 2px 10px; border-radius: 4px; margin-bottom: 10px; }}
.dg-req-group {{ margin-bottom: 12px; }}
.dg-req-group-title {{ font-size: 0.93em; font-weight: 600; color: #334155; margin-bottom: 4px; }}
.dg-req-list {{ list-style: none; padding: 0; margin: 0; }}
.dg-req-list li {{ font-size: 0.9em; color: #475569; padding: 3px 0 3px 12px; position: relative; }}
.dg-req-list li::before {{ content: "\\2022"; position: absolute; left: 0; color: #7B8B3D; }}
.dg-req-example {{ font-size: 0.85em; color: #64748b; margin-top: 10px; padding: 8px 12px; background: #f8fafc; border-radius: 6px; border-left: 3px solid #7B8B3D; }}
.dg-req-cta {{ font-size: 0.85em; color: #64748b; margin-top: 14px; font-style: italic; }}
.dg-fade-in {{ animation: dgFadeIn 0.3s ease-in; }}
@keyframes dgFadeIn {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
</style>
<div class="dg-container" id="dg-{uid}">
  <div class="dg-type-list" id="type-list-{uid}">
    <div class="dg-header">작성할 문서 유형을 선택해주세요</div>
    <div class="dg-group">
      <div class="dg-group-title">행정문서 (1. &rarr; 가. &rarr; 1) &rarr; 가) 번호 체계)</div>
{admin_buttons}    </div>
    <div class="dg-group">
      <div class="dg-group-title">기획보고서 (&square; &rarr; &cir; &rarr; ― &rarr; ※ 기호 체계)</div>
{planning_buttons}    </div>
    <div class="dg-footer">클릭하거나, 번호 또는 문서 유형명을 말씀해주세요.</div>
  </div>
{req_panels}</div>"""

    summary = (
        "문서 유형 선택 UI를 표시했습니다. 사용자가 버튼을 클릭하면 해당 유형의 안내가 화면에 바로 표시됩니다."
        " 사용자가 텍스트로 유형을 말하면 draft_document를 바로 호출하세요."
    )

    return {"status": "success", "html_content": html, "text_summary": summary}


def _build_requirements_panel(doc_key: str, tmpl: dict, back_js: str) -> str:
    """단일 문서 유형의 requirements 안내 패널 HTML을 생성한다."""
    label = tmpl.get("label", doc_key)
    sections = tmpl.get("sections", [])
    is_planning = tmpl.get("hwpx_template") == "planning_report"
    needs_recipient = doc_key == "공문"

    escaped_label = html_mod.escape(label)

    required_items = "      <li>제목 (문서 제목)</li>\n"
    if needs_recipient:
        required_items += "      <li>수신처 (수신 기관/부서)</li>\n"

    section_items = ""
    for s in sections:
        section_items += f"      <li>{html_mod.escape(s)}</li>\n"

    symbol_html = ""
    if is_planning:
        symbol_html = """
    <div class="dg-req-group">
      <div class="dg-req-group-title">기호 체계</div>
      <ul class="dg-req-list">
        <li>&square; 대항목(1단계) &rarr; &cir; 중항목(2단계) &rarr; ― 소항목(3단계) &rarr; ※ 참고/비고</li>
        <li>대제목: &#8544;. &#8545;. &#8546;. (로마숫자) / 소제목: 1. 2. 3. (아라비아숫자)</li>
      </ul>
    </div>"""

    if needs_recipient:
        example_text = f"예: \"{escaped_label} 작성해줘. 제목은 'AI 시스템 도입 협조 요청', 수신처는 '각 부서장'\""
    else:
        example_text = (
            f"예: \"{escaped_label} 작성해줘. 제목은 '2026년 상반기 사업 추진 현황'\""
        )

    return f"""  <div class="dg-req-panel">
    <button class="dg-back-btn" onclick="{back_js}">&larr; 목록으로 돌아가기</button>
    <div class="dg-header">{escaped_label} 작성 안내</div>
    <div class="dg-req-type">{escaped_label}</div>
    <div class="dg-req-group">
      <div class="dg-req-group-title">필수 입력 정보</div>
      <ul class="dg-req-list">
{required_items}      </ul>
    </div>
    <div class="dg-req-group">
      <div class="dg-req-group-title">자동 생성 섹션</div>
      <ul class="dg-req-list">
{section_items}      </ul>
    </div>{symbol_html}
    <div class="dg-req-example">{example_text}</div>
    <div class="dg-req-cta">위 정보를 메시지로 알려주시면 문서를 생성해드리겠습니다.</div>
  </div>
"""


def _guide_show_requirements(document_type: str) -> dict:
    """선택된 유형의 필요 정보를 안내 HTML로 생성한다."""
    if not document_type:
        return {"status": "error", "message": "document_type을 지정해주세요."}

    result = _find_public_template(document_type)
    if not result:
        return {
            "status": "error",
            "message": f"'{document_type}'은(는) 지원되지 않는 문서 유형입니다. guide_document_draft(step='select_type')으로 유형 목록을 확인하세요.",
        }

    doc_key, tmpl = result
    label = tmpl.get("label", doc_key)
    sections = tmpl.get("sections", [])
    is_planning = tmpl.get("hwpx_template") == "planning_report"
    needs_recipient = doc_key == "공문"

    required_items = "<li>제목 (문서 제목)</li>\n"
    if needs_recipient:
        required_items += "<li>수신처 (수신 기관/부서)</li>\n"

    section_items = ""
    for s in sections:
        section_items += f"<li>{html_mod.escape(s)}</li>\n"

    symbol_html = ""
    if is_planning:
        symbol_html = """
  <div class="doc-req-group">
    <div class="doc-req-group-title">기호 체계</div>
    <ul class="doc-req-list">
      <li>&square; 대항목(1단계) &rarr; &cir; 중항목(2단계) &rarr; ― 소항목(3단계) &rarr; ※ 참고/비고</li>
      <li>대제목: &#8544;. &#8545;. &#8546;. (로마숫자) / 소제목: 1. 2. 3. (아라비아숫자)</li>
    </ul>
  </div>"""

    if needs_recipient:
        example_text = f"예: \"{label} 작성해줘. 제목은 'AI 시스템 도입 협조 요청', 수신처는 '각 부서장'\""
    else:
        example_text = (
            f"예: \"{label} 작성해줘. 제목은 '2026년 상반기 사업 추진 현황'\""
        )

    html = f"""<style>
.doc-req {{ font-family: 'Pretendard','Malgun Gothic',sans-serif; max-width: 100%; margin: 4px 0; }}
.doc-req-header {{ font-size: 1.05em; font-weight: 700; color: #1e293b; margin-bottom: 12px; }}
.doc-req-type {{ display: inline-block; font-size: 0.88em; font-weight: 600; color: #1e40af; background: #eff6ff; padding: 2px 10px; border-radius: 4px; margin-bottom: 10px; }}
.doc-req-group {{ margin-bottom: 12px; }}
.doc-req-group-title {{ font-size: 0.93em; font-weight: 600; color: #334155; margin-bottom: 4px; }}
.doc-req-list {{ list-style: none; padding: 0; margin: 0; }}
.doc-req-list li {{ font-size: 0.9em; color: #475569; padding: 3px 0 3px 12px; position: relative; }}
.doc-req-list li::before {{ content: "\u2022"; position: absolute; left: 0; color: #7B8B3D; }}
.doc-req-example {{ font-size: 0.85em; color: #64748b; margin-top: 10px; padding: 8px 12px; background: #f8fafc; border-radius: 6px; border-left: 3px solid #7B8B3D; }}
</style>
<div class="doc-req">
  <div class="doc-req-header">{html_mod.escape(label)} 작성 안내</div>
  <div class="doc-req-type">{html_mod.escape(label)}</div>
  <div class="doc-req-group">
    <div class="doc-req-group-title">필수 입력 정보</div>
    <ul class="doc-req-list">
{required_items}    </ul>
  </div>
  <div class="doc-req-group">
    <div class="doc-req-group-title">자동 생성 섹션</div>
    <ul class="doc-req-list">
{section_items}    </ul>
  </div>{symbol_html}
  <div class="doc-req-example">{html_mod.escape(example_text)}</div>
</div>"""

    summary = f"[{label}] 필요 정보 안내 완료.\n"
    summary += "필수 입력: 제목"
    if needs_recipient:
        summary += ", 수신처"
    summary += f"\n자동 생성 섹션: {', '.join(sections)}"
    if is_planning:
        summary += "\n기호 체계: \u25a1\u2192\u25cb\u2192\u2015\u2192\u203b"
    summary += f'\n\n사용자가 제목 등 정보를 제공하면 draft_document(document_type="{doc_key}", title=..., ...)를 호출하세요.'

    return {"status": "success", "html_content": html, "text_summary": summary}


def _find_public_template(document_type: str) -> tuple[str, dict] | None:
    """document_type으로 공공기관 템플릿을 찾는다. aliases도 검색."""
    if document_type in _PUBLIC_DOC_TEMPLATES:
        return document_type, _PUBLIC_DOC_TEMPLATES[document_type]
    for key, tmpl in _PUBLIC_DOC_TEMPLATES.items():
        if document_type in tmpl.get("aliases", []):
            return key, tmpl
    return None


def _get_llm_config(_auth=None) -> dict:
    """LLM 설정(base_url, api_key, model)을 환경변수에서 추출한다."""
    return {
        "base_url": os.environ.get("OPENAI_BASE_URL"),
        "api_key": os.environ.get("OPENAI_API_KEY"),
        "model": os.environ.get("OPENAI_MODEL", "gpt-4o"),
    }


async def _generate_document_content(
    template: dict,
    doc_type: str,
    title: str,
    content_requirements: str | None,
    sender: dict,
    recipient: str | None = None,
    reference: str | None = None,
    _auth=None,
) -> str:
    """AsyncOpenAI를 사용하여 공공기관 문서 내용을 생성한다."""
    try:
        from openai import AsyncOpenAI

        llm_cfg = _get_llm_config(_auth)
        client_kwargs = {}
        if llm_cfg["api_key"]:
            client_kwargs["api_key"] = llm_cfg["api_key"]
        if llm_cfg["base_url"]:
            client_kwargs["base_url"] = llm_cfg["base_url"]
        client = AsyncOpenAI(**client_kwargs)
        model = llm_cfg["model"]

        today = datetime.now().strftime("%Y.%m.%d")
        sender_info = f"{sender.get('name', '')} {sender.get('position', '')} ({sender.get('dept', '')})".strip()

        user_prompt = f"""다음 정보를 바탕으로 {doc_type} 초안을 작성하세요.

\u25a0 문서 정보
- 문서 유형: {template['label']}
- 제목: {title}
- 작성일: {today}
- 작성자: {sender_info}"""

        if recipient:
            user_prompt += f"\n- 수신: {recipient}"
        if reference:
            user_prompt += f"\n- 참조: {reference}"

        user_prompt += f"""

\u25a0 포함할 내용
{content_requirements or '(사용자가 별도 요구사항을 제시하지 않았습니다. 제목을 바탕으로 적절한 내용을 작성하세요.)'}

\u25a0 섹션 구성
{chr(10).join(f'- {s}' for s in template['sections'])}

위 섹션 구성에 따라 실제 내용이 담긴 완성도 높은 문서 초안을 작성하세요.
플레이스홀더([내용을 작성하세요] 등)를 사용하지 말고, 구체적인 내용으로 채우세요."""

        is_planning = template.get("hwpx_template") == "planning_report"
        if is_planning:
            user_prompt += """

\u25a0 중요: 기호 체계 엄수
반드시 \u25a1 \u2192 \u25cb \u2192 \u2015 \u2192 \u203b 기호 체계를 사용하세요. 각 기호는 줄 맨 앞에 위치해야 합니다.
대제목은 \u2160. \u2161. \u2162. 로마숫자, 소제목은 1. 2. 3. 아라비아숫자로 시작하세요."""

        max_tokens = 6000 if is_planning else 4000

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": template["system_prompt"]},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM 문서 생성 실패: {e}")
        return None


def _generate_hwpx_file(
    template_name: str,
    title: str,
    content: str,
    sender: dict,
    recipient: str | None = None,
    reference: str | None = None,
    _auth=None,
) -> dict | None:
    """HWPX 파일을 생성하고 base64 data URI를 반환한다."""
    import base64
    import tempfile

    try:
        from react_system.tools.hwpx_builder import build_hwpx_from_content

        safe_title = (
            "".join(
                c for c in title if c.isascii() and (c.isalnum() or c in "_-")
            ).strip()[:30]
            or "document"
        )
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{safe_title}_{timestamp}.hwpx"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, filename)

            creator = sender.get("name", "")
            build_hwpx_from_content(
                template_name=template_name,
                content=content,
                title=title,
                creator=creator,
                sender=sender,
                output_path=output_path,
                recipient=recipient,
                reference=reference,
            )

            with open(output_path, "rb") as f:
                hwpx_b64 = base64.b64encode(f.read()).decode("ascii")

        logger.info(f"HWPX 파일 생성 완료: {filename} ({len(hwpx_b64)}B base64)")
        return {
            "data_uri": f"data:application/octet-stream;base64,{hwpx_b64}",
            "filename": filename,
            "title": title,
        }

    except Exception as e:
        logger.error(f"HWPX 파일 생성 실패: {e}")
        return None


def _style_doc_symbols(content_escaped: str) -> str:
    """공공문서 공통 -- 기호/번호 체계에 CSS 스타일을 적용한다 (줄 단위)."""
    import re as _re

    lines = content_escaped.split("\n")
    styled_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            styled_lines.append("<div>&nbsp;</div>")
            continue

        if _re.match(r"^(\u2160|\u2161|\u2162|\u2163|\u2164|\u2165|\u2166|\u2167|\u2168|\u2169)\.", stripped):
            styled_lines.append(
                f'<div style="font-size:1.1em;font-weight:700;margin-top:14px;margin-bottom:4px;'
                f'color:#1e40af;border-bottom:2px solid #7B8B3D;padding-bottom:4px;">{stripped}</div>'
            )
        elif _re.match(r"^\d+\.", stripped):
            styled_lines.append(
                f'<div style="font-size:1.05em;font-weight:600;margin-top:10px;margin-bottom:2px;'
                f'color:#1e3a5f;padding-left:0.6em;">{stripped}</div>'
            )
        elif _re.match(r"^[가-힣]\.", stripped):
            styled_lines.append(
                f'<div style="font-size:1.0em;font-weight:600;margin-top:6px;padding-left:1.2em;">{stripped}</div>'
            )
        elif _re.match(r"^\d+\)", stripped):
            styled_lines.append(
                f'<div style="font-size:0.97em;margin-left:1.8em;margin-top:2px;">{stripped}</div>'
            )
        elif _re.match(r"^[가-힣]\)", stripped):
            styled_lines.append(
                f'<div style="font-size:0.93em;margin-left:3.0em;color:#374151;">{stripped}</div>'
            )
        elif stripped.startswith("\u25a1"):
            styled_lines.append(
                f'<div style="font-size:1.0em;font-weight:700;margin-top:8px;padding-left:1.0em;">{stripped}</div>'
            )
        elif stripped.startswith("\u25cb"):
            styled_lines.append(
                f'<div style="font-size:0.97em;margin-left:1.8em;margin-top:2px;">{stripped}</div>'
            )
        elif (
            stripped.startswith("\u2015")
            or stripped.startswith("\u2013")
            or stripped.startswith("- ")
        ):
            styled_lines.append(
                f'<div style="font-size:0.93em;margin-left:3.0em;color:#374151;">{stripped}</div>'
            )
        elif stripped.startswith("\u203b"):
            styled_lines.append(
                f'<div style="font-size:0.9em;margin-left:1.2em;color:#6b7280;font-style:italic;'
                f'margin-top:4px;">{stripped}</div>'
            )
        else:
            styled_lines.append(f'<div style="padding-left:1.0em;">{stripped}</div>')

    return "\n".join(styled_lines)


def _build_public_doc_html(
    doc_type_label: str, title: str, content: str, sender: dict,
    has_footer: bool = True, recipient: str | None = None,
    reference: str | None = None, hwpx_url: dict | str | None = None,
    is_planning_report: bool = False,
) -> str:
    """공공기관 문서를 HTML로 렌더링한다 (복사 버튼 포함)."""
    today = datetime.now().strftime("%Y.%m.%d")
    uid = f"doc-draft-{id(content) % 100000}"
    sender_name = sender.get("name", "")
    sender_pos = sender.get("position", "")
    sender_dept = sender.get("dept", "")
    writer_label = sender_name
    if sender_pos and sender_pos != "-":
        writer_label += f" {sender_pos}"

    meta_parts = [f"\U0001f4c4 {html_mod.escape(doc_type_label)}"]
    meta_parts.append(f"제목: <b>{html_mod.escape(title)}</b>")
    if recipient:
        meta_parts.append(f"수신: <b>{html_mod.escape(recipient)}</b>")
    meta_parts.append(f"작성: <b>{html_mod.escape(writer_label)}</b>")
    meta_info = "&nbsp;&nbsp;|&nbsp;&nbsp;".join(meta_parts)

    content_escaped = html_mod.escape(content)
    content_escaped = _style_doc_symbols(content_escaped)

    footer_html = ""
    if has_footer:
        _bdr = "border:1px solid #94a3b8"
        _lbl_style = f"{_bdr};padding:5px 10px;text-align:center;font-weight:600;background:#f1f5f9;white-space:nowrap"
        _hdr_style = f"{_bdr};padding:5px 14px;text-align:center;font-weight:600;background:#dbeafe"
        _cell_style = f"{_bdr};padding:5px 14px;text-align:center"
        _sign_style = f"{_bdr};padding:5px 14px;text-align:center;height:48px;vertical-align:middle"
        _esc_pos = html_mod.escape(sender.get("position", "")) if sender.get("position") and sender.get("position") != "-" else ""
        _esc_name = html_mod.escape(sender_name)
        footer_html = f"""
  <div style="margin-top:24px;border-top:1px solid #cbd5e1;padding-top:16px;display:flex;justify-content:flex-end;">
    <table style="width:360px;border-collapse:collapse;font-size:0.86em;color:#1e293b;">
      <tr><td style="{_lbl_style}"></td><td style="{_hdr_style}">담당</td><td style="{_hdr_style}">검토</td><td style="{_hdr_style}">결재</td></tr>
      <tr><td style="{_lbl_style}">직급</td><td style="{_cell_style}">{_esc_pos}</td><td style="{_cell_style}"></td><td style="{_cell_style}"></td></tr>
      <tr><td style="{_lbl_style}">서명</td><td style="{_sign_style}">{_esc_name}</td><td style="{_sign_style}"></td><td style="{_sign_style}"></td></tr>
      <tr><td style="{_lbl_style}">날짜</td><td style="{_cell_style}">{html_mod.escape(today)}</td><td style="{_cell_style}">&nbsp;&nbsp;/&nbsp;&nbsp;/&nbsp;&nbsp;</td><td style="{_cell_style}">&nbsp;&nbsp;/&nbsp;&nbsp;/&nbsp;&nbsp;</td></tr>
    </table>
  </div>"""

    hwpx_btn = ""
    if hwpx_url:
        if isinstance(hwpx_url, dict):
            dl_href = hwpx_url["data_uri"]
            dl_name = hwpx_url.get("filename", "document.hwpx")
        else:
            dl_href = hwpx_url
            dl_name = "document.hwpx"
        hwpx_btn = f"""<a href="{dl_href}" download="{dl_name}" style="cursor:pointer;padding:4px 12px;border:1px solid #3b82f6;border-radius:6px;background:#eff6ff;font-size:0.82em;color:#1d4ed8;white-space:nowrap;text-decoration:none;margin-right:6px;">한글 다운로드</a>"""

    return f"""<style>#{uid} ::selection, #{uid}::selection {{ background:#264F78 !important; color:#fff !important; }}</style>
<div style="font-family:'Pretendard','Malgun Gothic',sans-serif;max-width:100%;margin:4px 0;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
    <span style="font-size:0.85em;color:#64748b;">{meta_info}</span>
    <div style="display:flex;gap:4px;">
      {hwpx_btn}<button onclick="(function(){{var t=document.getElementById('{uid}').innerText;navigator.clipboard.writeText(t).then(function(){{var b=event.target;b.textContent='복사됨 \u2713';setTimeout(function(){{b.textContent='복사'}},1500)}})}})()" style="cursor:pointer;padding:4px 12px;border:1px solid #cbd5e1;border-radius:6px;background:#f8fafc;font-size:0.82em;color:#475569;white-space:nowrap;">복사</button>
    </div>
  </div>
  <div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;background:#fff;">
    <div style="background:linear-gradient(135deg,#1e293b 0%,#334155 100%);color:#fff;padding:10px 18px;">
      <span style="font-size:0.9em;font-weight:600;">{html_mod.escape(sender_dept or '기관명')}</span>
      <span style="font-size:0.8em;color:#94a3b8;margin-left:12px;">{html_mod.escape(today)}</span>
    </div>
    <div id="{uid}" style="white-space:pre-wrap;padding:16px 20px;font-size:0.93em;line-height:1.75;color:#1e293b;">{content_escaped}</div>
    {footer_html}
  </div>
</div>"""


async def _get_sender_info(_auth=None):
    """인증 정보로 발신자 정보를 DB에서 조회한다."""
    if not _auth or not _auth.is_authenticated:
        return {"name": "홍길동", "position": "팀장", "dept": "경영지원팀", "team": "재무팀", "email": "hong.gd@kamco.co.kr", "phone": "02-1234-7001", "mobile": "010-1234-7001"}
    try:
        from app.tasks.node_agent.aiassistant.db_extract.db_search_api import OracleSearchClient
        db = OracleSearchClient(_auth.stat)
        df = await db.search_by_empcode(_auth.emp_code)
        if df is not None and not df.empty:
            row = df.iloc[0]
            return {"name": str(row.get("EMP_NM", _auth.user_nm)), "position": str(row.get("POSN_NM", "")), "dept": str(row.get("DEPT_NM", _auth.docdept_nm or "")), "team": str(row.get("TEAM_NM", "")), "email": str(row.get("EML", "")), "phone": str(row.get("TEL_NO", "")), "mobile": str(row.get("MBPH", ""))}
    except Exception as e:
        logger.error(f"발신자 정보 조회 실패: {e}")
    return {"name": _auth.user_nm or "", "dept": _auth.docdept_nm or ""}


def _build_signature(sender: dict, tone: str = "formal") -> str:
    """발신자 정보로 서명 블록을 생성한다."""
    if not sender:
        return "[발신자명]"
    name = sender.get("name", "")
    if not name:
        return "[발신자명]"
    parts = [name]
    position = sender.get("position", "")
    if position and position != "-":
        parts[0] = f"{name} {position}"
    dept = sender.get("dept", "")
    team = sender.get("team", "")
    org = " ".join(filter(None, [dept, team])) if (dept and dept != "-") or (team and team != "-") else ""
    if org:
        parts.append(org)
    email = sender.get("email", "")
    if email and email != "-":
        parts.append(f"E-mail: {email}")
    phone = sender.get("phone", "")
    if phone and phone != "-":
        parts.append(f"Tel: {phone}")
    mobile = sender.get("mobile", "")
    if mobile and mobile != "-":
        parts.append(f"Mobile: {mobile}")
    return "\n".join(parts)


async def draft_email(recipient, purpose, subject=None, key_points=None, tone="formal", _auth=None):
    """
    업무 메일 초안을 작성합니다.

    Args:
        recipient: 수신자
        purpose: 메일 목적
        subject: 메일 제목 (선택, 자동 생성)
        key_points: 핵심 내용 리스트 (선택)
        tone: 어조 (formal/casual)

    Returns:
        dict: 메일 초안
    """
    sender = await _get_sender_info(_auth)
    signature = _build_signature(sender, tone)
    if tone == "formal":
        greeting = f"{recipient}님께,\n\n안녕하십니까."
        closing = f"감사합니다.\n\n{signature}"
    else:
        greeting = f"{recipient}님,\n\n안녕하세요!"
        closing = f"감사합니다.\n\n{signature}"

    body_parts = [greeting, f"\n\n{purpose}에 대해 말씀드립니다.\n"]
    if key_points:
        body_parts.append("\n주요 내용은 다음과 같습니다:\n")
        for i, point in enumerate(key_points, 1):
            body_parts.append(f"{i}. {point}\n")
    else:
        body_parts.append("\n[구체적인 내용을 작성하세요]\n")
    body_parts.append(f"\n추가 문의사항이 있으시면 언제든 연락 부탁드립니다.\n\n{closing}")
    body = "".join(body_parts)

    if not subject:
        subject = f"[{purpose}] 안내"

    sender_name = sender.get("name", "") if sender else ""
    sender_pos = sender.get("position", "") if sender else ""
    sender_org = " ".join(filter(None, [sender.get("dept", ""), sender.get("team", "")])) if sender else ""
    from_label = sender_name
    if sender_pos and sender_pos != "-":
        from_label += f" {sender_pos}"
    if sender_org:
        from_label += f" ({sender_org})"

    body_escaped = html_mod.escape(body)
    uid = f"email-draft-{id(body) % 100000}"
    html_content = f"""<style>#{uid} ::selection, #{uid}::selection {{ background:#264F78 !important; color:#fff !important; }}</style>
<div style="font-family:'Pretendard','Malgun Gothic',sans-serif;max-width:100%;margin:4px 0;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
    <span style="font-size:0.85em;color:#64748b;">\U0001f4cc 제목: <b>{html_mod.escape(subject)}</b>&nbsp;&nbsp;\U0001f464 수신: <b>{html_mod.escape(recipient)}</b>&nbsp;&nbsp;\U0001f464 발신: <b>{html_mod.escape(from_label)}</b></span>
    <button onclick="(function(){{var t=document.getElementById('{uid}').innerText;navigator.clipboard.writeText(t).then(function(){{var b=event.target;b.textContent='복사됨 \u2713';setTimeout(function(){{b.textContent='\U0001f4cb 복사'}},1500)}})}})()" style="cursor:pointer;padding:4px 12px;border:1px solid #cbd5e1;border-radius:6px;background:#f8fafc;font-size:0.82em;color:#475569;white-space:nowrap;">\U0001f4cb 복사</button>
  </div>
  <div id="{uid}" style="white-space:pre-wrap;padding:16px 20px;border:1px solid #e2e8f0;border-radius:10px;background:#f8fafc;font-size:0.95em;line-height:1.7;color:#1e293b;">{body_escaped}</div>
</div>"""

    return {
        "status": "success",
        "html_content": html_content,
        "text_summary": f"제목: {subject}\n수신: {recipient}\n발신: {from_label}\n\n{body}",
        "draft": {"to": recipient, "from": sender or {"name": "[발신자명]"}, "subject": subject, "body": body, "tone": tone},
        "message": "메일 초안이 작성되었습니다.",
    }


async def draft_document(document_type, title, content_requirements=None, sections=None, recipient=None, reference=None, _auth=None):
    """
    공식 문서 초안을 작성합니다.

    Args:
        document_type: 문서 유형
        title: 문서 제목
        content_requirements: 포함할 내용이나 요구사항 (선택)
        sections: 섹션 목록 (선택, 자동 생성)
        recipient: 수신 기관/부서 (공문 작성 시)
        reference: 참조 기관/부서 (공문 작성 시)

    Returns:
        dict: 문서 초안
    """
    found = _find_public_template(document_type)

    if found:
        key, template = found
        logger.info(f"공공기관 문서 생성: {template['label']} - {title}")
        sender = await _get_sender_info(_auth)
        generated = await _generate_document_content(template, template["label"], title, content_requirements, sender, recipient=recipient, reference=reference, _auth=_auth)

        if generated:
            hwpx_url = None
            hwpx_template = template.get("hwpx_template")
            if hwpx_template:
                hwpx_url = _generate_hwpx_file(hwpx_template, title, generated, sender, recipient=recipient, reference=reference, _auth=_auth)
            is_planning = key in _PLANNING_REPORT_TYPES
            html_content = _build_public_doc_html(template["label"], title, generated, sender, has_footer=template.get("has_footer", True), recipient=recipient, reference=reference, hwpx_url=hwpx_url, is_planning_report=is_planning)
            result = {"status": "success", "html_content": html_content, "text_summary": f"[{template['label']}] {title}\n\n{generated}", "draft": {"document_type": template["label"], "title": title, "body": generated, "generated_by": "LLM"}, "message": f"{template['label']} 초안이 작성되었습니다."}
            if hwpx_url:
                result["hwpx_filename"] = hwpx_url.get("filename", "") if isinstance(hwpx_url, dict) else ""
                result["message"] += " 한글(.hwpx) 파일 다운로드가 가능합니다."
            return result
        else:
            logger.warning("LLM 생성 실패, 템플릿 구조로 fallback")
            fallback_body = f"제목: {title}\n작성일: {datetime.now().strftime('%Y년 %m월 %d일')}\n\n"
            for s in template["sections"]:
                fallback_body += f"\n{s}\n{'\u2500' * 40}\n[내용을 작성하세요]\n"
            return {"status": "success", "draft": {"document_type": template["label"], "title": title, "sections": template["sections"], "body": fallback_body, "generated_by": "Template (LLM 호출 실패)"}, "message": f"{template['label']} 템플릿이 생성되었습니다. (LLM 호출 실패로 구조만 제공)"}

    if not sections:
        sections = _GENERAL_DOC_TEMPLATES.get(document_type, ["1. 서론", "2. 본론", "3. 결론"])

    document_body = f"""{'=' * 60}
{document_type.upper()}
{'=' * 60}

제목: {title}
작성일: {datetime.now().strftime("%Y년 %m월 %d일")}

{'=' * 60}

"""
    for section in sections:
        document_body += f"\n{section}\n"
        document_body += "-" * 40 + "\n"
        document_body += f"[{section} 내용을 작성하세요]\n\n"
    if content_requirements:
        document_body += f"\n\n{'=' * 60}\n"
        document_body += f"참고사항:\n{content_requirements}\n"
        document_body += f"{'=' * 60}\n"

    return {"status": "success", "draft": {"document_type": document_type, "title": title, "sections": sections, "body": document_body, "generated_by": "Template"}, "message": f"{document_type} 초안이 작성되었습니다. (템플릿 기반)"}


# ==========================================
# 문서 검수 도구
# ==========================================

_PLANNING_REPORT_CRITERIA = """
[기획보고서 전용 검수 항목]
1. 기호 체계 정확성
   - \u25a1(대항목) \u2192 \u25cb(중항목) \u2192 \u2015(소항목) \u2192 \u203b(참고/비고) 순서 준수
   - 기호 계층이 뒤바뀌거나 건너뛰지 않아야 함
   - 각 기호의 용도가 적절해야 함
2. 들여쓰기 규칙
   - \u25a1: 1단계 (들여쓰기 없음)
   - \u25cb: 2단계 (1단계 들여쓰기)
   - \u2015: 3단계 (2단계 들여쓰기)
   - \u203b: 참고 (1단계 들여쓰기)
3. 대제목(로마숫자) 순서 및 형식
   - \u2160, \u2161, \u2162, \u2163, \u2164 순서대로 사용
   - 대제목 뒤에 마침표(.) 사용
4. 기호 계층 구조
   - 대제목(\u2160~) > 소제목(1.) > \u25a1 > \u25cb > \u2015 > \u203b
   - 각 계층이 논리적으로 올바르게 중첩되어야 함
"""

_GONMUN_CRITERIA = """
[공문 전용 검수 항목]
1. 계층 번호 체계 정확성
   - 1. \u2192 가. \u2192 1) \u2192 가) 순서 준수
   - 번호가 뒤바뀌거나 건너뛰지 않아야 함
2. 본문 시작 형식
   - 첫 항목은 "1. 관련:" 또는 "1. ~에 대하여"로 시작
3. "끝." 마감
   - 본문 마지막에 "끝." 기재 여부
4. 붙임 형식
   - "붙임  1. (문서명) 1부." 형식 준수
"""


async def review_document(document_content, document_type=None, review_focus="전체", _auth=None):
    """작성된 문서를 검수하여 개선 사항을 제안합니다.

    Args:
        document_content: 검수할 문서 내용
        document_type: 문서 유형
        review_focus: 검수 초점 (전체, 형식, 내용, 기호체계)
        _auth: AuthContext

    Returns:
        dict: 검수 결과
    """
    if not document_content or not document_content.strip():
        return {"status": "error", "message": "검수할 문서 내용이 비어있습니다."}

    try:
        from openai import AsyncOpenAI
        llm_cfg = _get_llm_config(_auth)
        client_kwargs = {}
        if llm_cfg["api_key"]:
            client_kwargs["api_key"] = llm_cfg["api_key"]
        if llm_cfg["base_url"]:
            client_kwargs["base_url"] = llm_cfg["base_url"]
        client = AsyncOpenAI(**client_kwargs)
        model = llm_cfg["model"]

        extra_criteria = ""
        if document_type:
            doc_lower = document_type.strip()
            if doc_lower in ("정책제안보고서", "사업계획보고서", "실적보고서", "현안보고서"):
                extra_criteria = _PLANNING_REPORT_CRITERIA
            elif doc_lower in ("공문", "협조전"):
                extra_criteria = _GONMUN_CRITERIA

        focus_instruction = ""
        if review_focus == "형식":
            focus_instruction = "형식(format) 영역에 집중하여 검수하세요."
        elif review_focus == "내용":
            focus_instruction = "내용(content) 영역에 집중하여 검수하세요."
        elif review_focus == "기호체계":
            focus_instruction = "기호 체계(symbol hierarchy) 영역에 집중하여 검수하세요."

        system_prompt = f"""당신은 대한민국 공공기관 문서 검수 전문가입니다.
행정안전부 「공문서 작성 규정」을 기반으로 문서를 검수합니다.

[검수 4개 영역]
1. 형식 (Format) - 10점 만점
2. 문체 (Style) - 10점 만점
3. 내용 (Content) - 10점 만점
4. 어문규범 (Grammar) - 10점 만점
{extra_criteria}
{focus_instruction}

[출력 형식 - 반드시 아래 JSON 형식으로 출력하세요]
```json
{{
  "scores": {{"format": <1~10>, "style": <1~10>, "content": <1~10>, "grammar": <1~10>}},
  "issues": [{{"area": "<format|style|content|grammar>", "severity": "<high|medium|low>", "description": "<문제 설명>", "suggestion": "<수정 제안>", "location": "<위치>"}}],
  "summary": "<전체 검수 요약>"
}}
```

[규칙]
- issues 배열에 최소 3개, 최대 15개의 이슈를 포함하세요
- JSON 외 다른 텍스트는 출력하지 마세요"""

        doc_type_label = f" (유형: {document_type})" if document_type else ""
        user_prompt = f"다음 문서를 검수해주세요{doc_type_label}.\n\n[검수 대상 문서]\n{document_content}"

        response = await client.chat.completions.create(model=model, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], temperature=0.3, max_tokens=4000)
        raw_response = response.choices[0].message.content.strip()

        import json as json_mod
        import re
        json_match = re.search(r"```json\s*(.*?)\s*```", raw_response, re.DOTALL)
        json_str = json_match.group(1) if json_match else raw_response

        try:
            review_data = json_mod.loads(json_str)
        except json_mod.JSONDecodeError:
            logger.warning("검수 결과 JSON 파싱 실패")
            return {"status": "success", "html_content": _build_review_html_fallback(raw_response, document_type), "text_summary": "문서 검수 완료 (원본 응답 반환)", "message": "문서 검수가 완료되었습니다."}

        scores = review_data.get("scores", {})
        issues = review_data.get("issues", [])
        summary_text = review_data.get("summary", "검수가 완료되었습니다.")
        total_score = sum(scores.get(k, 0) for k in ("format", "style", "content", "grammar"))
        max_score = 40

        html_content = _build_review_html(scores, issues, summary_text, total_score, max_score, document_type)
        return {"status": "success", "html_content": html_content, "text_summary": f"검수 완료: 총점 {total_score}/{max_score}점 ({summary_text})", "review": {"scores": scores, "total_score": total_score, "max_score": max_score, "issues": issues, "summary": summary_text}, "message": "문서 검수가 완료되었습니다."}

    except Exception as e:
        logger.error(f"문서 검수 실패: {e}")
        return {"status": "error", "message": f"문서 검수 중 오류가 발생했습니다: {str(e)}"}


def _build_review_html(scores, issues, summary, total_score, max_score, document_type=None):
    """검수 결과를 HTML로 렌더링한다."""
    def _score_color(score, max_val=10):
        ratio = score / max_val if max_val else 0
        return "#22c55e" if ratio >= 0.8 else "#f59e0b" if ratio >= 0.6 else "#ef4444"

    area_labels = {"format": "형식", "style": "문체", "content": "내용", "grammar": "어문규범"}
    gauge_bars = ""
    for key in ("format", "style", "content", "grammar"):
        score = scores.get(key, 0)
        label = area_labels.get(key, key)
        color = _score_color(score)
        pct = score * 10
        gauge_bars += f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;"><span style="width:60px;font-size:0.82em;color:#475569;font-weight:600;">{label}</span><div style="flex:1;height:14px;background:#e2e8f0;border-radius:7px;overflow:hidden;"><div style="width:{pct}%;height:100%;background:{color};border-radius:7px;"></div></div><span style="width:40px;text-align:right;font-size:0.85em;font-weight:700;color:{color};">{score}/10</span></div>'

    total_color = _score_color(total_score, max_score)
    severity_icons = {"high": "\U0001f534", "medium": "\U0001f7e1", "low": "\U0001f7e2"}
    severity_labels = {"high": "필수 수정", "medium": "권장 수정", "low": "선택적 개선"}

    issues_html = ""
    for issue in issues:
        sev = issue.get("severity", "medium")
        icon = severity_icons.get(sev, "\u26aa")
        sev_label = severity_labels.get(sev, sev)
        area = area_labels.get(issue.get("area", ""), issue.get("area", ""))
        desc = html_mod.escape(issue.get("description", ""))
        suggestion = html_mod.escape(issue.get("suggestion", ""))
        location = html_mod.escape(issue.get("location", ""))
        loc_html = f'<div style="font-size:0.78em;color:#94a3b8;margin-top:2px;">위치: {location}</div>' if location else ""
        sug_html = f'<div style="font-size:0.82em;color:#1d4ed8;margin-top:3px;">\U0001f4a1 {suggestion}</div>' if suggestion else ""
        border_color = '#ef4444' if sev == 'high' else '#f59e0b' if sev == 'medium' else '#22c55e'
        bg_color = '#fef2f2' if sev == 'high' else '#fffbeb' if sev == 'medium' else '#f0fdf4'
        text_color = '#dc2626' if sev == 'high' else '#d97706' if sev == 'medium' else '#16a34a'
        issues_html += f'<div style="padding:8px 12px;border-left:3px solid {border_color};background:#f8fafc;border-radius:0 6px 6px 0;margin-bottom:6px;"><div style="display:flex;align-items:center;gap:6px;"><span>{icon}</span><span style="font-size:0.78em;padding:1px 6px;background:{bg_color};border-radius:4px;color:{text_color};font-weight:600;">{sev_label}</span><span style="font-size:0.78em;color:#64748b;">[{area}]</span></div><div style="font-size:0.88em;color:#1e293b;margin-top:4px;">{desc}</div>{loc_html}{sug_html}</div>'

    doc_type_label = f" ({html_mod.escape(document_type)})" if document_type else ""
    return f"""<div style="font-family:'Pretendard','Malgun Gothic',sans-serif;max-width:100%;margin:4px 0;">
  <div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;background:#fff;">
    <div style="background:linear-gradient(135deg,#1e293b 0%,#334155 100%);color:#fff;padding:10px 18px;">
      <span style="font-size:0.9em;font-weight:600;">\U0001f4cb 문서 검수 결과{doc_type_label}</span>
      <span style="font-size:0.85em;float:right;color:{total_color};font-weight:700;">총점: {total_score}/{max_score}</span>
    </div>
    <div style="padding:16px 20px;">
      <div style="margin-bottom:14px;"><div style="font-size:0.85em;color:#64748b;margin-bottom:8px;font-weight:600;">영역별 점수</div>{gauge_bars}</div>
      <div style="padding:10px 14px;background:#f1f5f9;border-radius:8px;margin-bottom:14px;font-size:0.88em;color:#334155;">{html_mod.escape(summary)}</div>
      <div style="font-size:0.85em;color:#64748b;margin-bottom:8px;font-weight:600;">수정 제안 ({len(issues)}건)</div>
      {issues_html}
    </div>
  </div>
</div>"""


def _build_review_html_fallback(raw_response, document_type=None):
    """JSON 파싱 실패 시 원본 응답을 HTML로 렌더링한다."""
    uid = f"review-fallback-{id(raw_response) % 100000}"
    doc_type_label = f" ({html_mod.escape(document_type)})" if document_type else ""
    content_escaped = html_mod.escape(raw_response)
    return f"""<div style="font-family:'Pretendard','Malgun Gothic',sans-serif;max-width:100%;margin:4px 0;">
  <div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;background:#fff;">
    <div style="background:linear-gradient(135deg,#1e293b 0%,#334155 100%);color:#fff;padding:10px 18px;">
      <span style="font-size:0.9em;font-weight:600;">\U0001f4cb 문서 검수 결과{doc_type_label}</span>
    </div>
    <div id="{uid}" style="white-space:pre-wrap;padding:16px 20px;font-size:0.93em;line-height:1.75;color:#1e293b;">{content_escaped}</div>
  </div>
</div>"""


# ==========================================
# 테스트용
# ==========================================
if __name__ == "__main__":
    import asyncio

    async def _test():
        print("=" * 70)
        print("메일/문서 초안 작성 도구 테스트")
        print("=" * 70)

        print("\n[테스트 1: 격식 있는 업무 메일]")
        result1 = await draft_email(recipient="김팀장", purpose="월간 보고서 제출", key_points=["2월 실적 보고서 첨부", "주요 성과 3가지", "차월 계획 포함"], tone="formal")
        print(f"상태: {result1['status']}")
        print(f"메시지: {result1['message']}")

        print("\n[테스트 2: 공공기관 공문 초안]")
        result2 = await draft_document(document_type="공문", title="AI 시스템 도입 관련 협조 요청", recipient="각 부서장", content_requirements="AI 챗봇 시스템 도입 배경, 협조 요청 사항")
        print(f"상태: {result2['status']}")
        print(f"메시지: {result2['message']}")

        print("\n" + "=" * 70)

    asyncio.run(_test())
