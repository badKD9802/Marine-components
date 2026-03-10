from typing import TypedDict

from pydantic import BaseModel


class SummaryGroup(TypedDict):
    text: str
    page_labels: list[str]
    is_skip: bool
    token_length: int
    topic: str
    summary: str
    sentences: list[str]


class Summation(BaseModel):
    result_order: int
    index_text: str
    start_page_text: str
    end_page_text: str
    content: str


# class Summation(TypedDict):
#     result_order: int
#     index_text: str
#     start_page_text: str
#     end_page_text: str
#     content: str
