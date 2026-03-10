import http from 'k6/http';
import { sleep } from 'k6';

// 질문 리스트
const QUESTIONS = [
    "재산을 철거할 때 발생한 비용은 어떤 계정과목으로 처리해야해?",
    "채권업무 중 강제집행에 대해 알려줘",
    "채권업무 중 보증채무에 대한 시효 중단에 대해 알려줘",
    "주택 소액임차인의 기준 및 최우선변제액 알려줘",
    "출장비 상한선에 대해서 알려줘",
    "국유 직원 출장 결재는 어떻게 올려야해?",
    "계약서 작성을 생략할 수 있는 경우에 대해 알려줘",
    "시간외 근무수당 및 보상휴가 세칙의 주요 개정 내용이 뭐야",
    "국유재산 내 폐기물 처리 의무",
    "대부 기간이 끝났는데 건물 매각을 위해 계약 연장을 거부해도 돼?",
    "올해 건강검진 일정에 대해 설명해줘",
    "시외출장일 경우 출장문서 결재라인이 어떻게 돼?",
    "출장가서 숙박비는 얼마 지원되는지 알려줘",
    "채무조정 분할상환 관련 규정 어디있어?",
    "기초생활수급자 감면 규정 어디 나와있는지 알려줘",
    "연대보증인의 시효에 대해 설명해줘",
    "주택 소액임차인 기준별 최우선변제액 알려줘",
    "공매 해제 협의내용 알려줘",
    "법인 송달 판례에 대해  알려줘",
    "매각대금 분납 기준이 어떻게 돼?",
  ];

const TARGET_INTERVAL = 70_000;
const MAX_REQUESTS_PER_SESSION = 1;

export let options = {
    vus: 1,            // 동시 접속 사용자 수
    duration: '1m',     // 1m 테스트 지속 시간
//    gracefulStop: '120s',
    thresholds: {
        'http_req_waiting': ['avg<5000', 'min<5000','max<100000', 'p(95)<8000'],
    },
};

// 공통 헤더
const params = {
    timeout: '300s',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
};

function generateSessionId() {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let randomStr = '';
    for (let i = 0; i < 17; i++) {
      randomStr += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return 'AS_' + randomStr; // 총 20자
}

let sessionState = {};  // VU ID별 세션정보 저장

export default function () {
    const vuId = __VU;  // 현재 가상사용자(VU)의 고유 ID (1~200)
    const iter = __ITER;

    // 현재 VU의 상태가 없다면 새 세션 생성
    if (!sessionState[vuId]) {
      sessionState[vuId] = {
        session_id: generateSessionId(),
        requestCount: 0,
      };
    }

    // MAX_REQUESTS_PER_SESSION회 요청 시 새 세션 갱신
    if (sessionState[vuId].requestCount >= MAX_REQUESTS_PER_SESSION) {
      sessionState[vuId].session_id = generateSessionId();
      sessionState[vuId].requestCount = 0;
    }

    // 현재 session_id 사용
    const sessionId = sessionState[vuId].session_id;
    sessionState[vuId].requestCount++;

    const start = Date.now();
    // const idx = __ITER % QUESTIONS.length;  // 현재 iteration 번호 (__ITER)은 0부터 시작, QUESTIONS 배열 길이로 모듈로 연산 → 순환 접근
    const idx = Math.floor(Math.random() * QUESTIONS.length);
    const question = QUESTIONS[idx];

    // 요청 Body (테스트 입력값)
    const payload = JSON.stringify({
      "key": "1234TPMTESTabc",
      "type": "stream",
      "service_name": "kamco",
      "task_name": "multi_turn_stream",
      "session_id": sessionId,
      "messages": [
        {
          "type": "question",
          "content": question,
          "percentage": 0,
          "created_at": new Date().toISOString(),
          "extra_data": {
            "date_range": {
              "start_date": "2024-11",
              "end_date": "2025-11"
            },
            "is_all_doc_type": true,
            "doc_range": [
              {
                "doc_type": "approval",
                "list_item": []
              },
              {
                "doc_type": "notice_board",
                "list_item": []
              },
              {
                "doc_type": "kms",
                "list_item": [
                  "지식 허브",
                  "내규 법령 센터",
                  "Q&A 데스크"
                ]
              }
            ]
          }
        }
      ]
    });

    // POST 요청 (SSE 스트리밍 응답)
    const res = http.post(
        // 'http://6.5.72.248:8000/api/api/v1/agent/chat',    // loki
        // 'http://6.5.192.163:8088/api/v1/agent/chat',       // loki_app
        // 'http://172.16.4.118:31080/api/api/v1/agent/chat',
        // 'http://ai.e-kamco.com:31080/api/api/v1/agent/chat',
        // 'https://ai.e-kamco.com:31080/api/api/v1/agent/chat',
        // 'http://chatsam.sparklingsoda.ai/api/api/v1/agent/chat',
        'https://chatsam.e-kamco.com/api/api/v1/agent/chat',
        payload,
        params
    );

    // 메트릭 값들
    const ttfb = res.timings.waiting.toFixed(0);   // 첫문자
    const total = res.timings.duration.toFixed(0); // 전체응답
    const elapsed = Date.now() - start;
    const remain = TARGET_INTERVAL - elapsed;
    const wait = remain > 0 ? remain.toFixed(0) : 0;

    console.log(`${__ITER},"${question}",${ttfb},${total},${wait}`);

    if (remain > 0) sleep(remain / 1000);
}
