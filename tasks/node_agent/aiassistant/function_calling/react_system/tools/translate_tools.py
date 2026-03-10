"""
번역 도구
텍스트를 다른 언어로 번역합니다.
"""

from openai import AsyncOpenAI


async def translate_text(text: str, target_language: str, source_language: str = "auto", _auth=None) -> dict:
    """
    텍스트를 목표 언어로 번역합니다.

    Args:
        text: 번역할 원문 텍스트
        target_language: 목표 언어 (예: '영어', 'English', '한국어')
        source_language: 원문 언어 (기본값: 'auto' - 자동 감지)

    Returns:
        dict: {
            "status": "success" | "error",
            "original_text": "원문",
            "translated_text": "번역된 텍스트",
            "source_language": "감지된 원문 언어",
            "target_language": "목표 언어",
            "message": "오류 메시지 (실패 시)"
        }
    """
    try:
        # 언어 코드 정규화
        target_lang = _normalize_language(target_language)
        source_lang = _normalize_language(source_language) if source_language != "auto" else "auto"

        # 번역 수행
        translated = await _perform_translation(text, source_lang, target_lang)

        return {
            "status": "success",
            "original_text": text,
            "translated_text": translated["text"],
            "source_language": translated["detected_lang"],
            "target_language": target_lang
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"번역 중 오류 발생: {str(e)}",
            "original_text": text,
            "translated_text": ""
        }


def _normalize_language(language: str) -> str:
    """
    언어 이름을 표준 코드로 변환

    Args:
        language: 언어 이름 (예: '영어', 'English')

    Returns:
        str: 언어 코드 (예: 'en', 'ko', 'ja', 'zh')
    """
    language_map = {
        "영어": "en",
        "english": "en",
        "한국어": "ko",
        "korean": "ko",
        "일본어": "ja",
        "japanese": "ja",
        "중국어": "zh",
        "chinese": "zh",
        "auto": "auto"
    }

    return language_map.get(language.lower(), "en")


async def _perform_translation(text: str, source_lang: str, target_lang: str) -> dict:
    """
    OpenAI API를 사용한 실제 번역 수행 (async)

    Args:
        text: 원문
        source_lang: 원문 언어 코드
        target_lang: 목표 언어 코드

    Returns:
        dict: {"text": "번역 결과", "detected_lang": "감지된 언어"}
    """
    client = AsyncOpenAI()

    # 언어 이름 매핑
    lang_names = {
        "en": "영어",
        "ko": "한국어",
        "ja": "일본어",
        "zh": "중국어"
    }

    target_lang_name = lang_names.get(target_lang, "영어")

    # 프롬프트 구성
    if source_lang == "auto":
        prompt = f"다음 텍스트를 {target_lang_name}로 번역해주세요. 번역 결과만 출력하고 다른 설명은 하지 마세요.\n\n텍스트: {text}"
    else:
        source_lang_name = lang_names.get(source_lang, "자동 감지")
        prompt = f"다음 {source_lang_name} 텍스트를 {target_lang_name}로 번역해주세요. 번역 결과만 출력하고 다른 설명은 하지 마세요.\n\n텍스트: {text}"

    # OpenAI API 호출 (async)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "당신은 전문 번역가입니다. 정확하고 자연스러운 번역을 제공하세요. 번역 결과만 출력하고 다른 설명은 절대 하지 마세요."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3,
        max_tokens=2000
    )

    translated_text = response.choices[0].message.content.strip()

    # 원문 언어 감지 (간단한 휴리스틱)
    detected_lang = _detect_language(text) if source_lang == "auto" else source_lang

    return {
        "text": translated_text,
        "detected_lang": detected_lang
    }


def _detect_language(text: str) -> str:
    """
    간단한 언어 감지 (휴리스틱)

    Args:
        text: 감지할 텍스트

    Returns:
        str: 감지된 언어 코드
    """
    # 한글 포함 여부
    if any('\uac00' <= char <= '\ud7a3' for char in text):
        return "ko"

    # 일본어 히라가나/가타카나
    if any('\u3040' <= char <= '\u30ff' for char in text):
        return "ja"

    # 중국어 간체/번체
    if any('\u4e00' <= char <= '\u9fff' for char in text):
        return "zh"

    # 기본값: 영어
    return "en"


# 테스트용
if __name__ == "__main__":
    print("=" * 60)
    print("번역 도구 테스트")
    print("=" * 60)

    # 테스트 1: 한→영
    print("\n테스트 1: 한국어 → 영어")
    result1 = translate_text("안녕하세요, 반갑습니다!", "영어")
    print(f"원문: {result1['original_text']}")
    print(f"번역: {result1['translated_text']}")
    print(f"상태: {result1['status']}")

    # 테스트 2: 영→한
    print("\n테스트 2: 영어 → 한국어")
    result2 = translate_text("Hello, nice to meet you!", "한국어")
    print(f"원문: {result2['original_text']}")
    print(f"번역: {result2['translated_text']}")
    print(f"상태: {result2['status']}")

    # 테스트 3: 일→영
    print("\n테스트 3: 일본어 → 영어")
    result3 = translate_text("こんにちは、はじめまして！", "English")
    print(f"원문: {result3['original_text']}")
    print(f"번역: {result3['translated_text']}")
    print(f"상태: {result3['status']}")

    # 테스트 4: 긴 문장
    print("\n테스트 4: 긴 문장 (한→영)")
    long_text = "회의가 다음 주 월요일 오후 3시로 연기되었습니다. 참석자분들께 미리 양해 말씀 드립니다."
    result4 = translate_text(long_text, "영어")
    print(f"원문: {result4['original_text']}")
    print(f"번역: {result4['translated_text']}")
    print(f"상태: {result4['status']}")

    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)
