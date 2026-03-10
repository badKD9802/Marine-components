#!/bin/bash

# 1. k6의 모든 출력을 저장할 임시 파일을 생성합니다.
TEMP_LOG=$(mktemp)

# 2. k6를 실행하고 모든 출력(stdout, stderr)을 임시 파일에 저장합니다.
#    --quiet를 사용하여 console.log 외의 로그를 최소화합니다.
echo "------------------- K6 TEST START -------------------"
# sudo docker run -i --rm -v $(pwd):/scripts grafana/k6 run --quiet /scripts/chat_stream_loadtest_v1.js 2>&1 | tee "$TEMP_LOG"
# docker run -i --rm --add-host chatsam.sparklingsoda.ai:210.116.106.116 -v $(pwd):/scripts grafana/k6 run --quiet /scripts/rag_load.js 2>&1 | sed 's/http_req_waiting/time_to_first_chunk/g' | tee "$TEMP_LOG"
sudo docker run -i --rm --add-host ai.e-kamco.com:172.16.4.119 -v $(pwd):/scripts grafana/k6 run --quiet /scripts/rag_load.js 2>&1 | sed 's/http_req_waiting/time_to_first_chunk/g' | tee "$TEMP_LOG"

{
    echo "번호,질문,첫문자,전체응답,대기시간"
    grep 'msg=' "$TEMP_LOG" | awk -F'msg="' '{print $2}' | awk -F'" source=' '{print $1}'
} > rag_result.csv

{
    echo ""
    echo "------------------- K6 FINAL RESULTS -------------------"
    sed -n '/THRESHOLDS/,$p' "$TEMP_LOG"
} >> rag_result.csv

# 3. 임시 파일 삭제
rm "$TEMP_LOG"

