# 조사 보고서: AI 어시스턴트 도구 실행 UI 패턴 심층 분석

- 조사일: 2026-03-12
- 조사 범위: Claude Code(CLI), Claude.ai(웹), ChatGPT, Cursor, Perplexity, v0.dev, OpenAI Codex, Gemini 등 주요 AI 도구의 도구 실행 표시 UI 패턴 심층 비교 분석
- 이전 보고서: `2026-03-11-ai-chatbot-tool-execution-ui-patterns.md` (기초 조사)

---

## 1. 핵심 요약

2026년 현재 주요 AI 도구들의 도구 실행 UI는 공통적으로 **투명성(transparency)**, **점진적 공개(progressive disclosure)**, **사용자 제어(user control)** 세 축을 중심으로 발전하고 있다. Claude Code는 터미널에서 그룹화된 도구 호출을 접힘/펼침으로 관리하고 커스터마이징 가능한 스피너 동사를 제공한다. ChatGPT Deep Research와 Perplexity는 연구 계획을 먼저 보여주고 단계별 진행을 실시간으로 추적하는 "계획-실행 분리" 패턴을 채택했다. Cursor IDE는 파일별 diff 미리보기와 체크포인트 기반 롤백을 제공하며, v0.dev는 도구 실행 상태를 "상태 카드"로 시각화한다. 현재 챗봇 데모의 ProgressSteps 컴포넌트는 기본 기능이 잘 구현되어 있으나, **도구 유형별 시각적 구분**, **실행 계획 미리보기**, **중단/조정 인터페이스**, **인라인 결과 미리보기 강화** 등을 추가하면 상용 수준의 UX에 근접할 수 있다.

---

## 2. 상세 조사 내용

### 2.1 Claude Code (CLI) 도구 실행 표시 방식

#### 2.1.1 도구 호출 표시 형식
- **텍스트 포맷**: `[Read] /path/to/file.ts`, `[Bash] npm test`, `[Grep] pattern in files` 형태
- **도구 유형별 구분**: Read, Write, Edit, Bash, Grep, Glob, WebFetch, Agent(서브에이전트) 등
- **권한 계층**:
  | 도구 유형 | 승인 필요 여부 | "다시 묻지 않기" 동작 |
  |-----------|---------------|----------------------|
  | 읽기 전용 (Read, Grep, Glob) | 불필요 | N/A |
  | Bash 명령 | 필요 | 프로젝트 디렉토리+명령별 영구 저장 |
  | 파일 수정 (Edit, Write) | 필요 | 세션 종료까지 유지 |
