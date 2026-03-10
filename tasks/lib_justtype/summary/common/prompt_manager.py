from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from .prompts import (
    correction_prompt,
    format_analysis_ref,
    format_analysis_toc,
    format_question,
    format_summary,
    template_analysis_ref,
    template_analysis_toc,
    template_question,
    template_summary,
)
from .utils import extract_contents

templates = {
    "analysis_toc": (template_analysis_toc, format_analysis_toc),
    "analysis_ref": (template_analysis_ref, format_analysis_ref),
    "summary": (template_summary, format_summary),
    "question": (template_question, format_question),
}


class PromptManager:
    def __init__(self, logger, step, llm):
        self.logger = logger
        self.step = step
        self.llm = llm
        self._set_output_format()
        self._set_prompt()
        self._set_chain()

    def _set_output_format(self):
        self.output_format = templates[self.step][1]

    def _set_prompt(self):
        self.prompt = self._get_prompt(templates[self.step][0])
        self.correction_prompt = self._get_prompt(correction_prompt)

    def _set_chain(self):
        self.chain = self.prompt | self.llm | StrOutputParser()
        self.correction_chain = self.correction_prompt | self.llm | StrOutputParser()

    def _get_prompt(self, template):
        return ChatPromptTemplate(messages=[("user", template)], partial_variables={"format_instructions": self.output_format})

    # 응답을 파싱하여 필요한 정보를 추출
    def parse_data_by_tags(self, response: str, tags: list[str]):
        parsed_data = {}
        for tag in tags:
            content = extract_contents(response, tag)
            if content != []:
                parsed_data[tag] = content
            else:
                raise ValueError(f"Tag <{tag}> not found in response.")
        return parsed_data

    # 응답을 파싱하여 필요한 정보를 추출 + 파싱 실패 시 수정 요청
    def parse_data_with_correction(self, response: str, tags: list[str]) -> dict:
        parsed_data = {}
        try:
            parsed_data = self.parse_data_by_tags(response, tags)
        except Exception as e:
            input_data = {
                "error": str(e),
                "response": response,
            }
            try:
                correction_response = self.correction_chain.invoke(input_data)
                parsed_data = self.parse_data_by_tags(correction_response, tags)
            except Exception as e2:
                self.logger.error(f"Error during response parsing: {e2}")
        finally:
            self.logger.debug("parse_data_with_correction: parsing ok")
        return parsed_data
