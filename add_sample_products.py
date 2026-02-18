#!/usr/bin/env python3
"""data.js의 샘플 상품 2개를 DB에 추가하는 스크립트"""

import requests
import json

API_BASE = 'https://marine-parts-production-60a3.up.railway.app'

# 로그인
password = input("관리자 비밀번호 입력 (4781): ")
login_response = requests.post(f'{API_BASE}/admin/login', json={'password': password})
if login_response.status_code != 200:
    print(f"❌ 로그인 실패: {login_response.status_code}")
    exit(1)

token = login_response.json()['token']
print(f"✅ 로그인 성공")

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# 상품 1: 얀마 커넥팅 로드 베어링
product1 = {
    "image": "./parts_image/YANMAR CON BOD BEARING(4TNV98 129900-23600).jpg",
    "part_no": "4TNV98 129900-23600",
    "price": "2,000",
    "brand": "YANMAR",
    "category": "bearing",
    "name": {
        "ko": "얀마 커넥팅 로드 베어링",
        "en": "YANMAR CON ROD BEARING",
        "cn": "YANMAR 连杆轴承"
    },
    "description": {
        "ko": "4TNV98 엔진 호환",
        "en": "Compatible with 4TNV98",
        "cn": "兼容 4TNV98"
    },
    "category_name": {
        "ko": "베어링",
        "en": "Bearing",
        "cn": "轴承"
    },
    "detail_info": {
        "ko": "YANMAR 4TNV98 엔진에 사용되는 고품질 커넥팅 로드 베어링입니다. 정밀 가공으로 엔진 내구성과 성능을 보장하며, 순정품과 동일한 규격으로 제작되었습니다. 장기간 안정적인 운전을 위한 필수 교체 부품입니다.",
        "en": "High-quality connecting rod bearing for YANMAR 4TNV98 engines. Precision-machined to ensure engine durability and performance, manufactured to OEM specifications. An essential replacement part for long-term stable operation.",
        "cn": "适用于YANMAR 4TNV98发动机的高品质连杆轴承。精密加工确保发动机耐久性和性能，按OEM规格制造。是长期稳定运行的必备更换零件。"
    },
    "specs": {
        "ko": {
            "부품번호": "4TNV98 129900-23600",
            "브랜드": "YANMAR",
            "카테고리": "베어링",
            "호환 엔진": "4TNV98",
            "상태": "신품",
            "원산지": "일본"
        },
        "en": {
            "Part Number": "4TNV98 129900-23600",
            "Brand": "YANMAR",
            "Category": "Bearing",
            "Compatible Engine": "4TNV98",
            "Condition": "New",
            "Origin": "Japan"
        },
        "cn": {
            "零件编号": "4TNV98 129900-23600",
            "品牌": "YANMAR",
            "类别": "轴承",
            "兼容发动机": "4TNV98",
            "状态": "全新",
            "产地": "日本"
        }
    },
    "compatibility": {
        "ko": ["YANMAR 4TNV98 시리즈", "YANMAR 4TNV98T 터보"],
        "en": ["YANMAR 4TNV98 Series", "YANMAR 4TNV98T Turbo"],
        "cn": ["YANMAR 4TNV98 系列", "YANMAR 4TNV98T 涡轮"]
    }
}

# 상품 2: 마린 디젤 엔진 플런저 베럴
product2 = {
    "image": "./parts_image/YANMAR EY18AL.jpg",
    "part_no": "PB1002 / PB1003",
    "price": "400,000",
    "brand": "YANMAR",
    "category": "plunger",
    "name": {
        "ko": "마린 디젤 엔진 플런저 베럴",
        "en": "YANMAR EY18AL Plunger",
        "cn": "YANMAR EY18AL 柱塞"
    },
    "description": {
        "ko": "AL-SERIES / AL-PLUS 모델",
        "en": "AL-SERIES / AL-PLUS",
        "cn": "AL-SERIES / AL-PLUS"
    },
    "category_name": {
        "ko": "플런저",
        "en": "Plunger",
        "cn": "柱塞"
    },
    "detail_info": {
        "ko": "YANMAR EY18AL 엔진용 연료 분사 플런저 베럴입니다. AL-SERIES 및 AL-PLUS 모델에 호환되며, 정밀한 연료 분사를 통해 엔진 효율을 극대화합니다. 고내구성 소재로 장시간 사용에도 안정적인 성능을 유지합니다.",
        "en": "Fuel injection plunger barrel for YANMAR EY18AL engines. Compatible with AL-SERIES and AL-PLUS models, maximizing engine efficiency through precise fuel injection. Made with high-durability materials for reliable performance over extended use.",
        "cn": "适用于YANMAR EY18AL发动机的燃油喷射柱塞筒。兼容AL-SERIES和AL-PLUS型号，通过精确燃油喷射最大化发动机效率。采用高耐久性材料，长时间使用仍保持稳定性能。"
    },
    "specs": {
        "ko": {
            "부품번호": "PB1002 / PB1003",
            "브랜드": "YANMAR",
            "카테고리": "플런저",
            "호환 모델": "EY18AL, AL-SERIES, AL-PLUS",
            "상태": "신품",
            "원산지": "일본"
        },
        "en": {
            "Part Number": "PB1002 / PB1003",
            "Brand": "YANMAR",
            "Category": "Plunger",
            "Compatible Model": "EY18AL, AL-SERIES, AL-PLUS",
            "Condition": "New",
            "Origin": "Japan"
        },
        "cn": {
            "零件编号": "PB1002 / PB1003",
            "品牌": "YANMAR",
            "类别": "柱塞",
            "兼容型号": "EY18AL, AL-SERIES, AL-PLUS",
            "状态": "全新",
            "产地": "日本"
        }
    },
    "compatibility": {
        "ko": ["YANMAR EY18AL", "YANMAR AL-SERIES", "YANMAR AL-PLUS"],
        "en": ["YANMAR EY18AL", "YANMAR AL-SERIES", "YANMAR AL-PLUS"],
        "cn": ["YANMAR EY18AL", "YANMAR AL-SERIES", "YANMAR AL-PLUS"]
    }
}

# 상품 추가
for i, product in enumerate([product1, product2], 1):
    print(f"\n📦 상품 {i} 추가 중: {product['name']['ko']}")
    response = requests.post(
        f'{API_BASE}/admin/products',
        headers=headers,
        json=product
    )

    if response.status_code == 200:
        print(f"✅ 추가 성공: {response.json()}")
    else:
        print(f"❌ 추가 실패: {response.status_code}")
        print(f"   응답: {response.text}")

print("\n🎉 완료!")
