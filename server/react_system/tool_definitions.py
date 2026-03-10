"""OpenAI function calling schemas for KAMCO tools (21개 - RAG + 번역 + HTML포맷(달력+표) 추가)."""

TOOLS = [
    # 1. Schedule Management (4 tools)
    {
        "type": "function",
        "function": {
            "name": "get_schedule",
            "description": "사용자의 일정을 조회합니다. 특정 날짜, 기간, 또는 키워드로 검색할 수 있습니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "조회할 날짜 (YYYY-MM-DD 또는 '오늘', '내일' 등)",
                    },
                    "date_range_start": {
                        "type": "string",
                        "description": "조회 시작 날짜 (YYYY-MM-DD). 기간 조회 시 사용",
                    },
                    "date_range_end": {
                        "type": "string",
                        "description": "조회 종료 날짜 (YYYY-MM-DD). 기간 조회 시 사용",
                    },
                    "title": {"type": "string", "description": "일정 제목으로 검색"},
                    "calendar_name": {
                        "type": "string",
                        "description": "특정 달력에서 조회 (예: 나의달력, 업무달력)",
                    },
                    "cal_id": {
                        "type": "string",
                        "description": "일정 번호로 조회 (예: 1번, 2번)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_schedule",
            "description": """새로운 일정을 등록합니다.

**충돌 확인:** 해당 시간에 기존 일정이 있으면 status="conflict"를 반환합니다.
- conflict 반환 시: 사용자에게 기존 일정 정보를 보여주고 등록 여부를 확인하세요.
- 사용자가 등록을 원하면 force=true로 다시 호출하세요.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "일정 제목"},
                    "date": {
                        "type": "string",
                        "description": "일정 날짜 (YYYY-MM-DD 또는 '오늘', '내일' 등)",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "시작 시간 (HH:MM 또는 '오후 3시' 등)",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "종료 시간 (HH:MM 또는 '오후 4시' 등)",
                    },
                    "description": {"type": "string", "description": "일정 상세 내용"},
                    "calendar_name": {
                        "type": "string",
                        "description": "달력 이름 (예: 나의달력, 업무달력). 생략 시 기본 달력 사용",
                    },
                    "force": {
                        "type": "boolean",
                        "description": "true이면 시간 충돌을 무시하고 강제 등록. 사용자가 충돌을 확인하고 등록을 원할 때만 사용",
                    },
                },
                "required": ["title", "date", "start_time", "end_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_schedule",
            "description": "기존 일정을 변경합니다. 변경하려는 필드만 전달합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cal_id": {
                        "type": "string",
                        "description": "변경할 일정 번호 (예: 1번, 2번)",
                    },
                    "title": {
                        "type": "string",
                        "description": "기존 일정 제목 (검색용)",
                    },
                    "title_chg": {"type": "string", "description": "변경할 새 제목"},
                    "date": {
                        "type": "string",
                        "description": "변경할 날짜 (YYYY-MM-DD 또는 '내일' 등)",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "변경할 시작 시간 (HH:MM 또는 '오후 3시' 등)",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "변경할 종료 시간 (HH:MM 또는 '오후 4시' 등)",
                    },
                    "description": {
                        "type": "string",
                        "description": "변경할 상세 내용",
                    },
                    "calendar_name": {"type": "string", "description": "달력 이름"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_schedule",
            "description": "일정을 삭제합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cal_id": {
                        "type": "string",
                        "description": "삭제할 일정 번호 (예: 1번, 2번)",
                    },
                    "title": {"type": "string", "description": "삭제할 일정 제목"},
                    "date": {"type": "string", "description": "삭제할 일정 날짜"},
                    "start_time": {
                        "type": "string",
                        "description": "삭제할 일정 시작 시간",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "삭제할 일정 종료 시간",
                    },
                    "calendar_name": {"type": "string", "description": "달력 이름"},
                },
                "required": [],
            },
        },
    },
    # 2. Meeting Room Management (5 tools)
    {
        "type": "function",
        "function": {
            "name": "get_meeting_room_list",
            "description": "회의실 목록을 조회합니다 (예약 정보 제외). 회의실 이름, 위치, 수용인원, 시설 정보를 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "floor": {
                        "type": "integer",
                        "description": "층수로 필터링 (예: 8)",
                    },
                    "min_capacity": {
                        "type": "integer",
                        "description": "최소 수용 인원 (예: 10)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reserve_meeting_room",
            "description": "회의실을 예약합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "meetingroom": {
                        "type": "string",
                        "description": "회의실 이름 (예: 8층 영상회의실, 대회의실, 전산교육실)",
                    },
                    "title": {"type": "string", "description": "회의 제목"},
                    "date": {
                        "type": "string",
                        "description": "예약 날짜 (YYYY-MM-DD 또는 '오늘', '내일' 등)",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "시작 시간 (HH:MM 또는 '오후 3시' 등)",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "종료 시간 (HH:MM 또는 '오후 4시' 등)",
                    },
                    "description": {
                        "type": "string",
                        "description": "회의 내용 상세 설명",
                    },
                    "calendar_name": {
                        "type": "string",
                        "description": "달력 이름 (예: 나의달력, 업무달력)",
                    },
                },
                "required": ["meetingroom", "title", "date", "start_time", "end_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_meeting_rooms",
            "description": """특정 회의실의 예약 현황을 조회합니다. 회의실 이름을 반드시 지정해야 합니다.

여러 회의실을 조회할 때는 이 도구를 회의실별로 각각 호출하세요.
예: "8층 영상회의실이랑 대회의실" → get_meeting_rooms(meetingroom="8층 영상회의실") + get_meeting_rooms(meetingroom="대회의실")

'이번주', '다음주' 등 기간 조회는 date_range_start/date_range_end를 사용하세요.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "meetingroom": {
                        "type": "string",
                        "description": "회의실 이름 (필수, 예: 8층 영상회의실, 대회의실, 전산교육실)",
                    },
                    "date": {
                        "type": "string",
                        "description": "특정 날짜 조회 (YYYY-MM-DD 또는 '오늘', '내일' 등). 기간 조회 시에는 date_range_start/end 사용",
                    },
                    "date_range_start": {
                        "type": "string",
                        "description": "기간 시작 날짜 (예: '이번주', '다음주', '2026-03-03'). '이번주'=이번주 월~금",
                    },
                    "date_range_end": {
                        "type": "string",
                        "description": "기간 종료 날짜 (예: '이번주 금요일', '2026-03-07'). 생략 시 시작 주의 금요일",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "조회 시작 시간 (HH:MM, 선택)",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "조회 종료 시간 (HH:MM, 선택)",
                    },
                },
                "required": ["meetingroom"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_meeting_rooms",
            "description": """전체 회의실의 예약 현황을 한번에 조회합니다.

**반드시 이 도구를 사용해야 하는 경우:**
- "전체 회의실 현황 알려줘"
- "모든 회의실 예약 보여줘"
- "회의실 전부 조회해줘"
→ 사용자가 '전체', '모든', '전부' 등으로 모든 회의실을 요청할 때만 사용

**이 도구를 사용하면 안 되는 경우:**
- "8층 영상회의실이랑 대회의실 알려줘" → get_meeting_rooms를 2번 각각 호출
- "대회의실 예약 현황" → get_meeting_rooms(meetingroom="대회의실")
→ 특정 회의실 이름이 언급되면 get_meeting_rooms를 회의실별로 각각 호출하세요

결과를 format_meeting_rooms_as_table(meeting_data=결과)로 전달하면 회의실별 접기/펼치기 HTML이 생성됩니다.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "특정 날짜 조회 (예: '오늘', '내일', '2026-03-05')",
                    },
                    "date_range_start": {
                        "type": "string",
                        "description": "기간 시작 날짜 (예: '이번주', '다음주')",
                    },
                    "date_range_end": {
                        "type": "string",
                        "description": "기간 종료 날짜",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_meeting_room",
            "description": "회의실 예약 정보를 변경합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cal_id": {
                        "type": "string",
                        "description": "예약 번호 (예: 1번, 2번)",
                    },
                    "title": {
                        "type": "string",
                        "description": "기존 회의 제목 (검색용)",
                    },
                    "title_chg": {"type": "string", "description": "변경할 새 제목"},
                    "meetingroom_chg": {
                        "type": "string",
                        "description": "변경할 회의실 이름",
                    },
                    "date": {
                        "type": "string",
                        "description": "변경할 날짜 (YYYY-MM-DD 또는 '내일' 등)",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "변경할 시작 시간 (HH:MM 또는 '오후 3시' 등)",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "변경할 종료 시간 (HH:MM 또는 '오후 4시' 등)",
                    },
                    "description": {
                        "type": "string",
                        "description": "변경할 회의 내용",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_meeting_room",
            "description": "회의실 예약을 취소합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cal_id": {
                        "type": "string",
                        "description": "취소할 예약 번호 (예: 1번, 2번)",
                    },
                    "title": {"type": "string", "description": "취소할 회의 제목"},
                    "meetingroom": {
                        "type": "string",
                        "description": "취소할 회의실 이름",
                    },
                    "date": {"type": "string", "description": "취소할 예약 날짜"},
                    "start_time": {
                        "type": "string",
                        "description": "취소할 예약 시작 시간",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "취소할 예약 종료 시간",
                    },
                },
                "required": ["reservation_id"],
            },
        },
    },
    # 3. Executive Schedule (1 tool)
    {
        "type": "function",
        "function": {
            "name": "get_executive_schedule",
            "description": "임원(경영진)의 일정을 조회합니다. 임원 이름이나 직책으로 검색합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "executive_name": {
                        "type": "string",
                        "description": "임원 이름 (예: 홍길동)",
                    },
                    "position": {
                        "type": "string",
                        "description": "직책 (예: 사장, 부사장, 본부장)",
                    },
                    "date": {
                        "type": "string",
                        "description": "조회할 날짜 (YYYY-MM-DD)",
                    },
                    "date_range_start": {
                        "type": "string",
                        "description": "조회 시작 날짜",
                    },
                    "date_range_end": {
                        "type": "string",
                        "description": "조회 종료 날짜",
                    },
                },
                "required": [],
            },
        },
    },
    # 4. Employee Search (1 tool)
    {
        "type": "function",
        "function": {
            "name": "find_employee",
            "description": "직원 정보를 검색합니다. 이름, 부서, 팀, 직책, 업무, 근무지 등으로 검색 가능합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "직원 이름 (부분 일치)"},
                    "emp_code": {"type": "string", "description": "사번"},
                    "email": {"type": "string", "description": "이메일"},
                    "dept": {
                        "type": "string",
                        "description": "부서명 (예: 디지털시스템실, 경영지원팀)",
                    },
                    "team": {
                        "type": "string",
                        "description": "팀명 (예: AI팀, 개발팀)",
                    },
                    "position": {
                        "type": "string",
                        "description": "직책 (예: 팀장, 차장, 과장, 대리)",
                    },
                    "duty": {
                        "type": "string",
                        "description": "담당 업무 (예: 사업관리, 공사채권, AI개발)",
                    },
                    "location": {
                        "type": "string",
                        "description": "근무지 (예: 본사, 부산지역본부)",
                    },
                },
                "required": [],
            },
        },
    },
    # 5. Approval Form (4 tools)
    {
        "type": "function",
        "function": {
            "name": "get_approval_form",
            "description": "전자결재 양식을 조회합니다. 양식 이름으로 검색합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "form_name": {
                        "type": "string",
                        "description": "양식 이름 (예: 지출결의서, 휴가신청서, 출장신청서, 통합기안양식, 구매요청서)",
                    },
                    "department": {
                        "type": "string",
                        "description": "부서별 양식이 필요한 경우 부서명",
                    },
                },
                "required": ["form_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_approvals",
            "description": "내 결재함(대기 중인 결재 문서)을 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "결재 상태 (pending: 대기, approved: 승인, rejected: 반려)",
                        "enum": ["pending", "approved", "rejected"],
                    },
                    "date_from": {
                        "type": "string",
                        "description": "조회 시작일 (YYYY-MM-DD)",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "조회 종료일 (YYYY-MM-DD)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "approve_document",
            "description": "결재 문서를 승인합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "문서 ID (예: APPR-2026-001)",
                    },
                    "comment": {"type": "string", "description": "승인 의견 (선택)"},
                },
                "required": ["doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reject_document",
            "description": "결재 문서를 반려합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "문서 ID (예: APPR-2026-001)",
                    },
                    "reason": {"type": "string", "description": "반려 사유 (필수)"},
                },
                "required": ["doc_id", "reason"],
            },
        },
    },
    # 6. Draft Tools (2 tools)
    {
        "type": "function",
        "function": {
            "name": "draft_email",
            "description": "업무 메일 초안을 작성합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {
                        "type": "string",
                        "description": "수신자 또는 수신 대상 (예: 팀장님, 고객사, 전사)",
                    },
                    "subject": {"type": "string", "description": "메일 제목"},
                    "purpose": {
                        "type": "string",
                        "description": "메일 목적 (예: 미팅 요청, 보고, 안내)",
                    },
                    "key_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "메일에 포함할 핵심 내용",
                    },
                    "tone": {
                        "type": "string",
                        "enum": ["formal", "casual"],
                        "description": "메일 어조. 기본값: formal",
                    },
                },
                "required": ["recipient", "purpose"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_document",
            "description": """공식 문서 초안을 작성합니다.

**공공기관 문서 (행정안전부 공문서 작성 규정 준수, LLM으로 실제 내용 생성):**
- 공문/협조전: 수신·참조·본문·붙임 구조의 공식 서한
- 업무보고서: 업무 현황, 분석, 대책 보고
- 기획안: 사업/프로젝트 기획 문서
- 회의록: 회의 내용 기록
- 결과보고서: 사업/업무 추진 결과 보고
- 사업계획서: 사업 추진 계획
- 검토보고서: 안건 검토 의견

**기획보고서 (□○―※ 기호 체계, LLM으로 실제 내용 생성):**
- 정책제안보고서: 정책 제안 및 건의
- 사업계획보고서: 사업 추진 계획 (상세)
- 실적보고서: 사업/업무 실적 보고
- 현안보고서: 현안 분석 및 대응 방안

**일반 문서 (템플릿 구조 제공):**
- 보고서, 기획서, 제안서

공공기관 문서 요청 시 document_type에 정확한 유형명을 사용하세요.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_type": {
                        "type": "string",
                        "enum": [
                            "공문",
                            "협조전",
                            "업무보고서",
                            "기획안",
                            "회의록",
                            "결과보고서",
                            "사업계획서",
                            "검토보고서",
                            "정책제안보고서",
                            "사업계획보고서",
                            "실적보고서",
                            "현안보고서",
                            "보고서",
                            "기획서",
                            "제안서",
                        ],
                        "description": "문서 유형",
                    },
                    "title": {"type": "string", "description": "문서 제목"},
                    "content_requirements": {
                        "type": "string",
                        "description": "포함해야 할 내용이나 요구사항",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "수신 기관/부서 (공문 작성 시, 예: 각 부서장, 경영지원팀)",
                    },
                    "reference": {
                        "type": "string",
                        "description": "참조 기관/부서 (공문 작성 시)",
                    },
                    "sections": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "문서에 포함할 섹션 목록 (선택, 공공기관 문서는 자동 적용)",
                    },
                },
                "required": ["document_type", "title"],
            },
        },
    },
    # 6-2. Document Guide (1 tool)
    {
        "type": "function",
        "function": {
            "name": "guide_document_draft",
            "description": "문서 초안 작성을 단계별로 안내합니다. 사용자가 문서 유형을 특정하지 않고 문서초안/공문서 작성을 요청할 때 호출합니다. step='select_type'으로 문서 유형 목록을 보여주고, step='show_requirements'로 선택된 유형의 필요 정보를 안내합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "step": {
                        "type": "string",
                        "enum": ["select_type", "show_requirements"],
                        "description": "select_type: 문서 유형 목록 표시, show_requirements: 선택된 유형의 필요 정보 안내",
                    },
                    "document_type": {
                        "type": "string",
                        "description": "show_requirements 단계에서 필수. 문서 유형명 (예: 공문, 정책제안보고서)",
                    },
                },
                "required": ["step"],
            },
        },
    },
    # 6-1. Document Review (1 tool)
    {
        "type": "function",
        "function": {
            "name": "review_document",
            "description": """작성된 문서를 검수합니다. 형식, 문체, 내용, 어문규범 4개 영역을 평가하고 수정 제안을 제공합니다.

**사용 시나리오:**
- draft_document로 생성한 문서를 바로 검수할 때
- 사용자가 직접 작성한 문서의 품질을 점검할 때
- "이 문서 검수해줘", "문서 검토해줘" 요청 시

**검수 영역 (각 10점 만점, 총 40점):**
- 형식: 문서 구조, 번호 체계, 들여쓰기
- 문체: 경어체, 개조식, 간결성
- 내용: 논리적 구성, 근거, 명확성
- 어문규범: 맞춤법, 띄어쓰기, 행정 용어

**기획보고서(□○―※ 기호 체계) 검수:**
document_type에 "정책제안보고서", "사업계획보고서" 등을 지정하면 기호 체계 정확성도 추가 검수합니다.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_content": {
                        "type": "string",
                        "description": "검수할 문서 내용 (전체 텍스트)",
                    },
                    "document_type": {
                        "type": "string",
                        "description": "문서 유형 (예: 정책제안보고서, 공문, 업무보고서, 기획안 등). 유형에 맞는 추가 검수 기준이 적용됩니다.",
                    },
                    "review_focus": {
                        "type": "string",
                        "enum": ["전체", "형식", "내용", "기호체계"],
                        "description": "검수 초점. 기본값: 전체",
                    },
                },
                "required": ["document_content"],
            },
        },
    },
    # 7. RAG Search (1 tool) ⭐
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": """KAMCO 내부 문서 및 지식 기반에서 정보를 검색합니다.

**사용 시나리오:**
- 업무 매뉴얼, 규정, 가이드를 찾을 때
- 회사 정책이나 절차에 대한 질문
- 과거 문서나 참고 자료가 필요할 때
- 일반적인 업무 지식이 필요할 때

**예시 질문:**
- "출장비 신청 절차가 어떻게 되나요?"
- "연차 사용 규정 알려줘"
- "신규 입사자 온보딩 프로세스는?"
- "회사 복리후생 제도에 대해 알려줘"

**주의:** 실시간 데이터(일정, 회의실)는 해당 전용 도구를 사용하세요.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색할 질문 또는 키워드. 명확하고 구체적으로 작성하세요.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    # 8. Translation (1 tool) ⭐ NEW
    {
        "type": "function",
        "function": {
            "name": "translate_text",
            "description": """텍스트를 다른 언어로 번역합니다.

**지원 언어:**
- 한국어 ↔ 영어
- 한국어 ↔ 일본어
- 한국어 ↔ 중국어
- 영어 ↔ 일본어
- 영어 ↔ 중국어

**사용 시나리오:**
- 해외 거래처와의 이메일 번역
- 영문 계약서 내용 이해
- 외국어 문서 작성 지원
- 다국어 커뮤니케이션

**예시:**
- "안녕하세요를 영어로 번역해줘"
- "Hello World를 한국어로 번역"
- "こんにちは를 영어로 번역해줘"
- "이 문장을 일본어로 번역: 회의가 연기되었습니다"
""",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "번역할 원문 텍스트"},
                    "target_language": {
                        "type": "string",
                        "enum": [
                            "영어",
                            "한국어",
                            "일본어",
                            "중국어",
                            "English",
                            "Korean",
                            "Japanese",
                            "Chinese",
                        ],
                        "description": "번역할 목표 언어. 예: '영어', 'English', '한국어', 'Korean'",
                    },
                    "source_language": {
                        "type": "string",
                        "enum": [
                            "영어",
                            "한국어",
                            "일본어",
                            "중국어",
                            "English",
                            "Korean",
                            "Japanese",
                            "Chinese",
                            "auto",
                        ],
                        "description": "원문 언어 (선택사항). 기본값: 'auto' (자동 감지)",
                    },
                },
                "required": ["text", "target_language"],
            },
        },
    },
    # 9. HTML Format Tools (4 tools) ⭐ NEW - 달력 + 표 형식
    # 일정 - 달력 형식
    {
        "type": "function",
        "function": {
            "name": "format_schedule_as_calendar",
            "description": """일정 조회 결과를 달력 형식으로 변환합니다. (월별 캘린더 뷰)

**사용 시나리오:**
- 일정 조회 결과가 많을 때 (10개 이상)
- 사용자가 "달력으로 보여줘" 또는 "달력 형식으로" 요청 시
- 월별로 일정을 보고 싶을 때

**사용 절차:**
1. get_schedule()로 일정 조회
2. 결과가 많으면 (10개+) 사용자에게 물어보기: "일정이 {count}개입니다. 달력 또는 표 형식으로 보여드릴까요?"
3. 사용자가 "달력" 선택 시 이 도구 호출
4. HTML 달력이 브라우저에서 자동으로 열림

**특징:** 실제 캘린더 뷰, 월별 접기/펼치기, 날짜별 일정 배치""",
            "parameters": {
                "type": "object",
                "properties": {
                    "schedules": {
                        "description": "get_schedule() 반환값 전체를 그대로 전달 (dict 또는 schedules 배열 모두 가능)"
                    },
                    "user_name": {
                        "type": "string",
                        "description": "사용자 이름 (기본값: '사용자')",
                    },
                    "start_dt": {
                        "type": "string",
                        "description": "조회 시작 날짜 (YYYY.MM.DD)",
                    },
                    "end_dt": {
                        "type": "string",
                        "description": "조회 종료 날짜 (YYYY.MM.DD)",
                    },
                },
                "required": ["schedules"],
            },
        },
    },
    # 일정 - 표 형식
    {
        "type": "function",
        "function": {
            "name": "format_schedule_as_table",
            "description": """일정 조회 결과를 표 형식으로 변환합니다. (테이블 목록)

**사용 시나리오:**
- 일정 조회 결과가 많을 때 (10개 이상)
- 사용자가 "표로 보여줘" 또는 "테이블로" 요청 시
- 일정을 목록으로 한눈에 보고 싶을 때

**사용 절차:**
1. get_schedule()로 일정 조회
2. 결과가 많으면 (10개+) 사용자에게 물어보기: "일정이 {count}개입니다. 달력 또는 표 형식으로 보여드릴까요?"
3. 사용자가 "표" 선택 시 이 도구 호출
4. HTML 표가 브라우저에서 자동으로 열림

**특징:** 간단한 테이블, 행 단위 목록, 빠른 스캔""",
            "parameters": {
                "type": "object",
                "properties": {
                    "schedules": {
                        "description": "get_schedule() 반환값 전체를 그대로 전달 (dict 또는 schedules 배열 모두 가능)"
                    },
                    "user_name": {
                        "type": "string",
                        "description": "사용자 이름 (기본값: '사용자')",
                    },
                    "start_dt": {
                        "type": "string",
                        "description": "조회 시작 날짜 (표시용)",
                    },
                    "end_dt": {
                        "type": "string",
                        "description": "조회 종료 날짜 (표시용)",
                    },
                },
                "required": ["schedules"],
            },
        },
    },
    # 회의실 - 달력 형식
    {
        "type": "function",
        "function": {
            "name": "format_meeting_rooms_as_calendar",
            "description": """회의실 예약 현황을 달력 형식으로 변환합니다. (월별 캘린더 뷰)

**⚠️ 달력은 1회만 호출 가능! 여러 회의실이 있어도 이 도구는 첫 번째 회의실 1개만 호출하세요.**
- 사용자가 2개 이상 회의실을 "달력으로 보여줘"라고 요청해도, 첫 번째 회의실만 이 도구로 호출
- 나머지 회의실은 답변에서 "나머지 회의실도 달력으로 보고 싶으시면 하나씩 요청해주세요! 아니면 표 형식으로 한번에 보여드릴 수도 있어요."라고 안내
- 2개 이상 회의실을 한번에 비교하려면 → format_meeting_rooms_as_table 사용 (표 형식)

**사용 시나리오:**
- 회의실 예약 조회 결과를 달력으로 볼 때 (1개 회의실씩)

**사용 절차:**
1. get_meeting_rooms()로 회의실 예약 현황 조회
2. 이 도구는 **1개 회의실만** 호출 (여러 개 조회했어도 첫 번째만)
3. 나머지 회의실은 텍스트로 안내

**⚠️ 중요: meeting_data에 get_meeting_rooms() 결과 dict 전체를 반드시 전달하세요!**
예: format_meeting_rooms_as_calendar(meeting_data=get_meeting_rooms_결과)
meetingroom_name, start_dt, end_dt만 전달하면 오류 발생!

**특징:** 실제 캘린더 뷰, 날짜별 예약 배치""",
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_data": {
                        "type": "object",
                        "description": "get_meeting_rooms() 반환값 전체 dict를 그대로 전달 (필수! room_info가 포함된 전체 결과)",
                    },
                    "user_name": {
                        "type": "string",
                        "description": "사용자 이름 (기본값: '사용자')",
                    },
                    "meetingroom_name": {
                        "type": "string",
                        "description": "회의실 이름 (선택, meeting_data에서 자동 추출)",
                    },
                    "start_dt": {
                        "type": "string",
                        "description": "조회 시작 날짜 (선택, meeting_data에서 자동 추출)",
                    },
                    "end_dt": {
                        "type": "string",
                        "description": "조회 종료 날짜 (선택, meeting_data에서 자동 추출)",
                    },
                },
                "required": ["meeting_data"],
            },
        },
    },
    # 회의실 - 표 형식
    {
        "type": "function",
        "function": {
            "name": "format_meeting_rooms_as_table",
            "description": """회의실 예약 현황을 표 형식으로 변환합니다. (테이블 목록)

**사용 시나리오:**
- 회의실 예약 조회 결과가 많을 때 (5개 이상)
- 사용자가 "표로 보여줘" 요청 시
- 예약 현황을 목록으로 한눈에 보고 싶을 때

**사용 절차:**
1. get_meeting_rooms()로 예약 현황 조회
2. 결과가 많으면 (5개+) 사용자에게 물어보기: "예약이 {count}개입니다. 달력 또는 표 형식으로 보여드릴까요?"
3. 사용자가 "표" 선택 시 이 도구 호출
4. HTML 표가 브라우저에서 자동으로 열림

**⚠️ 중요: meeting_data에 get_meeting_rooms() 결과 dict 전체를 반드시 전달하세요!**
예: format_meeting_rooms_as_table(meeting_data=get_meeting_rooms_결과)
meetingroom_name, start_dt, end_dt만 전달하면 오류 발생!

**특징:** 날짜별 접기/펼치기, 2열 카드 배치, 회의실별 필터""",
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_data": {
                        "type": "object",
                        "description": "get_meeting_rooms() 반환값 전체 dict를 그대로 전달 (필수! room_info가 포함된 전체 결과)",
                    },
                    "user_name": {
                        "type": "string",
                        "description": "사용자 이름 (기본값: '사용자')",
                    },
                    "meetingroom_name": {
                        "type": "string",
                        "description": "회의실 이름 (선택, meeting_data에서 자동 추출)",
                    },
                    "start_dt": {
                        "type": "string",
                        "description": "조회 시작 날짜 (선택, meeting_data에서 자동 추출)",
                    },
                    "end_dt": {
                        "type": "string",
                        "description": "조회 종료 날짜 (선택, meeting_data에서 자동 추출)",
                    },
                },
                "required": ["meeting_data"],
            },
        },
    },
    # ============================================================
    # 사용자 정보 도구 (3개) ⭐ NEW
    # ============================================================
    {
        "type": "function",
        "function": {
            "name": "get_my_info",
            "description": "내 정보를 조회합니다. 이름, 부서, 팀, 직책, 이메일, 전화번호 등을 확인할 수 있습니다.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_team",
            "description": "내 팀원 목록을 조회합니다. 우리 팀에 누가 있는지, 팀이 누구인지 확인할 수 있습니다.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_next_schedule",
            "description": "다음 일정을 조회합니다. 현재 시간 기준으로 가장 가까운 예정된 일정을 확인할 수 있습니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_time": {
                        "type": "string",
                        "description": "기준 시간 (선택, 기본값: 현재). ISO 형식 (YYYY-MM-DDTHH:MM:SS)",
                    }
                },
                "required": [],
            },
        },
    },
    # ============================================================
    # 회의실 강화 도구 (1개) ⭐ NEW
    # ============================================================
    {
        "type": "function",
        "function": {
            "name": "find_available_room",
            "description": "특정 시간대에 예약 가능한 빈 회의실을 찾습니다. 사용 가능한 회의실 목록을 확인할 수 있습니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "날짜 (YYYY-MM-DD 또는 '오늘', '내일', '모레' 등)",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "시작 시간 (HH:MM 형식, 예: 14:00)",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "종료 시간 (HH:MM 형식, 예: 15:00)",
                    },
                    "min_capacity": {
                        "type": "integer",
                        "description": "최소 수용 인원 (선택, 예: 10명 이상)",
                    },
                },
                "required": ["date", "start_time", "end_time"],
            },
        },
    },
    # ============================================================
    # 범용 테이블 도구 (1개) ⭐ NEW - 어떤 데이터든 표로 변환
    # ============================================================
    {
        "type": "function",
        "function": {
            "name": "format_data_as_table",
            "description": """구조화된 데이터를 HTML 표로 변환하여 보여줍니다.

**사용 시나리오:**
- 임원 일정, 결재 목록, 주간 요약 등 구조화된 데이터를 표로 정리할 때
- 사용자가 "표로 보여줘", "테이블로 정리해줘" 요청 시
- 여러 항목을 한눈에 비교해야 할 때

**사용 방법:**
1. 다른 도구로 데이터를 먼저 조회
2. 중첩된 데이터는 flat한 리스트로 변환 (각 행이 하나의 dict)
3. 이 도구에 전달

**예시 - 임원 일정:**
get_executive_schedule() 결과의 executives를 펼쳐서:
data = [
    {"이름": "김태영", "직위": "사장", "일정": "이사회", "시간": "09:00~11:00", "장소": "대회의실"},
    {"이름": "이민호", "직위": "부사장", "일정": "채권관리 전략회의", "시간": "10:00~12:00", "장소": "소회의실"}
]
format_data_as_table(title="임원 일정", data=data)

**주의:**
- data는 반드시 flat한 list[dict] 형태 (중첩 dict/list 불가)
- 한글 키를 사용하면 column_labels 불필요
- columns를 지정하면 해당 열만 표시 (순서 보장)
- 일정은 format_schedule_as_table, 회의실은 format_meeting_rooms_as_table 사용 (전용 기능 있음)""",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "표 제목 (예: '임원 일정', '결재 현황', '직원 목록')",
                    },
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "표시할 데이터 (flat한 dict 배열). 중첩 구조는 미리 펼쳐서 전달",
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "표시할 열 키 목록 (순서대로). 생략 시 모든 키 자동 표시",
                    },
                    "column_labels": {
                        "type": "object",
                        "description": '열 키 → 한글 라벨 매핑 (예: {"name": "이름"}). 생략 시 자동 매핑',
                    },
                },
                "required": ["title", "data"],
            },
        },
    },
    # ============================================================
    # Excel 다운로드 도구 (1개) ⭐ NEW - 표 표시 + Excel 파일 다운로드
    # ============================================================
    {
        "type": "function",
        "function": {
            "name": "format_data_as_excel",
            "description": """구조화된 데이터를 HTML 표로 화면에 표시하고 Excel(.xlsx) 파일 다운로드를 제공합니다.

**사용 시나리오:**
- 사용자가 "엑셀로 정리해줘", "엑셀로 만들어줘", "다운로드", "Excel" 요청 시
- 데이터를 스프레드시트 형태로 보여주고 파일로 내보내고 싶을 때
- format_data_as_table과 동일하지만 Excel 다운로드 기능이 추가됨

**사용 방법:**
1. 다른 도구로 데이터를 먼저 조회 (일정, 결재, 직원 등)
2. 중첩된 데이터는 flat한 리스트로 변환
3. 이 도구에 전달

**예시:**
data = [
    {"월": "1월", "매출": "12억", "영업이익": "3.5억"},
    {"월": "2월", "매출": "14억", "영업이익": "4.2억"}
]
format_data_as_excel(title="월별 매출 현황", data=data, file_name="월별_매출_현황")

**주의:**
- data는 반드시 flat한 list[dict] 형태 (중첩 dict/list 불가)
- 한글 키를 사용하면 column_labels 불필요
- columns를 지정하면 해당 열만 표시 (순서 보장)
- 단순 표 표시만 원하면 format_data_as_table 사용""",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "표 제목 (예: '월별 매출 현황', '직원 목록')",
                    },
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "표시할 데이터 (flat한 dict 배열). 중첩 구조는 미리 펼쳐서 전달",
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "표시할 열 키 목록 (순서대로). 생략 시 모든 키 자동 표시",
                    },
                    "column_labels": {
                        "type": "object",
                        "description": '열 키 → 한글 라벨 매핑 (예: {"name": "이름"}). 생략 시 자동 매핑',
                    },
                    "file_name": {
                        "type": "string",
                        "description": "다운로드 파일명 (확장자 제외). 생략 시 제목_날짜 자동 생성",
                    },
                },
                "required": ["title", "data"],
            },
        },
    },
    # ============================================================
    # 요약 도구 (1개) ⚠️ OPTIONAL - 필요 없으면 주석 처리
    # ============================================================
    {
        "type": "function",
        "function": {
            "name": "get_weekly_summary",
            "description": "주간 요약 정보를 제공합니다. 이번 주 일정, 회의, 결재 현황을 한눈에 볼 수 있습니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "week_offset": {
                        "type": "integer",
                        "description": "주 오프셋 (0=이번주, -1=지난주, 1=다음주)",
                    }
                },
                "required": [],
            },
        },
    },
]
