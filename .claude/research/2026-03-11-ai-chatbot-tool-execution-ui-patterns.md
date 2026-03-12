# 조사 보고서: AI 챗봇 도구 실행 진행 표시 UI 패턴

- 조사일: 2026-03-11
- 조사 범위: Claude Code(터미널), Claude.ai(웹), ChatGPT, Perplexity 등 주요 AI 챗봇의 도구 실행 진행 표시 UI 패턴, CSS 구현 참고사항

## 1. 핵심 요약

AI 챗봇의 도구 실행 UI는 크게 세 가지 계층으로 구성된다: (1) 상위 수준의 진행 요약(스피너 + 카운터), (2) 개별 단계 표시(체크리스트 형태), (3) 접힘/펼침을 통한 세부 결과 노출. Claude Code는 터미널 환경에서 React Ink 기반의 ASCII 스피너와 동사형 상태 메시지를 사용하고, Claude.ai 웹에서는 "Thinking" 블록을 접힘/펼침 토글로 제공한다. ChatGPT와 Perplexity는 각각 단계별 진행 표시와 실시간 검색 과정 노출을 통해 대기 시간을 사용자 경험의 일부로 전환하는 전략을 취한다. 핵심 디자인 원칙은 "사용자가 궁금할 때만 세부 정보를 제공하되, 항상 진행 상태를 투명하게 보여주는 것"이다.

---

## 2. 상세 조사 내용

### 2.1 Claude Code 터미널 UI 패턴

