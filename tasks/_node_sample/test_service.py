import json

import requests


def send_post_request():
    url = "http://localhost:8100/api/v1/chat/predict"
    headers = {"Content-Type": "application/json"}

    payload = {
        "site": "kriss",  # 현재 러닝 중인 서비스 (running platform으로 활용)
        "req_type": "question",
        "req_items": [{"name": "svc_name", "value": "kriss_sum"}],  # 새로 만든 변수명.  # 실제로 call할 서비스 명.
        "use_llm": False,
        "is_api": False,
        "question": "ChunkStudio란?",  # 서버에게 전달할 질문
        "chunk_cnt": None,
        "search_param": None,
        "user_id": "admin",
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))

        if response.status_code == 200:
            print("Response received successfully:")
            print(json.dumps(response.json(), indent=4, ensure_ascii=False))
        else:
            print(f"Failed to fetch response. HTTP Status Code: {response.status_code}")
            print("Response:", response.text)
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    send_post_request()
