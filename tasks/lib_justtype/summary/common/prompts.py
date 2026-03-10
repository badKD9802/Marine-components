template_analysis_toc = """당신은 페이지의 특징을 식별하는 전문가입니다. 제공된 페이지 원문을 분석하여 페이지의 특징을 식별하세요.

## 중요 지침:
텍스트의 내용이 아닌 구조를 중시하세요. 

## Table of Contents
- "목차", "Contents" 등의 키워드 포함.
- 각 문장의 마지막에 페이지 번호가 위치하는 패턴이 반복.

### 각 문장의 마지막에 페이지 번호가 위치하는 패턴 예시
- "제2절 연구목표 및 내용 ··························································· 2"
- "나. 블라인드 채용제도 효과성 분석 결과 ··········································· 44"
- "Ⅳ. 결론 및 요약 / 20"
- "5. 시사점 19"
- "두바이, 7가지 새로운 디지털 전략 발표 _ 30"

## 출력 형식:
{format_instructions}

## 페이지 원문:
{user_input}
"""
format_analysis_toc = """
<output>
<reasoning>
[간단한 페이지 구조 분석]
</reasoning>
<decision>[페이지가 Table of Contents라면 Y, 아니면 N]</decision>
</output>
"""

template_analysis_ref = """당신은 페이지의 특징을 식별하는 전문가입니다. 제공된 페이지 원문을 분석하여 페이지의 특징을 식별하세요.

## 중요 지침:
텍스트의 내용이 아닌 구조를 중시하세요. 

## Bibliography
- "참고문헌", "References", "Bibliography" 등의 키워드 포함.
- 텍스트가 여러 문헌 항목(예: 책, 논문, 웹사이트 등)을 나열.
- 특정 인용 형식(예: APA, MLA, IEEE 스타일: 저자 이름, 연도, 제목, 출판사 등)이 나타남.

## 출력 형식:
{format_instructions}

## 페이지 원문:
{user_input}
"""
format_analysis_ref = """
<output>
<reasoning>
[간단한 페이지 구조 분석]
</reasoning>
<decision>[페이지가 Bibliography라면 Y, 아니면 N]</decision>
</output>
"""


template_summary = """당신은 요약 전문가입니다. 아래의 텍스트를 참고하여 간결하고 중요한 정보를 담은 요약을 작성하세요.

## 작업 순서:
1. 텍스트 분석:
    - 문서 제목과 텍스트를 주의 깊게 읽고, 문서의 주요 주제를 파악하세요.
    - 만약 제목이 요약과 관련이 없을 경우, 요약만을 중심으로 분석하세요.
2. 주요 주장(key_argument) 식별:
    - 다음 질문에 답변하기: "이 텍스트의 주요 주장 또는 핵심 논점은 무엇인가?"
3. 핵심 엔티티(entities) 추출: 
    - 5단어 이하의 핵심 엔티티 3개를 뽑아주세요.
4. 요약문의 주제(title) 생성: 
    - 제공된 텍스트에 대한 간결한 한문장의 주제를 생성하세요.
5. 요약(summary) 작성: 
    - 주요 주장과 핵심 엔티티, 주제를 참고하여 텍스트의 주요 내용을 500자 이내로 요약하세요.

## 작성 방식:
    - 문서를 소개하는 대신 요약 내용만 작성하세요.
    - 구체적인 데이터나 수치보다는 전체 흐름과 방향을 설명하세요.
    - 주어진 내용에만 기반해 객관적으로 작성하세요.
    - 명확한 문장 구조를 유지하고, {sentence_range} 문장으로 요약하세요.
    - 한국어로 작성하되, 영어 기술 용어와 고유 명사는 그대로 사용하세요. 번역이 필요한 경우 한국어(원어)로 병기하세요.

## 요약 문장의 예시:
    - 인공지능(AI) 기술의 발전은 다양한 산업 분야에 혁명적인 변화를 가져오고 있다.
    - 기후 변화로 인한 해수면 상승은 연안 지역 주민들에게 심각한 위협이 되고 있다.
    - 새로운 암 치료법 개발로 생존율이 크게 향상되었다.

## 입력:
### 문서 제목:
{title}
### 텍스트:
{user_input}

## 출력 형식:
{format_instructions}
"""
format_summary = """
<output>
    <key_argument>[주요 주장(한국어)]</key_argument>
    <entities>[주요 개체 목록, 쉼표로 구분]</entities>
    <title>[주제(한국어)]</title>
    <summary>
        <point>[첫번째 요약 문장(한국어)]</point>
        <point>[두번째 요약 문장(한국어)]</point>
        ...
    </summary>
</output>
"""

template_question = """**작업**:
주어진 텍스트는 전체 문서의 일부분입니다.
주어진 텍스트를 주의 깊게 읽고 하나의 질문을 생성하세요. 
텍스트가 질문을 만들기에 적절하지 않으면 "질문을 생성할 수 없습니다."라고만 답변하세요.

**지침**:
- 텍스트의 정보만으로 완전히 답변할 수 있는 질문을 하나 작성하세요.
- 생성된 질문으로 주어진 텍스트를 retriever에서 가져올 수 있어야 합니다.
- 문서 전체에 대한 호기심을 유발하는 흥미로운 질문이어야 합니다.
- 질문은 한국어로 작성하세요.
- 질문은 30자 이내여야 합니다.
- 텍스트를 직접 언급하지 마세요 (예: "이 문단에서" 등 피하기).

**예시**:
- <question>최근 개발된 인공지능 기술의 주요 특징은 무엇인가요?</question>
- <question>식물성 대체육과 배양육의 가장 큰 차이점은 무엇인가요?</question>

**텍스트**:
<chunk>
{context}
</chunk>

**출력 형식**:
- **질문을 생성한 경우**:
```
{format_instructions}
```
- **질문을 생성할 수 없는 경우**:
```
질문을 생성할 수 없습니다.
```
"""
format_question = """
<output>
    <question>[질문 내용]</question>
</output>
"""

correction_prompt = """
다음은 출력 파싱 중 발생한 오류와 잘못된 출력입니다. 올바른 형식으로 수정해 주세요.

오류: {error}
잘못된 출력: {response}

## 수정된 출력 형식:{format_instructions}
"""


qa_system_template = """You are an AI assistant specializing in Question-Answering (QA) tasks within a Retrieval-Augmented Generation (RAG) system. 
Your primary mission is to answer questions based on provided context.
Ensure your response is concise and directly addresses the question without any additional narration.

###

Your final answer should be written concisely (but include important numerical values, technical terms, and jargon).

# Steps
1. Carefully read and understand the context provided.
2. Identify the key information related to the question within the context.
3. Formulate a concise answer based on the relevant information.
4. Ensure your final answer directly addresses the question.

###

Remember:
- It's crucial to base your answer solely on the **PROVIDED CONTEXT**. 
- DO NOT use any external knowledge or information not present in the given materials.
- If you can't find the source of the answer, you should answer that "제공된 문서에서 질문에 대한 답변을 찾을 수 없습니다."

###

# Here is the user's QUESTION that you should answer:
{question}

# Here is the CONTEXT that you should use to answer the question:
{context}

# Your final ANSWER to the user's QUESTION:
"""
