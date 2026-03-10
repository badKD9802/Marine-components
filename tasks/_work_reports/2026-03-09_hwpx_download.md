# HWPX(한글) 파일 다운로드 기능 구현

> 작성일: 2026-03-09 | 카테고리: feat

## 배경

`draft_document` 도구로 공공기관 문서(공문, 보고서, 회의록 등)를 LLM으로 생성하여 HTML로 채팅 화면에 표시하는 기능이 있었으나, 사용자가 한글(Hancom Office)에서 편집할 수 있는 `.hwpx` 파일로 다운로드하는 기능이 없었다. [hwpxskill](https://github.com/Canine89/hwpxskill) 프로젝트의 OWPML XML 템플릿과 빌드 로직을 활용하여 구현하였다.

## 변경 사항

| 파일 | 변경 내용 |
|------|----------|
| `react_system/tools/hwpx_builder.py` | **신규** — HWPX 빌드 엔진 (텍스트 기반 플레이스홀더 치환) |
| `react_system/hwpx_templates/` | **신규** — HWPX XML 템플릿 디렉토리 (base + gonmun/report/minutes/proposal 오버레이) |
| `react_system/tools/draft_tools.py` | `_generate_hwpx_file()` 헬퍼 추가, `_build_public_doc_html()`에 다운로드 버튼 추가, `_PUBLIC_DOC_TEMPLATES`에 `hwpx_template` 키 추가 |
| `app/api/v1/endpoints/chat_router.py` | `/hwpx/{filename}` 다운로드 엔드포인트 추가 |

## 아키텍처

### 전체 흐름

```
사용자 "공문 작성해줘" → draft_document() 호출
  → LLM이 공문 내용 생성
  → _build_public_doc_html()로 HTML 렌더링 (채팅 표시)
  → _generate_hwpx_file()로 HWPX 파일 생성 (서버 저장)
  → HTML에 "한글 다운로드" 버튼 포함
  → 사용자 클릭 → /api/v1/chat/hwpx/{filename} → FileResponse
```

### HWPX 빌드 과정 (`hwpx_builder.py`)

```
1. base 템플릿 복사 → 임시 디렉토리
2. 문서유형 오버레이 적용 (gonmun/report/minutes/proposal의 header.xml, section0.xml 덮어쓰기)
3. section0.xml 텍스트 기반 {{플레이스홀더}} 치환 (str.replace — lxml 미사용)
4. content.hpf 메타데이터 텍스트 치환 (제목, 작성자, 날짜)
5. XML 무결성 검증 (etree.parse — read-only)
6. ZIP 패키징 (mimetype 첫 번째 엔트리, ZIP_STORED)
7. 최종 검증 (ZIP 구조, 파일 크기 > 3KB)
```

### 템플릿 매핑

| draft_document 유형 | hwpx_template | 템플릿 디렉토리 |
|---------------------|---------------|-----------------|
| 공문, 협조전 | `gonmun` | `hwpx_templates/gonmun/` |
| 업무보고서, 기획안, 결과보고서, 검토보고서 | `report` | `hwpx_templates/report/` |
| 회의록 | `minutes` | `hwpx_templates/minutes/` |
| 사업계획서 | `proposal` | `hwpx_templates/proposal/` |

### 파일 저장 경로

```
{UPLOAD_PATH[:-3]}hwpx/
예: /home/upload/hwpx/AI_시스템_도입_협조_20260309143022.hwpx
```

Excel 다운로드와 동일한 패턴: `settings.UPLOAD_PATH` = `/home/upload/pdf` → `[:-3]` → `/home/upload/` → `+ "hwpx/"`.

## 핵심 코드

### 텍스트 기반 치환 (hwpx_builder.py 핵심 원리)

```python
# section0.xml을 텍스트로 읽어 str.replace()로 치환
# lxml tree.write()를 사용하면 네임스페이스 선언이 재배치되어 한글에서 열 수 없음
xml_text = section_xml.read_text(encoding="utf-8")
for placeholder, value in placeholders.items():
    escaped = xml_escape(value)  # &, <, > 이스케이프
    xml_text = xml_text.replace(placeholder, escaped)
section_xml.write_text(xml_text, encoding="utf-8")
```

### _generate_hwpx_file (draft_tools.py)

```python
def _generate_hwpx_file(template_name, title, content, sender, recipient=None, reference=None, _auth=None):
    from .hwpx_builder import build_hwpx_from_content
    # settings.UPLOAD_PATH 에서 저장 경로 결정
    if _auth and _auth.stat:
        just_env = JustEnv(_auth.stat)
        settings = just_env.get_settings()
        upload_path = settings.UPLOAD_PATH
    else:
        upload_path = "/home/upload/pdf"
    hwpx_dir = f"{upload_path[:-3]}hwpx{os.sep}"
    os.makedirs(hwpx_dir, exist_ok=True)
    # ...
    build_hwpx_from_content(template_name=template_name, content=content, ...)
    return f"/api/v1/chat/hwpx/{filename}"
```

### 다운로드 엔드포인트 (chat_router.py)

```python
@router.get("/hwpx/{filename}")
async def download_hwpx(req: Request, filename: str):
    settings = req.app.state.settings
    hwpx_dir = os.path.realpath(f"{settings.UPLOAD_PATH[:-3]}hwpx")
    filepath = os.path.realpath(os.path.join(hwpx_dir, os.path.basename(filename)))
    if not filepath.startswith(hwpx_dir):
        raise HTTPException(status_code=400, detail="잘못된 파일 경로입니다.")
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(filepath, media_type="application/hwp+zip", filename=filename)
```

## 기술적 의사결정

### lxml 대신 텍스트 기반 치환을 사용하는 이유

1차 구현에서 lxml `etree.parse()` + `tree.write()`로 section0.xml을 처리했으나, 서버에서 738B의 비정상 파일이 생성됨. 원인:

- lxml의 `tree.write()`가 XML 직렬화 시 네임스페이스 선언을 재배치/축약함
- HWPX(OWPML 표준)는 `<hs:sec xmlns:hp="..." xmlns:hs="...">` 등 정확한 네임스페이스 선언 위치에 의존
- 한글(Hancom Office)은 네임스페이스가 변경된 XML을 파싱하지 못함

hwpxskill SKILL.md에서도 "text-based replacement is preferred over DOM manipulation to preserve namespace declarations"로 명시.

해결: section0.xml과 content.hpf 모두 `str.replace()`로 처리. lxml은 XML 무결성 검증(read-only `etree.parse()`)에만 사용.

### content.hpf 메타데이터 처리

content.hpf의 메타 태그 형식: `<opf:meta name="creator" content="text"/>`. `content` 속성의 기본값 `"text"`를 실제 값으로 치환:

```python
old = 'name="creator" content="text"'
new = 'name="creator" content="홍길동"'
result = result.replace(old, new)
```

## HWPX 파일 구조 (참고)

```
*.hwpx (ZIP 아카이브)
├── mimetype                    # "application/hwp+zip" (첫 번째 엔트리, ZIP_STORED)
├── META-INF/
│   └── container.xml
├── Contents/
│   ├── header.xml              # 스타일 정의 (charPr, paraPr, borderFill, fontfaces)
│   ├── section0.xml            # 본문 내용 ({{플레이스홀더}} 포함)
│   └── content.hpf             # 메타데이터 (제목, 작성자, 날짜)
├── Preview/
│   └── PrvImage.png
├── settings.xml
└── version.xml
```

### 스타일 ID 맵 (주요)

| ID | 유형 | 설명 |
|----|------|------|
| charPr 0 | 글자 | 10pt 함초롬바탕 (기본) |
| charPr 7 | 글자 | 22pt 볼드 (기관명/제목) — gonmun 기준 |
| charPr 8 | 글자 | 16pt 볼드 (서명자) — gonmun 기준 |
| charPr 9 | 글자 | 8pt (하단 연락처) — gonmun 기준 |
| paraPr 0 | 문단 | JUSTIFY, 160% 줄간격 |
| paraPr 20 | 문단 | CENTER, 160% 줄간격 |
| paraPr 21 | 문단 | CENTER, 130% (표 셀) |

각 템플릿별 전체 스타일 ID 맵은 `/tmp/hwpxskill/SKILL.md`의 "템플릿별 스타일 ID 맵" 섹션 참조.

## 영향 범위

- `draft_tools.py` — 기존 HTML 렌더링 기능에 HWPX 다운로드 버튼 추가 (기존 기능 영향 없음)
- `chat_router.py` — 새 엔드포인트 추가 (기존 엔드포인트 영향 없음, **서버 재시작 필요**)
- `hwpx_builder.py`, `hwpx_templates/` — 완전 신규 파일

## 후속 작업

- [ ] `chat_router.py` 변경 반영을 위한 서버 재시작
- [ ] 실제 한글(Hancom Office)에서 생성된 .hwpx 파일 열기 테스트
- [ ] proposal 템플릿 플레이스홀더 추가 (현재는 고정 샘플 레이아웃)
- [ ] 본문이 긴 경우 다중 `<hp:p>` 문단 동적 생성 (현재는 단일 `<hp:t>` 노드에 전체 텍스트)
- [ ] 프론트엔드에서 다운로드 버튼 스타일 개선 (현재 HTML inline onclick)

## 참고 사항

- `dynamic_reload`로 `hwpx_builder.py`와 `draft_tools.py`는 즉시 반영되지만, `chat_router.py`는 `app/api/` 경로이므로 서버 재시작 필요
- HWPX 파일은 ZIP 기반이므로 mimetype이 반드시 첫 번째 엔트리이고 `ZIP_STORED`(비압축)여야 함
- hwpxskill 프로젝트 소스: `/tmp/hwpxskill/` (클론된 상태)
- 의존성: `lxml` (이미 설치됨), 추가 패키지 불필요