#### 2.1.1 기술 스택
- **프레임워크**: React + [Ink](https://github.com/vadimdemedes/ink) (터미널용 React 렌더러)
- **언어**: TypeScript
- **런타임**: Bun
- **레이아웃**: Yoga (Flexbox 레이아웃 엔진)
- 출처: [How Claude Code is built](https://newsletter.pragmaticengineer.com/p/how-claude-code-is-built), [GitHub](https://github.com/anthropics/claude-code)

#### 2.1.2 스피너 (Spinner)
- **형태**: ASCII 문자 기반 회전 애니메이션 (Braille 문자 사용)
- **타이밍**: 50ms 간격의 애니메이션 루프 (v2.1.31에서 격리하여 CPU 오버헤드 감소)
- **표시 내용**: 경과 시간(타이머) + 상태 동사(spinner verb)
- **커스터마이징**: `/config`에서 `spinnerVerbs` 설정으로 사용자 정의 가능 (v2.1.23~)
  - 예: "Thinking...", "Reading...", "Searching..."
- **shimmer 효과**: 사고(thinking) 상태 시 미묘한 shimmer 애니메이션 추가 (v2.1.20)
- 출처: [Claude Code Changelog](https://claudefa.st/blog/guide/changelog), [Reverse Engineering Claude's ASCII Spinner](https://medium.com/@kyletmartinez/reverse-engineering-claudes-ascii-spinner-animation-eec2804626e0) [접근 불가 - Medium 403]

#### 2.1.3 도구 실행 상태 표시
| 상태 | 표시 형태 | 설명 |
|------|-----------|------|
| 실행 중 | `Reading...`, `Searching...` | 동사 진행형 + 스피너 |
| 완료 | `Read`, `Searched` | 과거형/완료형, 스피너 사라짐 |
| 에러 | 에러 메시지 표시 | 빨간색 텍스트 |

- **접힘/펼침**: 읽기/검색 그룹이 접힌 상태에서 "현재 파일/패턴"을 표시 (v2.1.45)
- **도구 호출 형식**: `[Read] /path/to/file.ts`, `[Bash] npm test` 형태의 텍스트 표기
- 출처: [Claude Code Changelog](https://claudefa.st/blog/guide/changelog)

#### 2.1.4 렌더링 최적화
- 초기에는 상태 변경 시 전체 터미널 버퍼를 다시 그려 화면 깜빡임 발생
- 해결: ANSI 이스케이프 시퀀스로 커서 위치를 지정해 상태 줄만 갱신
- 레이아웃 jitter 감소: 스피너 표시/숨김 시 레이아웃 흔들림 수정 (v2.1.31)
- 출처: [GitHub Issue #769](https://github.com/anthropics/claude-code/issues/769)

#### 2.1.5 노력 수준 표시
- 스피너 옆에 "with low effort" 등의 노력 수준 표시 추가
- 출처: [Claude Code Changelog](https://claudefa.st/blog/guide/changelog)

---

### 2.2 Claude.ai 웹 - Thinking 블록 UI

#### 2.2.1 Extended Thinking 토글
- **진입**: 채팅 입력창 좌하단 "Search and tools" 버튼 -> "Extended thinking" 토글
- **활성화 시**: Claude가 답변 전에 내부 추론 과정을 거침
- 출처: [Using Extended Thinking](https://support.claude.com/en/articles/10574485-using-extended-thinking)

#### 2.2.2 Thinking 블록 표시
- **구조**: 답변 위에 "Thinking" 섹션이 별도로 표시됨
- **타이머**: 사고 중일 때 경과 시간 표시 ("Thinking" + 타이머)
- **접힘/펼침**: 클릭으로 Claude의 사고 과정 요약을 펼쳐볼 수 있음
- **내용**: 요약된 추론 과정 표시 (전체 단계가 아닌 압축 버전)
- **시각적 스타일**:
  - 배경: 본문과 구분되는 약간 밝은/어두운 배경 (라이트 모드에서 연한 회색)
  - 브랜드 색상: 보라색(purple) 계열 악센트
  - 폰트: 본문 대비 약간 작은 크기
  - 테두리: 미묘한 border 또는 배경색으로 영역 구분
- 출처: [Claude's Visible Extended Thinking](https://www.anthropic.com/news/visible-extended-thinking)

#### 2.2.3 안전 장치
- 유해한 내용이 포함된 경우: "the rest of the thought process is not available for this response" 메시지로 대체
- 출처: [Claude's Visible Extended Thinking](https://www.anthropic.com/news/visible-extended-thinking)

#### 2.2.4 전반적 디자인 특성
- **레이아웃**: 2열 구조 (좌측 사이드바 + 우측 채팅)
- **색상 테마**: 흰 배경에 검정 텍스트, 보라색 악센트 (다크 모드 지원)
- **디자인 철학**: "유틸리타리안" - 콘텐츠 자체를 돋보이게 하는 절제된 스타일
- 출처: [Conversational AI UI Comparison 2025](https://intuitionlabs.ai/articles/conversational-ai-ui-comparison-2025)

---

### 2.3 ChatGPT 도구 실행 UI 패턴

#### 2.3.1 일반 도구 호출 (검색, 브라우징)
- **상태 텍스트**: "Searching the web...", "Reading [site name]..." 형태
- **시각적 요소**:
  - 작은 글로브 아이콘(웹 검색 시)
  - 회전하는 로딩 스피너
  - 완료 후 참조 출처 표시 (인라인 citation)
- **완료 표시**: 로딩 -> 텍스트 스트리밍으로 자연스럽게 전환
- 출처: [Browsing the Web with ChatGPT Atlas](https://help.openai.com/en/articles/12628371-browsing-the-web-with-chatgpt-atlas)

#### 2.3.2 Deep Research UI
- **단계별 진행**:
  1. Query Decomposition (쿼리 분해)
  2. Agentic Browsing (웹 탐색)
  3. Critical Synthesis (비판적 종합)
  4. Structured Output (구조화된 출력)
  5. Iterative Refinement (반복 개선)
- **실시간 추적**: 연구 진행 상황을 실시간으로 표시
- **중단/조정**: 진행 중 사용자가 "update" 클릭으로 방향 수정 가능
- **소요 시간**: 1~30분 (복잡도에 따라)
- 출처: [Introducing Deep Research](https://openai.com/index/introducing-deep-research/), [Deep Research FAQ](https://help.openai.com/en/articles/10500283-deep-research-faq)

#### 2.3.3 Code Interpreter
- **표시 방식**: 샌드박스 열림 -> 코드 실행 -> 결과/차트/파일을 채팅 내 표시
- **코드 블록**: 구문 강조 + 복사 버튼 + 단일 스페이스 폰트
- 출처: [AI UI Comparison 2025](https://intuitionlabs.ai/articles/conversational-ai-ui-comparison-2025)

#### 2.3.4 모드 선택
- 채팅 인터페이스에서 "Auto", "Fast", "Thinking" 모드 직접 전환 가능
- 각 모드에 따라 다른 수준의 진행 표시
- 출처: [AI UI Comparison 2025](https://intuitionlabs.ai/articles/conversational-ai-ui-comparison-2025)

---

### 2.4 Perplexity AI 도구 실행 UI 패턴

#### 2.4.1 Pro Search 단계별 진행
- **핵심 전략**: 계획(Planning) -> 실행(Execution) 분리
- **UI 흐름**:
  1. 사용자 쿼리 제출
  2. AI가 계획 수립 (step-by-step plan)
  3. 각 단계마다 검색 쿼리 생성 및 실행
  4. 순차적 단계 실행 중 실시간 UI 갱신
  5. 최종 종합 답변 생성
- **소요 시간**: 주제 복잡도에 따라 3~5분
- 출처: [Perplexity Pro Search Case Study](https://www.langchain.com/breakoutagents/perplexity)

#### 2.4.2 시각적 요소
- **확장 가능한 섹션**: 각 검색 단계를 클릭하여 세부 정보 확인 가능
- **인용 상호작용**: 인용에 마우스 호버 시 출처 미리보기 스니펫 표시
- **디자인 원칙**: "사용자가 실제로 궁금해할 때까지 정보를 과다하게 보여주지 않는다. 그 다음, 호기심을 충족시킨다." - William Zhang
- **대기 시간의 UX 전환**: 대기 시간을 기능으로 전환 - 동적 UI 피드백으로 참여도 유지
- 출처: [Perplexity Pro Search Case Study](https://www.langchain.com/breakoutagents/perplexity), [Perplexity UX](https://mttmr.com/2024/01/10/perplexitys-high-bar-for-ux-in-the-age-of-ai/)

---

### 2.5 AI UI 디자인 패턴 이론

#### 2.5.1 The Shape of AI 패턴
- **Stream of Thought**: AI의 논리적 사고 과정, 도구 사용, 결정을 실시간으로 노출
- **Action Plan**: 실행 전에 수행할 단계를 미리 보여줌
- **Controls**: 정보 흐름을 관리하거나 요청을 중간에 일시 중지하여 조정
- **References**: AI가 참조하는 추가 소스를 보고 관리
- 출처: [The Shape of AI](https://www.shapeof.ai)

#### 2.5.2 AWS Cloudscape GenAI 로딩 상태 패턴
- **두 단계**: Processing (프롬프트 수신 후, 생성 전) -> Generation (응답 생성 중)
- **시각적 구성 요소**: 아바타(로딩 상태) + 로딩 바(선형 진행 표시기)
- **텍스트 규칙**:
  - 새 콘텐츠 생성: "Generating [specific artifact]"
  - 기존 콘텐츠 로딩: "Loading" 또는 "Fetching"
  - 끝 문장 부호 없음
- **1초 미만 로딩**: 로딩 상태 표시 생략 (깜빡임 방지)
- **스트리밍**: 텍스트와 인라인 코드에만 사용. 테이블/코드 블록은 로딩 바 사용
- 출처: [Cloudscape GenAI Loading States](https://cloudscape.design/patterns/genai/genai-loading-states/)

#### 2.5.3 Vercel AI SDK 도구 호출 상태 관리
도구 파트(tool part)가 거치는 상태:
| 상태 | 설명 |
|------|------|
| `input-streaming` | 도구 입력이 실시간으로 생성 중 |
| `input-available` | 완전한 도구 입력 준비됨 |
| `output-available` | 도구 실행 성공적 완료 |
| `output-error` | 실행 실패 |
| `approval-requested` | 서버 실행 전 사용자 확인 대기 |

멀티스텝 도구 시퀀스에서는 `step-start` 파트가 단계 전환을 표시:
```tsx
case 'step-start':
  return index > 0 ? <div className="text-gray-500"><hr /></div> : null;
```
- 출처: [AI SDK UI: Chatbot Tool Usage](https://ai-sdk.dev/docs/ai-sdk-ui/chatbot-tool-usage)

#### 2.5.4 Chainlit CoT(Chain of Thought) 표시 모드
- `hidden`: 추론 과정 완전 숨김
- `tool_call`: 도구 호출만 표시
- `full` (기본값): 전체 단계 표시
- `hide_cot=true`일 때 마지막 메시지 아래 로딩 인디케이터 표시
- 출처: [Chainlit UI Config](https://docs.chainlit.io/backend/config/ui)

---

### 2.6 웹 기반 "작업 수행 중" UI 베스트 프랙티스

#### 2.6.1 스피너 vs 프로그레스 바 vs 체크리스트

| 패턴 | 적합한 상황 | 장점 | 단점 |
|------|-------------|------|------|
| **스피너** | 짧은 대기 (2~5초) | 단순, 범용적 | 진행도 파악 불가 |
| **프로그레스 바** | 예측 가능한 진행 | 진행도 시각화 | AI 도구에서 단계 수 예측 어려움 |
| **체크리스트** | 다단계 작업 (검색, 분석, 생성) | 투명성, 단계별 피드백 | 화면 공간 차지 |
| **단계별 타임라인** | 복잡한 리서치 작업 | 과정 전체 가시성 | 오버엔지니어링 위험 |

#### 2.6.2 접힘/펼침 UX 원칙
1. **기본 상태**: 실행 중에는 펼침, 완료 후에는 접힘
2. **사용자 제어**: 언제든 토글 가능
3. **시각적 구분**: 접힘/펼침 상태를 명확히 구분 (chevron 방향 변경)
4. **매끄러운 전환**: height transition으로 부드러운 애니메이션
5. **접근성**: `aria-expanded` 속성, 키보드 네비게이션 지원
6. **정보 계층**: 요약 -> 세부사항의 점진적 공개(progressive disclosure)
- 출처: [Accordion UI Best Practices](https://www.eleken.co/blog-posts/accordion-ui), [LogRocket Accordion Design](https://blog.logrocket.com/ux-design/accordion-ui-design/)

#### 2.6.3 각 단계의 시각적 구분 아이콘

| 상태 | 아이콘 | 색상 | 의미 |
|------|--------|------|------|
| 대기(pending) | `○` 빈 원 | 회색 (`#9CA3AF`) | 아직 시작 전 |
| 실행 중(active) | 회전 스피너 | 인디고/파랑 (`#6366F1`) | 현재 실행 중 |
| 완료(completed) | `✓` 체크마크 | 초록 (`#22C55E`) | 성공적 완료 |
| 에러(error) | `✗` 엑스 | 빨강 (`#EF4444`) | 실행 실패 |

---

### 2.7 CSS 구현 참고사항

#### 2.7.1 회전 스피너 (CSS Only)

```css
/* 기본 원형 스피너 */
.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid #6366F1;      /* indigo-500 */
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

Tailwind CSS 버전:
```html
<span class="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
```

#### 2.7.2 바운싱 점 3개 (Typing Indicator)

```css
.typing-dots {
  display: flex;
  gap: 4px;
  align-items: center;
}

.typing-dots span {
  width: 8px;
  height: 8px;
  background: #6B7280;
  border-radius: 50%;
  animation: bounceDot 1.4s ease-in-out infinite;
}

.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounceDot {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
```

Tailwind Config 버전:
```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      keyframes: {
        bounceDot: {
          '0%, 80%, 100%': { transform: 'scale(0)' },
          '40%': { transform: 'scale(1)' },
        },
      },
      animation: {
        'bounce-dot-1': 'bounceDot 1.4s infinite ease-in-out',
        'bounce-dot-2': 'bounceDot 1.4s infinite ease-in-out 0.2s',
        'bounce-dot-3': 'bounceDot 1.4s infinite ease-in-out 0.4s',
      },
    },
  },
}
```
- 출처: [Tailwind CSS Loading Dots](https://dev.to/ankitvermaonline/create-loading-dots-animations-in-tailwind-css-2o3l)

#### 2.7.3 점진적 점 추가 (Loading...)

```javascript
// tailwind.config.js
keyframes: {
  dotLoop: {
    '0%':   { content: '"."' },
    '25%':  { content: '".."' },
    '50%':  { content: '"..."' },
    '75%':  { content: '""' },
    '100%': { content: '"."' },
  },
},
animation: {
  dotLoop: 'dotLoop 1.5s steps(1,end) infinite',
}
```

```html
<span class="text-gray-500">
  Loading<span class="after:animate-dotLoop after:content-['']"></span>
</span>
```
- 출처: [Tailwind CSS Loading Dots](https://dev.to/ankitvermaonline/create-loading-dots-animations-in-tailwind-css-2o3l)

#### 2.7.4 접힘/펼침 (Collapsible/Accordion)

```css
/* 순수 CSS 접힘/펼침 */
.collapsible-content {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.3s ease-out;
}

.collapsible-content.open {
  max-height: 500px; /* 충분히 큰 값 */
  transition: max-height 0.5s ease-in;
}

/* 또는 HTML <details>/<summary> 활용 */
details summary {
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 8px;
}

details summary::-webkit-details-marker {
  display: none;
}

details[open] summary .chevron {
  transform: rotate(180deg);
}

.chevron {
  transition: transform 0.2s ease;
}
```

React 구현 패턴:
```tsx
function CollapsibleStep({ title, children, defaultOpen = false }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border-l-2 border-gray-200 pl-4">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-sm"
        aria-expanded={isOpen}
      >
        <svg
          className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          viewBox="0 0 24 24" fill="none" stroke="currentColor"
        >
          <path d="M19 9l-7 7-7-7" />
        </svg>
        <span>{title}</span>
      </button>
      {isOpen && (
        <div className="mt-2 ml-6">{children}</div>
      )}
    </div>
  );
}
```

#### 2.7.5 스트리밍 커서 (Blinking Cursor)

```css
.streaming-cursor::after {
  content: '\2588';  /* 블록 커서 (Block) */
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}
```

#### 2.7.6 Shimmer 효과 (Thinking 상태)

```css
.thinking-shimmer {
  background: linear-gradient(
    90deg,
    #f1f5f9 25%,
    #e2e8f0 50%,
    #f1f5f9 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 다크모드 */
.dark .thinking-shimmer {
  background: linear-gradient(
    90deg,
    #1e293b 25%,
    #334155 50%,
    #1e293b 75%
  );
  background-size: 200% 100%;
}
```

#### 2.7.7 단계별 체크리스트 전체 예시 (종합)

```css
/* 프로그레스 스텝 컨테이너 */
.progress-steps {
  margin: 8px 0;
}

/* 토글 버튼 */
.progress-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: #6B7280;
  cursor: pointer;
  border: none;
  background: none;
  padding: 4px 0;
  transition: color 0.15s;
}

.progress-toggle:hover {
  color: #374151;
}

/* 단계 목록 */
.step-list {
  margin-left: 24px;
  margin-top: 8px;
  padding-left: 16px;
  border-left: 2px solid #E5E7EB;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 개별 단계 */
.step-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 0.875rem;
}

/* 단계 아이콘 */
.step-icon {
  flex-shrink: 0;
  margin-top: 2px;
  width: 14px;
  height: 14px;
}

.step-icon--pending { color: #D1D5DB; }
.step-icon--active { color: #6366F1; }
.step-icon--completed { color: #22C55E; }
.step-icon--error { color: #EF4444; }

/* 단계 텍스트 */
.step-title {
  color: #374151;
}

/* 결과 카운트 */
.step-count {
  margin-left: 6px;
  font-size: 0.75rem;
  color: #9CA3AF;
}

/* 미리보기 */
.step-preview {
  margin-top: 2px;
  font-size: 0.75rem;
  color: #9CA3AF;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
```

---

## 3. 프로젝트 현황 분석

### 3.1 현재 구현 상태

프로젝트의 `chatbot-demo/frontend/` 에 이미 도구 실행 진행 표시 UI가 구현되어 있다.

**파일**: `/mnt/c/Users/qorud/Desktop/my-boat-shop/chatbot-demo/frontend/src/components/message-parts/ProgressSteps.tsx`

현재 구현된 기능:
- 스피너: `animate-spin` + `border-2 border-indigo-500 border-t-transparent` (CSS 원형 스피너)
- 체크마크: `&#10003;` (녹색), 엑스: `&#10007;` (빨간색), 대기: `&#9675;` (회색)
- 접힘/펼침: 모든 단계 완료 시 자동 접힘, 클릭으로 토글
- 카운터: "작업 수행 중... (N/M)" / "N개 작업 완료"
- 왼쪽 세로줄: `border-l-2 border-gray-200` (단계 목록 좌측 연결선)
- 미리보기: 문자열 또는 `[{icon, text, sub}]` 배열 형태 지원
- chevron 아이콘: 펼침 시 180도 회전

**파일**: `/mnt/c/Users/qorud/Desktop/my-boat-shop/chatbot-demo/frontend/src/app/globals.css`

현재 구현된 관련 CSS:
- 스트리밍 커서: `.streaming-cursor::after` 블링크 애니메이션
- 다크모드 지원: CSS 변수 기반
- 테이블/버튼 스타일: HTML 블록 내부 요소

**파일**: `/mnt/c/Users/qorud/Desktop/my-boat-shop/chatbot-demo/frontend/src/components/chat/AssistantMessage.tsx`

- `progress` 타입 파트에 대해 `ProgressSteps` 컴포넌트 렌더링
- `text` 타입에 `streaming-cursor` 클래스 적용

### 3.2 이미 적용된 것

| 기능 | 상태 | 비고 |
|------|------|------|
| 원형 스피너 (실행 중) | 적용됨 | indigo 색상 |
| 체크마크 (완료) | 적용됨 | 녹색 유니코드 |
| 에러 표시 | 적용됨 | 빨간색 X |
| 대기 상태 | 적용됨 | 회색 빈 원 |
| 접힘/펼침 토글 | 적용됨 | 자동 접힘 포함 |
| 진행 카운터 | 적용됨 | (N/M) 형식 |
| 왼쪽 연결선 | 적용됨 | border-l-2 |
| 미리보기 | 적용됨 | 문자열/배열 |
| 스트리밍 커서 | 적용됨 | 블링크 애니메이션 |
| 다크모드 | 적용됨 | CSS 변수 기반 |

### 3.3 추가 적용 가능한 개선사항

| 기능 | 우선순위 | 참고 |
|------|----------|------|
| Shimmer 애니메이션 (사고 중 상태) | 중간 | Claude Code v2.1.20에서 도입된 패턴 |
| 부드러운 접힘/펼침 트랜지션 | 높음 | 현재 즉시 표시/숨김 -> height transition 추가 |
| Thinking 블록 (별도 섹션) | 중간 | Claude.ai 스타일 사고 과정 표시 영역 |
| 바운싱 점 타이핑 인디케이터 | 낮음 | 현재 스트리밍 커서로 대체 가능 |
| `aria-expanded` 접근성 속성 | 높음 | 현재 미적용 |
| 단계 간 수평선 구분 | 낮음 | Vercel AI SDK의 step-start 패턴 |
| 도구 호출 알림 스타일 | 낮음 | Claude Code의 brief notification 패턴 |
| 1초 미만 로딩 생략 | 중간 | Cloudscape 패턴 - 깜빡임 방지 |

---

## 4. 참고 자료

### 공식 문서 / 1차 자료
- [Claude Code GitHub Repository](https://github.com/anthropics/claude-code) - Claude Code 오픈소스 저장소
- [Claude Code Changelog](https://claudefa.st/blog/guide/changelog) - 스피너, 진행 표시 관련 업데이트 이력
- [GitHub Issue #769](https://github.com/anthropics/claude-code/issues/769) - 터미널 렌더링 깜빡임 이슈와 해결
- [Claude's Visible Extended Thinking](https://www.anthropic.com/news/visible-extended-thinking) - 사고 과정 가시화 발표
- [Using Extended Thinking](https://support.claude.com/en/articles/10574485-using-extended-thinking) - Extended Thinking 사용 가이드
- [Browsing the Web with ChatGPT Atlas](https://help.openai.com/en/articles/12628371-browsing-the-web-with-chatgpt-atlas) - ChatGPT 웹 브라우징 UI
- [Introducing Deep Research](https://openai.com/index/introducing-deep-research/) - ChatGPT Deep Research 소개
- [AI SDK UI: Chatbot Tool Usage](https://ai-sdk.dev/docs/ai-sdk-ui/chatbot-tool-usage) - Vercel AI SDK 도구 호출 UI
- [Cloudscape GenAI Loading States](https://cloudscape.design/patterns/genai/genai-loading-states/) - AWS 디자인 시스템 GenAI 로딩 패턴

### 디자인 패턴 / 2차 자료
- [The Shape of AI](https://www.shapeof.ai) - AI UX 패턴 레퍼런스
- [AI UI Patterns (patterns.dev)](https://www.patterns.dev/react/ai-ui-patterns/) - React AI UI 패턴
- [Perplexity Pro Search Case Study](https://www.langchain.com/breakoutagents/perplexity) - Perplexity 단계별 UI 분석
- [Conversational AI UI Comparison 2025](https://intuitionlabs.ai/articles/conversational-ai-ui-comparison-2025) - 주요 AI 챗봇 UI 비교
- [Chainlit UI Configuration](https://docs.chainlit.io/backend/config/ui) - Chainlit CoT 표시 설정

### CSS 구현 참고
- [Tailwind CSS Loading Dots](https://dev.to/ankitvermaonline/create-loading-dots-animations-in-tailwind-css-2o3l) - 바운싱 점 애니메이션
- [Accordion UI Best Practices](https://www.eleken.co/blog-posts/accordion-ui) - 접힘/펼침 디자인 가이드
- [LogRocket Accordion Design](https://blog.logrocket.com/ux-design/accordion-ui-design/) - 아코디언 UX/구현 가이드
- [W3Schools Accordion](https://www.w3schools.com/howto/howto_js_accordion.asp) - 기본 아코디언 구현

### 접근 불가 [커뮤니티 출처]
- [Reverse Engineering Claude's ASCII Spinner](https://medium.com/@kyletmartinez/reverse-engineering-claudes-ascii-spinner-animation-eec2804626e0) - Medium 403 차단
- [Claude Code Spinner Verbs](https://medium.com/@joe.njenga/claude-code-2-1-23-is-out-with-spinner-verbs-i-tested-it-ae94a6325f79) - Medium 403 차단
- [Claude Code Internals Part 11: Terminal UI](https://kotrotsos.medium.com/claude-code-internals-part-11-terminal-ui-542fe17db016) - Medium 403 차단

---

## 5. 추가 조사 필요 사항

- [높음] Claude.ai 웹에서 Thinking 블록의 정확한 CSS 스타일 (배경색, 보더, 여백 수치) - 브라우저 DevTools로 직접 검사 필요
- [높음] ChatGPT가 "Searching the web..." 표시 시 사용하는 정확한 애니메이션 및 아이콘 - 브라우저 DevTools로 직접 검사 필요
- [중간] Vercel AI Chatbot 템플릿(github.com/vercel/chatbot)의 도구 호출 렌더링 컴포넌트 소스코드 상세 분석
- [중간] Claude Code의 Ink 컴포넌트 구조 상세 분석 (소스코드가 난독화되어 있어 제한적)
- [낮음] Google Gemini의 "Deep Research" 모드 UI 패턴 비교 분석
- [낮음] OpenAI Codex의 실시간 작업 진행 UI 상세 조사