- 출처: [Configure permissions - Claude Code Docs](https://code.claude.com/docs/en/permissions)

#### 2.1.2 스피너 및 상태 표시
- **스피너 형태**: Braille 문자 기반 ASCII 회전 애니메이션 (50ms 간격)
- **고정폭 Braille 문자**: 터미널 타이틀 애니메이션 jitter 방지
- **상태 동사 변화**:
  - 실행 중: `Reading...`, `Searching...`, `Editing...` (현재 진행형)
  - 완료: `Read`, `Searched`, `Edited` (과거형)
- **커스터마이징**: `/config` -> `spinnerVerbs` 설정으로 사용자 정의 가능
- **shimmer 효과**: thinking 상태 시 미묘한 shimmer 애니메이션
- **노력 수준 표시**: 스피너 옆에 `○` (low), `◐` (medium), `●` (high) 기호 + brief notification
- 출처: [Claude Code Changelog](https://claudefa.st/blog/guide/changelog), [Releasebot](https://releasebot.io/updates/anthropic/claude-code)

#### 2.1.3 그룹화된 도구 호출 접힘/펼침
- 다수의 Read/Search 호출을 그룹으로 묶어 접힘 표시
- 접힘 상태에서 현재 작업 중인 파일/패턴을 한 줄로 요약
- `Ctrl+O`로 도구 호출 확장 가능
- 서브에이전트 도구 호출 아래 불필요한 빈 줄 제거 (최근 개선)
- 출처: [Claude Code Changelog](https://claudefa.st/blog/guide/changelog)

#### 2.1.4 권한 승인/거부 UI
- 터미널 내 인라인 프롬프트: Claude가 도구 사용 시도 시 확인 요청
- 선택지: 승인, 거부, "Always allow" (규칙으로 저장)
- `Shift+Tab` 사이클: normal mode -> accept edits on -> plan mode on
- 복합 Bash 명령에 대한 개선된 권한 프롬프트 시각
- **권한 모드**: `default` (매번 확인), `acceptEdits` (편집 자동 승인), `plan` (분석만), `dontAsk` (사전 승인만), `bypassPermissions` (모두 건너뛰기)
- 출처: [Configure permissions - Claude Code Docs](https://code.claude.com/docs/en/permissions)

#### 2.1.5 렌더링 최적화 (2025-2026)
- ANSI 이스케이프 시퀀스로 커서 위치 지정하여 상태 줄만 갱신 (깜빡임 방지)
- 스피너 표시/숨김 시 레이아웃 jitter 감소
- 프롬프트 입력 re-render ~74% 감소
- macOS OAuth MCP 서버로 인한 UI 프레임 드롭 수정
- 출처: [Releasebot](https://releasebot.io/updates/anthropic/claude-code), [GitHub Issue #769](https://github.com/anthropics/claude-code/issues/769)

---

### 2.2 Claude.ai (웹) 도구 실행 표시

#### 2.2.1 Extended Thinking 블록
- **트리거**: 입력창 좌하단 "Search and tools" -> "Extended thinking" 토글
- **실행 중 표시**: "Thinking" + 경과 시간 타이머
- **접힘/펼침**: 클릭으로 사고 과정 요약 확인 가능
- **시각 스타일**: 연한 회색 배경, 보라색 계열 악센트, 본문보다 작은 폰트
- **안전 장치**: 유해 내용 포함 시 "the rest of the thought process is not available" 대체
- 출처: [Claude's Visible Extended Thinking](https://www.anthropic.com/news/visible-extended-thinking), [Using Extended Thinking](https://support.claude.com/en/articles/10574485-using-extended-thinking)

#### 2.2.2 Web Search 표시
- **검색 중 표시**: 검색 인디케이터 표시 + 검색어 노출
- **결과 통합**: 대화형 응답 내 인라인 citation + 소스 링크 + 관련 인용문
- **이미지 검색**: 이미지를 대화 내 직접 표시 + 원본 페이지 소스 링크
- **백엔드**: Brave Search 기반 (결과 86.7% 일치율 확인됨)
- 출처: [Enabling and using web search](https://support.claude.com/en/articles/10684626-enabling-and-using-web-search), [Claude web search explained](https://www.tryprofound.com/blog/what-is-claude-web-search-explained)

#### 2.2.3 Artifacts 표시
- **별도 패널**: 대화 옆에 전체 크기 패널로 생성된 콘텐츠 표시
- **코드 에디터**: 구문 강조 + 전용 에디터 뷰
- **HTML/다이어그램**: 미리보기 렌더링 (라이브 프리뷰)
- **번들 다운로드**: 여러 파일(HTML, CSS, JS)을 ZIP으로 패키징
- **실시간 코드 실행**: API 키 없이 포크 및 커스터마이징 가능
- 출처: [What are artifacts](https://support.claude.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them)

#### 2.2.4 전반적 디자인
- 2열 레이아웃 (사이드바 + 채팅)
- 흰/검정 배경 + 보라색 악센트 (다크 모드 지원)
- "유틸리타리안" 디자인 철학 - 콘텐츠 중심
- 출처: [Conversational AI UI Comparison 2025](https://intuitionlabs.ai/articles/conversational-ai-ui-comparison-2025)

---

### 2.3 ChatGPT 도구 실행 표시

#### 2.3.1 웹 검색/브라우징
- **상태 텍스트**: "Searching the web...", "Reading [site name]..." 형태
- **시각 요소**: 글로브 아이콘 + 회전 로딩 스피너
- **완료 후**: 참조 출처 표시 (인라인 citation), 응답 텍스트 스트리밍으로 자연스러운 전환
- **GPT-5.3 Instant**: 더 정확한 검색 + 풍부한 컨텍스트 결과
- 출처: [Browsing the Web with ChatGPT Atlas](https://help.openai.com/en/articles/12628371-browsing-the-web-with-chatgpt-atlas)

#### 2.3.2 Deep Research 진행 표시
- **연구 계획**: 사용자가 연구 시작 전 계획을 생성/수정 가능
- **사이드바 진행**: 단계별 요약 + 사용된 소스 목록 실시간 표시
- **중단/조정**: 진행 중 "update" 클릭으로 초점 변경, 접근 소스 제한 가능
- **GPT-5.4 Thinking**: 추론 과정을 사전 노출, 중간에 방향 전환 가능
- **소요 시간**: 5~30분 (복잡도 기반), 완료 시 알림 수신
- **체인 오브 소트 요약**: 각 deep research/thinking 출력에 투명한 추론 과정 제공
- 출처: [Introducing Deep Research](https://openai.com/index/introducing-deep-research/), [Deep Research FAQ](https://help.openai.com/en/articles/10500283-deep-research-faq)

#### 2.3.3 Code Interpreter (Advanced Data Analysis)
- **실행 흐름**: 샌드박스 열림 -> 코드 실행 -> 결과/차트/파일을 채팅 내 표시
- **코드 블록**: 구문 강조 + 복사 버튼 + 모노스페이스 폰트
- **Canvas (2024~)**: 분할 화면 작업 공간, 실시간 코드 편집
  - Python 코드: Pyodide(WebAssembly)로 브라우저 내 직접 실행
  - 코딩 단축키: 코드 리뷰, 로그 추가, 주석 추가, 버그 수정, 언어 변환
- **모드 선택**: "Auto", "Fast", "Thinking" 모드 전환 가능
- 출처: [AI UI Comparison 2025](https://intuitionlabs.ai/articles/conversational-ai-ui-comparison-2025), [Introducing canvas](https://openai.com/index/introducing-canvas/)

#### 2.3.4 DALL-E 이미지 생성
- **진행 표시**: "Generating image..." 텍스트 + 로딩 애니메이션
- **결과**: 이미지 인라인 표시 + 다운로드 옵션
- **상태 전환**: 로딩 -> 이미지 렌더링으로 자연스러운 전환

---

### 2.4 OpenAI Codex (CLI) 도구 실행 표시

#### 2.4.1 전체 화면 터미널 UI (TUI)
- **구문 강조**: 마크다운 코드 블록과 diff에 대한 syntax highlighting
- **테마**: `/theme`으로 색상 테마 선택/미리보기/저장, 커스텀 `.tmTheme` 파일 지원
- **실시간 진행**: 코드 실행 중 라이브 업데이트, 진행 모니터링
- 출처: [Codex CLI features](https://developers.openai.com/codex/cli/features/)

#### 2.4.2 승인/거부 인터페이스
- **인라인 승인**: 계획 설명 -> 사용자 승인/거부 -> 실행
- **권한 요청 도구**: `request_permissions` 빌트인 도구로 런타임 추가 권한 요청
- **TUI 렌더링**: 권한 요청 승인 호출에 대한 전용 렌더링
- **승인 모드**: Auto, Read-only, Full Access
- 출처: [Codex CLI features](https://developers.openai.com/codex/cli/features/), [Introducing Codex](https://openai.com/index/introducing-codex/)

#### 2.4.3 실행 중 상호작용
- 실행 중 `Enter` 키로 새 명령 주입 가능
- 실행 완료 전 `/copy` 시 가장 최근 완료된 출력 복사 (진행 중 텍스트와 구분)
- transcript로 모든 액션 연속 노출
- 출처: [Codex CLI features](https://developers.openai.com/codex/cli/features/)

---

### 2.5 Cursor IDE 도구 실행 표시

#### 2.5.1 에이전트 모드 도구 호출
- **파일 읽기**: "Reading docs" + 파일명 표시
- **파일 편집**: "Editing files" + diff 미리보기
- **터미널 실행**: `$ npm run build` 형태로 명령 표시
- **코드 검색**: "Searched [패턴]" 텍스트 표시
- **스크린샷**: "Taking screenshot" (디버그 컨텍스트용)
- 출처: [Cursor Product Page](https://cursor.com/product)

#### 2.5.2 Diff 미리보기 시스템
- **실시간 diff**: 변경 사항이 나타나는 것을 실시간으로 관찰 가능
- **멀티 파일 diff**: 여러 파일의 변경을 한눈에 확인 (Diffs & Review 인터페이스)
- **파일 표기**: `summary.py+150-0` (추가 150줄, 삭제 0줄) 형식
- **중단**: `Escape`로 에이전트가 잘못된 방향으로 갈 때 즉시 중단
- **Edited Files 탭**: 에이전트 채팅 내 수정된 파일 목록 접근
- 출처: [Cursor Product Page](https://cursor.com/product), [Cursor Changelog](https://cursor.com/changelog)

#### 2.5.3 체크포인트 시스템
- **타임라인 스냅샷**: 각 단계마다 git 커밋과 유사한 체크포인트 생성
  - 예: "Set up Next.js project" (Jan 8)
- **롤백**: 이전 체크포인트로 되돌아가기 가능
- 출처: [Cursor Product Page](https://cursor.com/product)

#### 2.5.4 MCP Apps & Interactive UI
- 에이전트 채팅 내 인터랙티브 UI 표시 (차트, 다이어그램, 화이트보드)
- Amplitude, Figma, tldraw 등의 외부 도구 직접 임베드
- 출처: [Cursor Changelog](https://cursor.com/changelog)

#### 2.5.5 작업 시간 추적
- 각 작업에 소요 시간 표시 ("10m", "30m", "45m")
- 사고 처리 시간: "Thought 7s"
- "In Progress" / "Ready for Review" 상태 카테고리 구분
- 출처: [Cursor Product Page](https://cursor.com/product)

---

### 2.6 Perplexity AI 검색 진행 표시

#### 2.6.1 Pro Search 단계별 진행
- **계획-실행 분리**: 쿼리 -> AI 계획 수립 -> 단계별 검색 쿼리 생성/실행 -> 종합 답변
- **확장 가능한 섹션**: 각 검색 단계를 클릭하여 세부 정보 확인
- **인용 호버**: 마우스 호버 시 출처 미리보기 스니펫 표시
- 출처: [Perplexity Pro Search Case Study](https://www.langchain.com/breakoutagents/perplexity)

#### 2.6.2 Advanced Deep Research (2026)
- **진행 표시**: 읽고 있는 소스, 학습 중인 내용, 보고서 구성 진행 실시간 표시
- **핵심 발견 조기 표시**: 연구 진행 중에도 주요 발견사항을 먼저 표시 -> 최종 보고서 완성 전 정보 확인 가능
- **보고서 스트리밍**: 연구 보고서가 파일에 직접 스트리밍, 편집/정제/공유 가능
- **새 UI**: 다크모드 대시보드 + 쿼리별 인터랙티브 섹션
- **엔진**: Opus 4.5/4.6 기반 (2026년 3월 업데이트)
- 출처: [What's New in Advanced Deep Research](https://www.perplexity.ai/help-center/en/articles/13600190-what-s-new-in-advanced-deep-research), [Perplexity Changelog](https://www.perplexity.ai/changelog)

#### 2.6.3 디자인 원칙
- "사용자가 실제로 궁금해할 때까지 정보를 과다하게 보여주지 않는다. 그 다음, 호기심을 충족시킨다." - William Zhang, Perplexity PM
- **대기 시간의 UX 전환**: 동적 UI 피드백으로 대기 시간을 참여도 유지 기능으로 전환
- 출처: [Perplexity Pro Search Case Study](https://www.langchain.com/breakoutagents/perplexity)

---

### 2.7 v0.dev 코드 생성 진행 표시

#### 2.7.1 에이전트 모드 시각적 피드백
- **라이브 업데이트**: 에이전트 액션에 대한 실시간 업데이트
- **태스크 카드**: 진행 중인 작업의 시각적 카드 표현
- **상태 카드**: 외부 도구 실행에 대한 상태 카드 표시
- **인용 필**: 웹 검색 결과에 대한 소스 웹사이트 직접 링크 pill
- **애니메이션 로딩 인디케이터**: 검색/실행 중 애니메이션 표시
- 출처: [v0 Agentic Features](https://v0.app/docs/agentic-features)

#### 2.7.2 에이전트 제어
- **투명성**: 에이전트 의사결정 과정 가시화
- **중단 가능**: 언제든지 에이전트 실행 중단
- **자동 진행**: 멀티스텝 작업의 자동 순차 진행
- **Fix with v0 버튼**: 배포 팝오버에서 자동 에러 수정 버튼 + "Free" 배지
- 출처: [v0 Agentic Features](https://v0.app/docs/agentic-features)

---

### 2.8 Google Gemini Deep Research 진행 표시

#### 2.8.1 연구 계획 표시
- **계획 수립**: AI가 연구 계획 생성 -> 사용자가 섹션 추가/제거/수정 후 승인
- **실행**: 승인 후 웹 소스 분석 시작 (100+ 페이지 읽기)
- **라이브 업데이트**: 분석 중인 소스, 발견한 인사이트 실시간 표시
- **소요 시간**: 5~10분 (복잡한 보고서는 더 오래 소요)
- 출처: [Deep Research - Gemini](https://support.google.com/g/answer/16577209), [Google Gemini Deep Research Guide](https://www.digitalapplied.com/blog/google-gemini-deep-research-guide)

#### 2.8.2 시각적 보고서 (2026)
- 보고서 내 커스텀 이미지, 차트, 인터랙티브 시뮬레이터 직접 임베드
- Canvas-first 편집: Canvas에서 시각적 요소 정제 -> Google Docs로 내보내기
- **디자인**: Material Design (흰 배경, Google Sans, 파란 악센트)
- 출처: [Gemini Deep Research Visual Reports](https://www.gend.co/blog/gemini-deep-research-visual-reports-2026)

---

### 2.9 공통 UI 패턴 종합 비교

| 기능 | Claude Code | Claude.ai | ChatGPT | Cursor | Perplexity | v0.dev | Codex CLI | Gemini |
|------|------------|-----------|---------|--------|------------|--------|-----------|--------|
| **상태 동사** | Reading/Read | Thinking + 타이머 | Searching... | Reading docs | 단계별 계획 | 라이브 업데이트 | 계획 -> 승인 | 계획 -> 실행 |
| **접힘/펼침** | 그룹화 접힘 | Thinking 토글 | Deep Research 사이드바 | Diff 확장 | 검색 단계 확장 | - | - | 계획 섹션 |
| **중단/조정** | - | - | 방향 수정 가능 | Escape 중단 | - | 중단 가능 | Enter로 명령 주입 | 계획 수정 |
| **diff/결과 미리보기** | 파일 패턴 | Artifact 패널 | Canvas 편집 | 실시간 diff | 인용 호버 | 태스크 카드 | syntax highlight | 시각 보고서 |
| **시간 표시** | 경과 시간 | 사고 시간 | 5~30분 알림 | 작업 시간 | - | - | 1~30분 | 5~10분 |
| **권한/승인** | 인라인 프롬프트 | - | - | 승인 제어 | - | - | 인라인 승인 | 계획 승인 |
| **노력/모드** | low/mid/high | - | Auto/Fast/Thinking | - | Pro/Advanced | - | Auto/ReadOnly/Full | - |

---

## 3. 프로젝트 현황 분석: 현재 있는 것 vs 추가하면 좋을 것

### 3.1 현재 ProgressSteps 컴포넌트 기능

**파일**: `/mnt/c/Users/qorud/Desktop/my-boat-shop/chatbot-demo/frontend/src/components/message-parts/ProgressSteps.tsx`

| 기능 | 구현 상태 | 구현 방식 |
|------|----------|----------|
| 상태별 아이콘 | 구현됨 | Lucide 아이콘 (Loader2, CheckCircle2, XCircle, Circle) |
| 스피너 (실행 중) | 구현됨 | `animate-spin` + indigo 색상 border |
| 체크마크 (완료) | 구현됨 | CheckCircle2 green-500 |
| 에러 표시 | 구현됨 | XCircle red-500 |
| 대기 상태 | 구현됨 | Circle gray-300/600 |
| 접힘/펼침 토글 | 구현됨 | CSS Grid `gridTemplateRows` 트랜지션 |
| 자동 접힘 | 구현됨 | 모든 단계 완료 + 스트리밍 종료 시 |
| 진행 카운터 | 구현됨 | "작업 수행 중... (N/M)" / "N개 작업 완료" |
| 경과 시간 | 구현됨 | 1초 간격 타이머, `tabular-nums` 고정폭 |
| 카드 컨테이너 | 구현됨 | rounded-lg border bg-gray-50/50 |
| 미리보기 (문자열) | 구현됨 | line-clamp-2 텍스트 |
| 미리보기 (객체 배열) | 구현됨 | icon + text + sub, 최대 3건 표시 |
| result_count | 구현됨 | "N건" 형식 |
| shimmer 텍스트 | 구현됨 | `shimmer-text` 클래스 (헤더) |
| 진입 애니메이션 | 구현됨 | `animate-fade-in-up` + stagger delay |
| 접근성 속성 | 구현됨 | `aria-expanded`, `aria-label`, `role="list/listitem"` |
| 스크롤 가능 영역 | 구현됨 | `max-h-28 overflow-y-auto` |
| 다크모드 | 구현됨 | dark: 변수 사용 |

### 3.2 추가하면 좋을 기능 (우선순위별)

#### [높음] 도구 유형별 시각적 구분

**참고 패턴**: Claude Code의 `[Read]`, `[Bash]`, `[Grep]` 구분 / Cursor의 파일/터미널/검색 구분

현재 모든 단계가 동일한 스타일로 표시된다. 도구 유형에 따라 작은 배지 또는 아이콘을 추가하면 사용자가 어떤 종류의 작업이 수행 중인지 즉시 파악할 수 있다.

```tsx
// 제안 구현
const TOOL_BADGES: Record<string, { icon: string; color: string; label: string }> = {
  search:   { icon: 'Search',   color: 'text-blue-500',   label: 'DB 검색' },
  api:      { icon: 'Globe',    color: 'text-purple-500', label: 'API 호출' },
  analysis: { icon: 'BarChart', color: 'text-amber-500',  label: '분석' },
  generate: { icon: 'Wand2',    color: 'text-pink-500',   label: '생성' },
}
```

#### [높음] 실행 완료 후 인라인 결과 요약 강화

**참고 패턴**: Perplexity의 인용 호버 미리보기 / ChatGPT의 소스 citation

현재 `preview`가 문자열 또는 배열로 제공되지만, 완료된 단계에 대해 결과를 클릭하면 상세 정보를 표시하는 확장 가능한 영역을 추가할 수 있다.

```tsx
// 제안: 완료된 단계 클릭 시 결과 확장
<button onClick={() => toggleStepDetail(i)}>
  <span>{step.title}</span>
  {step.status === 'completed' && step.detail && (
    <ChevronRight size={12} className={expandedStep === i ? 'rotate-90' : ''} />
  )}
</button>
{expandedStep === i && <StepDetail data={step.detail} />}
```

#### [높음] 도구 실행 계획 미리보기

**참고 패턴**: ChatGPT Deep Research의 연구 계획 / Gemini의 계획 수정 / Perplexity의 step-by-step plan

AI가 여러 도구를 실행하기 전에 "이런 순서로 작업하겠습니다"라는 계획을 먼저 보여주는 패턴. 사용자 신뢰도를 크게 높인다.

```tsx
// 제안: plan step 타입 추가
interface PlanStep {
  type: 'plan';
  steps: string[];  // ["DB에서 부품 검색", "가격 비교 분석", "추천 결과 생성"]
}
```

#### [중간] 단계별 소요 시간 개별 표시

**참고 패턴**: Cursor의 작업별 시간 표시 ("10m", "Thought 7s")

현재는 전체 경과 시간만 표시한다. 각 단계별 소요 시간을 표시하면 어떤 작업이 오래 걸리는지 파악할 수 있다.

```tsx
// 제안: step에 duration 필드 추가
interface ProgressStep {
  // ... 기존 필드
  startedAt?: number;  // timestamp
  completedAt?: number;
}
// 표시: "DB 검색 (2.3s)" 형식
```

#### [중간] 중단/취소 버튼

**참고 패턴**: ChatGPT Deep Research 방향 수정 / Cursor Escape 중단 / v0 중단 가능

장시간 작업 시 사용자가 중단할 수 있는 X 버튼 또는 "취소" 인터페이스.

```tsx
// 제안: 헤더에 취소 버튼 추가
{hasActive && onCancel && (
  <button onClick={onCancel} className="text-gray-400 hover:text-red-500">
    <X size={14} />
  </button>
)}
```

#### [중간] 스켈레톤/예측 로딩 (1초 미만 작업 생략)

**참고 패턴**: AWS Cloudscape의 1초 미만 로딩 생략 패턴

매우 빠른 작업은 깜빡임만 유발하므로 표시를 생략하는 것이 좋다. 반대로 오래 걸리는 작업은 스켈레톤 UI로 예상 결과 영역을 미리 보여줄 수 있다.

#### [중간] 인용/소스 링크 통합

**참고 패턴**: Perplexity의 citation pill / ChatGPT의 인라인 citation / Claude.ai의 소스 링크

도구 실행 결과에 참조 소스가 있을 때 클릭 가능한 링크로 표시.

```tsx
// 제안: preview 배열 아이템에 url 필드 추가
interface PreviewItem {
  icon?: string;
  text: string;
  sub?: string;
  url?: string;  // 클릭 시 새 탭 열기
}
```

#### [낮음] 도구 실행 승인/거부 인터페이스

**참고 패턴**: Claude Code/Codex의 인라인 승인 프롬프트

보안이 중요한 작업(외부 API 호출, DB 수정 등)에 대해 사용자 확인을 요청하는 UI.

```tsx
// 제안: approval status 추가
if (step.status === 'approval-required') {
  return (
    <div className="flex gap-2">
      <button onClick={() => onApprove(step)}>승인</button>
      <button onClick={() => onDeny(step)}>거부</button>
    </div>
  );
}
```

#### [낮음] 멀티스텝 구분선

**참고 패턴**: Vercel AI SDK의 `step-start` 파트

서로 다른 도구 호출 그룹 간 시각적 구분선 추가.

#### [낮음] 완료 요약 카드

**참고 패턴**: Perplexity의 핵심 발견 조기 표시 / Gemini 시각 보고서

모든 단계 완료 후 전체 결과를 요약하는 카드 형태의 마무리 표시.

### 3.3 기능 비교 매트릭스

| 기능 | Claude Code | Claude.ai | ChatGPT | Cursor | Perplexity | 현재 데모 | 추가 제안 |
|------|:-----------:|:---------:|:-------:|:------:|:----------:|:---------:|:---------:|
| 상태 아이콘 4종 | -- | -- | -- | -- | -- | O | -- |
| 스피너 애니메이션 | O | O | O | -- | O | O | -- |
| 접힘/펼침 | O | O | O | O | O | O | -- |
| 자동 접힘 (완료 시) | O | -- | -- | -- | -- | O | -- |
| 경과 시간 | O | O | -- | O | -- | O | -- |
| 진행 카운터 | -- | -- | -- | -- | -- | O | -- |
| shimmer 효과 | O | -- | -- | -- | -- | O | -- |
| 진입 애니메이션 | -- | -- | -- | -- | -- | O | -- |
| 카드 컨테이너 | -- | O | -- | O | O | O | -- |
| 미리보기 | -- | -- | O | O | O | O | -- |
| **도구 유형 배지** | O | -- | O | O | -- | X | 제안 |
| **실행 계획 미리보기** | -- | -- | O | -- | O | X | 제안 |
| **단계별 소요 시간** | -- | -- | -- | O | -- | X | 제안 |
| **중단/취소** | -- | -- | O | O | -- | X | 제안 |
| **결과 상세 확장** | -- | -- | -- | O | O | X | 제안 |
| **소스/인용 링크** | -- | O | O | -- | O | X | 제안 |
| **승인/거부** | O | -- | -- | O | -- | X | 제안 |
| **완료 요약 카드** | -- | -- | -- | -- | O | X | 제안 |

> O = 구현됨, X = 미구현, -- = 해당 없음

---

## 4. 참고 자료

### 공식 문서 / 1차 자료
- [Configure permissions - Claude Code Docs](https://code.claude.com/docs/en/permissions) - 도구 권한 체계, 승인/거부 UI, 모드 설정
- [Claude Code overview](https://code.claude.com/docs/en/overview) - Claude Code 도구 실행 전반
- [Claude Code Changelog](https://code.claude.com/docs/en/changelog) - 공식 변경 이력
- [Releasebot - Claude Code Releases](https://releasebot.io/updates/anthropic/claude-code) - 2026년 3월 최신 UI 업데이트 집계
- [Claude's Visible Extended Thinking](https://www.anthropic.com/news/visible-extended-thinking) - Thinking 블록 공식 발표
- [Enabling and using web search](https://support.claude.com/en/articles/10684626-enabling-and-using-web-search) - Claude.ai 웹 검색 UI
- [What are artifacts](https://support.claude.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them) - Artifacts 표시 방식
- [Introducing Deep Research](https://openai.com/index/introducing-deep-research/) - ChatGPT Deep Research 소개
- [Deep Research FAQ](https://help.openai.com/en/articles/10500283-deep-research-faq) - Deep Research 진행 UI 설명
- [Introducing canvas](https://openai.com/index/introducing-canvas/) - ChatGPT Canvas UI
- [Browsing the Web with ChatGPT Atlas](https://help.openai.com/en/articles/12628371-browsing-the-web-with-chatgpt-atlas) - 웹 검색 UI
- [Codex CLI features](https://developers.openai.com/codex/cli/features/) - Codex 터미널 UI 상세
- [Introducing Codex](https://openai.com/index/introducing-codex/) - Codex 소개 및 UI
- [Cursor Product Page](https://cursor.com/product) - Cursor 에이전트 모드 UI
- [Cursor Changelog](https://cursor.com/changelog) - Cursor 최신 UI 업데이트
- [v0 Agentic Features](https://v0.app/docs/agentic-features) - v0 에이전트 시각적 피드백
- [What's New in Advanced Deep Research - Perplexity](https://www.perplexity.ai/help-center/en/articles/13600190-what-s-new-in-advanced-deep-research) - 2026 Perplexity 업데이트
- [Perplexity Pro Search Case Study](https://www.langchain.com/breakoutagents/perplexity) - 단계별 UI 상세 분석
- [Deep Research - Gemini](https://support.google.com/g/answer/16577209) - Gemini 연구 계획 UI
- [Gemini Deep Research Visual Reports](https://www.gend.co/blog/gemini-deep-research-visual-reports-2026) - 2026 시각 보고서

### 디자인 패턴 / 2차 자료
- [Conversational AI UI Comparison 2025](https://intuitionlabs.ai/articles/conversational-ai-ui-comparison-2025) - 주요 AI 챗봇 UI 종합 비교
- [tweakcc - Claude Code UI Customization](https://github.com/Piebald-AI/tweakcc) - Claude Code 내부 UI 구조 노출 도구
- [Claude web search explained](https://www.tryprofound.com/blog/what-is-claude-web-search-explained) - Brave Search 백엔드 분석
- [Chatbot UI Best Practices 2026](https://vynta.ai/blog/chatbot-ui/) - 2026 챗봇 UI 모범 사례
- [AI UI Patterns (patterns.dev)](https://www.patterns.dev/react/ai-ui-patterns/) - React AI UI 패턴
- [The Shape of AI](https://www.shapeof.ai) - AI UX 디자인 패턴 분류

---

## 5. 추가 조사 필요 사항

- [높음] ChatGPT Deep Research 사이드바의 정확한 UI 구조 (단계 목록, 소스 표시, 중단 버튼 위치) - 브라우저 DevTools로 직접 확인 필요
- [높음] Perplexity Advanced Deep Research의 새 UI 상세 스크린샷 분석 - 2026년 3월 업데이트 이후 변경점 직접 확인 필요
- [중간] Claude Code Desktop App의 시각적 diff 리뷰 UI - 터미널과 다른 GUI 기반 표시 방식
- [중간] OpenAI Codex의 `request_permissions` TUI 렌더링 정확한 시각적 형태 확인
- [중간] Gemini Canvas-first 편집 인터페이스의 도구 실행 표시 방식
- [낮음] Windsurf/Cline/Aider 등 기타 AI 코딩 도구의 도구 실행 UI 비교
- [낮음] Google Gemini "Google It" 버튼의 정확한 인터랙션 패턴 및 결과 표시
- [낮음] DeepSeek의 Chain-of-Thought 표시 UI 상세 분석
