import http from 'k6/http';
import { sleep } from 'k6';

// 질문 리스트
const QUESTIONS = [
        "대한민국이 대부분의 지형이 산으로 이루어진 이유와 지형적 장점에 대해서 설명해줘",
        "바나나가 자라는 나라의 특징에 대해서 자세히 설명해줘",
        "구글이라는 회사에 대한 정보와 하는 일에 대해서 설명해줘",
        "대한민국의 사계절이 뚜렷한 이유에 대해서 설명해줘",
        "달의 뒷면을 볼 수 없는 이유와 뒷면에는 무엇이 있는지에 대해서 설명해줘",
        "AI와 ML의 차이에 대해서 설명해줘",
        "우주의 행성들이 둥근 이유에 대해서 설명해줘",
        "물이 끓는 온도와 기름이 끓는 온도가 다른 이유에 대해서 설명해줘",
        "RAG에 대해서 자세히 설명해줘",
        "지구와 달의 거리가 일정하게 유지되는 이유와 그 거리에 대해서 설명해줘",
        "삼성에서 만든 휴대폰 종류와 특징에 대해서 설명해줘",
        "전기가 어떻게 만들어지는지에 대해서 자세히 설명해줘",
        "바다에 소금이 존재하는 이유에 대해서 설명해줘",
        "우리가 심해를 탐사할 수 있는 깊이에 대해서 설명해주고 그 이상으로 탐사하지 못하는 이유에 대해서 알려줘",
        "구름이 생기는 원리에 대해서 설명해주고 비가 내리는 이유도 알려줘",
        "무지개가 생기는 원리에 대해서 설명해주고 인공적으로 만들수 있는 방법 알려줘",
        "국가가 섬으로 되어있을때의 장점과 단점에 대해서 설명해줘",
        "인터넷이 연결되는 원리에 대해서 자세히 설명해줘",
        "북극이 녹고있는 이유와 북극이 녹았을 때의 지구에 벌어지는 일에 대해서 설명해줘",
        "바다와 호수의 차이는 뭐야?",
  ];

const TARGET_INTERVAL = 70_000;
const MAX_REQUESTS_PER_SESSION = 1;

export let options = {
    vus: 200,            // 동시 접속 사용자 수
    duration: '5m',     // 1m 테스트 지속 시간
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
          "type": "llm_question",
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
        'https://ai.e-kamco.com:31080/api/api/v1/agent/chat',
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
