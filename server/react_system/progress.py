import json
from typing import List, Optional

def make_agent_progress(steps: list, writer=None) -> str:
    """도구 실행 진행 상황을 JSON으로 변환하여 writer로 전송."""
    progress_data = {
        "replace_chunk": True,
        "steps": []
    }
    for step in steps:
        step_info = {
            "title": step.get("title", ""),
            "status": step.get("status", "running"),  # running, done, error
        }
        if "result_count" in step:
            step_info["result_count"] = step["result_count"]
        if "preview" in step:
            step_info["preview"] = step["preview"]
        progress_data["steps"].append(step_info)

    if writer:
        writer(progress_data)

    return json.dumps(progress_data, ensure_ascii=False)


def make_agent_summary(steps: list, writer=None) -> str:
    """완료된 도구 실행 단계들을 summary로 변환하여 writer로 전송.

    Args:
        steps: _finalize_steps()로 완료 처리된 step 리스트
        writer: SSEWriter (optional)
    """
    summary_data = {
        "replace_chunk": True,
        "steps": []
    }
    for step in steps:
        step_info = {
            "title": step.get("title", ""),
            "status": step.get("status", "done"),
        }
        if "result_count" in step:
            step_info["result_count"] = step["result_count"]
        if "preview" in step:
            step_info["preview"] = step["preview"]
        summary_data["steps"].append(step_info)

    if writer:
        writer(summary_data)

    return json.dumps(summary_data, ensure_ascii=False)
