
extra_data = {
    "기간": { "시작일": "2023년1월", "종료일": "2025년1월"},
    "전체선택여부": True | False,
    "범위": [
        {
            "상위항목": "결재 문서",
            "하위항목": [],
        },
        {
            "상위항목": "지식",
            "하위항목": ["지식 허브","내부 법령 센터"],
        }
    ],
}

print (f"extra_data= {extra_data['기간']['시작일']}")
print (f"extra_data= {extra_data['기간']['종료일']}")
print (f"전체선택여부= {extra_data['전체선택여부']}")
for x in extra_data["범위"]:
    print (f"x['상위항목']= {x['상위항목']}")
    print (f"x['하위항목']= {x['하위항목']}")

# if extra_data["범위"]["전체선택"] == False:4

# else:

