import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union, cast

import numpy as np
import pandas as pd

from app.justtype.rag.just_model import Tokenizer

# from automation_service.utils import read_yaml
#
# from app.utils import util

logger = logging.getLogger(__name__)


class ChatsamStructureMaker:
    """DLA 결과를 ChatSAM의 Input 형식으로 변환하기 위한 클래스"""

    def __init__(
        self,
        dla_result: dict,
        # cfg_path: Union[Path, str],
        cfg_data: dict,
        original_file_name: Optional[str] = None,
    ):
        self.dla_result = dla_result
        # 공백문자가 언더바로 대체된, 실제 서버에 저장되어있는 파일 이름
        self.pdf_name = self.dla_result["pdfName"]
        self.dla_result_name = Path(self.pdf_name).with_suffix(".json")
        # self.cfg_path = Path(cfg_path)
        self.cfg_data = cfg_data
        # 업로드 될 때 전달받았던 원본 파일 이름
        self.original_file_name = original_file_name if original_file_name else self.pdf_name
        # 챗샘에서는 pdf만 받을 수 있기 때문에 pdf로 수정
        self.original_file_name = Path(self.original_file_name).with_suffix(".pdf")

        # table 처리 tag
        self.tbl_stag = "<AgileTable_start>"
        self.tbl_etag = "<AgileTable_end>"
        # 컨텐츠 추출 대상 타입
        self.extract_contents_type = [
            "Caption",
            "Formula",
            "List-item",
            "Picture",
            "Section-header",
            "Text",
            "Title",
            "RegionKV",
        ]
        # 타이틀이 될 수 있는 후보 타입
        self.title_candidate_type = [
            "Text",
            "Title",
            "Section-header",
            "List-item",
        ]

        self.max_token = 512 - 20  # 카테고리가 내용에 포함되기 때문에 20 제거

        # title 데이터가 저장될 영역
        self.df_title = pd.DataFrame(
            {
                "crawling_id": pd.Series(dtype="string"),
                "category": pd.Series(dtype="string"),
                "level": pd.Series(dtype="int32"),
                "page_number": pd.Series(dtype="int32"),
            }
        )
        # Crawling 데이터가 저장될 영역
        self.df_crawling_data = pd.DataFrame(
            {
                "crawling_id": pd.Series(dtype="string"),
                "link_seq": pd.Series(dtype="int32"),
                "category": pd.Series(dtype="string"),
                "dp_category": pd.Series(dtype="string"),
                "level": pd.Series(dtype="int32"),
                "chunk": pd.Series(dtype="string"),
                "page_number": pd.Series(dtype="int32"),
                "table_cnt": pd.Series(dtype="int32"),
            }
        )

    async def chunking(self, tokenizer_name: str) -> Optional[pd.DataFrame]:
        logger.info(f'********** Chunking Start : "{self.dla_result_name}"')

        # Step 1 ===========================================
        logger.info(f'Step 1 : Extract title & page info from "{self.dla_result_name}"')

        self.df_title = self.extract_title()

        if len(self.df_title) == 0:
            logger.info("Step 1 : No title data extracted. Skip all steps")
            return None

        # title에서 추출한 데이터를 crawling_data에 추가
        self.df_crawling_data = self.df_title.reindex(columns=self.df_crawling_data.columns)

        # Step 2 ===========================================
        logger.info("Step 2 : Add blank page and overlapping page")

        self.make_pageinfo()

        # Step 3 ===========================================
        logger.info("Step 3 : Crawling the text of each page")

        # 각 페이지의 텍스트를 crawling
        self.crawling_contents()

        # Step 4 ===========================================
        logger.info("Step 4 : Arrange Main Chunk as title content")

        # Main Chunk 를 title 에 맞게 정리
        self.arrange_chunk()

        # Step 5 ===========================================
        logger.info("Step 5 : Preprocess Main Chunk")

        # Chunking 위해 crawling 데이터를 정리
        self.df_cdata = self.cdata_from_crawling_data()

        # Chunking 을 위해 데이터를 전처리한다.
        self.preprocess_data()

        # Step 6 ===========================================
        logger.info("Step 6 : Split the Main Chunk into sub-chunks")

        # Main Chunk 를 512 단위 SubChunk 로 분리
        # NOTE: 다른 모델의 토크나이저가 필요할 경우 수정 필요

        # tokenizer = util.get_tokenizer("beomi/Llama-3-Open-Ko-8B")
        tokenizer = Tokenizer(tokenizer_name).tokenizer
        self._split_mainchunk(tokenizer=tokenizer, max_length=self.max_token)

        # Step 7 ===========================================
        logger.info("Step 7 : Convert to ChatSAM structure")

        # 최종 결과물을 ChatSAM 구조에 맞도록 변환
        chatsam_result = self.convert_to_chatsam_structure()

        logger.info(f'********** Crawling finish : "{self.dla_result_name}"')

        return chatsam_result

    def extract_title(self) -> pd.DataFrame:
        # 섹션 레벨이 있는 경우(사용자가 섹션 레벨을 설정한 경우)
        if "section_level" in self.dla_result["pages"][0]["paragraphs"][0]:
            logger.info("extract title using section_level")
            result = self.extract_title_by_section_level()
        # 그 외의 경우 기존 방식 사용
        else:
            logger.info("extract title using config")
            result = self.extract_title_by_config()

        return result

    def extract_title_by_section_level(self) -> pd.DataFrame:
        """섹션 레벨이 있는 경우, 사용자가 직접 타이틀을 설정했을테니 해당 정보들을 이용"""
        titles = [
            {
                "crawling_id": self._generate_uuid("CW"),
                "category": paragraph["contents"].strip(),
                "level": paragraph["section_level"],
                "page_number": page["pageId"],
            }
            for page in self.dla_result["pages"]
            for paragraph in page["paragraphs"]
            if paragraph["type"] == "Title" and paragraph["contents"].strip()
        ]

        return pd.DataFrame(titles)

    # NOTE: 기존 DLAtoEXCEL에서 사용하던 title_by_pagereg 방식으로 추출
    def extract_title_by_config(self) -> pd.DataFrame:
        # config 파일에서 필요한 config 초기화
        # import yaml

        # logger.info(f"self.cfg_path = {self.cfg_path}")
        # logger.info(yaml.safe_load(str(self.cfg_path)))
        #
        # with open(self.cfg_path, encoding="utf-8") as f:
        #     cfg_data = yaml.safe_load(f)

        cfg_data = self.cfg_data["config"]
        # cfg_data = read_yaml(str(self.cfg_path))["config"]

        exclude_page = cfg_data.get("exclude_page", [])
        exclude_page = self._parse_page_ranges(exclude_page)
        appendix_title = cfg_data.get("appendix_title", "부록")
        appendix_page = cfg_data.get("appendix_page", 10000)

        extra = cfg_data.get("extra", {})
        reg_exp = extra.get("reg_exp", [])

        # DLAtoEXCEL에서 사용하던 타이틀 대상 타입
        ls_dla_type = [
            "Caption",
            "Formula",
            "List-item",
            "Picture",
            "Section-header",
            "Title",
            "Text",
            "RegionKV",
        ]

        title_list: list[dict] = []

        # 페이지 정규식은 첫장부터 차례로 진행
        for pg_idx in range(0, self.dla_result["pageLen"]):
            pgnum = pg_idx + 1  # 실제 페이지번호
            page = self.dla_result["pages"][pg_idx]  # 처리중인 페이지
            txt_data = ""

            # 제외대상 페이지이면 다음으로
            if pgnum in exclude_page:
                continue

            # appendix 로 처리해야하는 페이지가 있고 마지막 title 의 page 보다 크다면 마지막으로 설정하고 끝냄
            if appendix_page < 10000 and appendix_page <= pgnum:
                title_list.append(
                    {
                        "crawling_id": self._generate_uuid("CW"),
                        "category": appendix_title,
                        "level": 1,
                        "page_number": appendix_page,
                    }
                )
                break

            # 영역을 순회하며 내용을 추출
            for pgraph in page["paragraphs"]:
                # 텍스트는 일단 모음
                if pgraph["type"] in ls_dla_type:
                    if pgraph["contents"].strip() != "":
                        txt_data += pgraph["contents"] + "\n"

            ls_txt_data = txt_data.strip().split("\n")

            # 페이지의 각 라인 문장에 정규식 대응
            for toc in ls_txt_data:
                # 정규 표현식이 한 개 이상인 경우 순서에 맞게 처리(최대 3개)
                for reg_idx, exp in enumerate(reg_exp):
                    # 정규식이 빈값이면 다음으로
                    if self.is_empty(exp):
                        continue

                    match_data = re.search(exp, toc.strip(), flags=re.UNICODE | re.IGNORECASE)

                    if not match_data:
                        continue

                    cat_data = match_data.group()
                    title_list.append(
                        {
                            "crawling_id": self._generate_uuid("CW"),
                            "category": cat_data,
                            "level": reg_idx + 1,
                            "page_number": pgnum,
                        }
                    )

        result = pd.DataFrame(title_list)

        return result

    def make_pageinfo(self):
        """title 사이에 있는 빈 페이지 정보를 추가"""
        # 데이터 정리용 임시 dataframe
        page_info: list[dict[str, Any]] = []

        # dp_category 처리
        for i in range(len(self.df_crawling_data) - 1):
            current_page_number: int = self.df_crawling_data.at[i, "page_number"]
            next_page_number: int = self.df_crawling_data.at[i + 1, "page_number"]

            if next_page_number == current_page_number:
                page_info.append(
                    {
                        **self.df_crawling_data.iloc[i].to_dict(),
                        "link_seq": 1,
                        "dp_category": f"{self.df_crawling_data.at[i, 'category']}_{current_page_number}",
                    }
                )
            # 다음 페이지 번호에 도달할 때 까지 동일한 페이지에 대한 정보 추가
            else:
                for seq_idx, pg_num in enumerate(range(current_page_number, next_page_number)):
                    page_info.append(
                        {
                            **self.df_crawling_data.iloc[i].to_dict(),
                            "link_seq": seq_idx + 1,
                            "dp_category": f"{self.df_crawling_data.at[i, 'category']}_{pg_num}",
                            "page_number": pg_num,
                        }
                    )

        # 마지막 title 요소는 마지막 페이지까지 동일하게 진행
        last_title_data = self.df_crawling_data.iloc[-1].to_dict()

        for seq_idx, pg_num in enumerate(range(last_title_data["page_number"], self.dla_result["pageLen"] + 1)):
            page_info.append(
                {
                    **last_title_data,
                    "link_seq": seq_idx + 1,
                    "dp_category": f"{last_title_data['category']}_{pg_num}",
                    "page_number": pg_num,
                }
            )

        # 하나의 title에 대한 내용이 한 페이지를 넘어가는 경우의 확장 처리
        result_page_info = []

        for i in range(0, len(page_info) - 1):
            current_page_info = page_info[i]
            next_page_info = page_info[i + 1]
            current_page_number = current_page_info["page_number"]
            next_page_number = next_page_info["page_number"]

            # 일단 현재 목차를 옮김
            result_page_info.append(current_page_info)

            # 다음 페이지가 같으면 통과
            if current_page_number == next_page_number:
                continue

            # 페이지가 다르고 카테고리도 다르면 다음 페이지로 현재 목차정보 추가
            if current_page_info["category"].strip() != next_page_info["category"].strip():
                result_page_info.append(
                    {
                        **current_page_info,
                        "link_seq": current_page_info["link_seq"] + 1,
                        "dp_category": f"{current_page_info['category']}_{next_page_number}",
                        "page_number": next_page_number,
                    }
                )

        # 마지막 데이터 처리
        result_page_info.append(page_info[-1])

        # NaN 값 처리
        df_result = pd.DataFrame(result_page_info).replace(pd.NA, None)
        # index 재설정
        df_result.reset_index(inplace=True, drop=True)
        # 결과 저장
        self.df_crawling_data = df_result

    # 정리된 목차를 기준으로 각 페이지 내용을 Crawling
    def crawling_contents(self):
        # 데이터 정리용 임시 dataframe
        df_result = pd.DataFrame(columns=self.df_crawling_data.columns)

        prv_pg_num = -1

        # 각 페이지의 데이터를 추출한다.
        for i in range(0, len(self.df_crawling_data)):
            cur_pg_num = self.df_crawling_data.at[i, "page_number"]

            # 목차 데이터 복사
            df_result.loc[i] = self.df_crawling_data.loc[i]

            # 이전 row 와 동일한 페이지이면 추출 데이터 재사용, 다르면 페이지에서 데이터 추출
            if prv_pg_num != cur_pg_num:
                logger.debug(f" Crawling {cur_pg_num} page from {self.dla_result_name}")
                txt_data, tbl_cnt = self.extract_page(self.dla_result["pages"][cur_pg_num - 1])

            df_result.loc[i, "chunk"] = txt_data
            df_result.loc[i, "table_cnt"] = tbl_cnt

            prv_pg_num = cur_pg_num

        # DB 에서 저장하지 못하는 특수문자 처리
        df_result["chunk"] = df_result["chunk"].apply(self._del_code_excel)

        # index 재설정
        df_result.reset_index(inplace=True, drop=True)

        # 정리된 데이터 재할당
        self.df_crawling_data = df_result

    # PDF 의 해당 페이지 내용을 추출
    def extract_page(self, page):
        txt_data = ""
        tbl_cnt = 0

        # 영역을 순회하며 내용을 추출
        for pgraph in page["paragraphs"]:
            if pgraph["type"] == "Table":
                txt_data += self.extract_table_contents(pgraph)
                tbl_cnt += 1
            # 텍스트는 일단 모음
            elif pgraph["type"] in self.extract_contents_type:
                if pgraph["contents"].strip() != "":
                    txt_data += pgraph["contents"] + "\n"

        return txt_data.strip(), tbl_cnt

    def arrange_chunk(self):
        # 초기값
        pg_para = []
        prv_pgnum = 0
        i_tbl_cnt = 0
        is_new_title = True
        len_cwrow = len(self.df_crawling_data)

        for i in range(len_cwrow):
            cur_pgnum = self.df_crawling_data.at[i, "page_number"]

            # 이전 category 와 페이지가 다르면 새로운 content 설정
            if prv_pgnum != cur_pgnum:
                pg_para = self.dla_result["pages"][cur_pgnum - 1]["paragraphs"]

            # 각 데이터 초기화
            cur_cat = self.df_crawling_data.at[i, "category"].strip()
            ls_cwdata = []

            # 마지막 자료 별도 처리
            if i == len_cwrow - 1:
                nxt_cat = r"^@:#$"
            else:
                # 다음 목차의 카테고리 정보를 정규식으로 가져오기
                nxt_cat = self.df_crawling_data.at[i + 1, "category"].strip()
                if cur_cat == nxt_cat:
                    try:
                        nxt_cat = self.df_crawling_data.at[i + 2, "category"].strip()
                    except Exception:
                        pass

            # contents 를 줄단위로 처리
            while pg_para:
                line = pg_para[0]["contents"].strip()

                # 라인의 텍스트가 현재 Category 이면 contents를 모으기 시작
                if is_new_title and pg_para[0]["type"] in self.title_candidate_type and nxt_cat not in line:
                    is_new_title = False

                # contents 모으기
                elif not is_new_title:
                    # 라인의 텍스트가 다음 Category 로 시작하면 다음 자료로 넘김
                    if pg_para[0]["type"] in self.title_candidate_type and nxt_cat in line:
                        is_new_title = True
                        break

                    # category 내용이면 모음
                    dict_item = pg_para.pop(0)

                    contents = dict_item["contents"]
                    contents = contents.replace("\n", " ")

                    if dict_item["type"] == "Table":
                        contents = self.extract_table_contents(dict_item)
                        i_tbl_cnt += 1

                    # 내용에서 타이틀 자체의 텍스트 제거
                    elif dict_item["type"] in self.title_candidate_type:
                        if cur_cat in contents:
                            contents = contents.replace(cur_cat, "").strip()

                    ls_cwdata.append(contents)

                # 전부 아니면 버림
                else:
                    pg_para.pop(0)

            # 모은 데이터 저장 및 변수 업데이트
            self.df_crawling_data.loc[i, "chunk"] = "\n".join(ls_cwdata)
            self.df_crawling_data.loc[i, "table_cnt"] = i_tbl_cnt
            prv_pgnum = cur_pgnum
            i_tbl_cnt = 0

    def extract_table_contents(self, pgraph):
        # NOTE: dla에서 테이블 내부 줄바꿈을 <br>로 표기하기 때문에 해당 문자를 공백으로 대체
        contents: str = pgraph["contents"].replace("<br>", " ").strip()
        remove_escape_contents = contents.replace("\n", "")

        if not remove_escape_contents.startswith(self.tbl_stag):
            contents = f"{self.tbl_stag}\n{contents}"

        if not remove_escape_contents.endswith(self.tbl_etag):
            contents = f"{contents}\n{self.tbl_etag}"

        return contents

    def cdata_from_crawling_data(self):
        df_temp_cdata = self.df_crawling_data.copy()

        # 카테고리 레벨 계산, 최소 5
        self.num_unique_categories = max(5, df_temp_cdata.level.nunique())

        columns = [
            "chunk_id",
            "crawling_id",
            "chunk_seq",
            "main_chunk",
            "page_number",
            "sub_chunk",
            "sub_chunk_seq",
            "sub_chunk_link",
            "category",
            "level",
        ]

        category_columns = [f"category_{i}" for i in range(1, self.num_unique_categories + 1)]

        # 카테고리 컬럼 생성 후 chunk_seq 다음 위치에 삽입
        for col in sorted(category_columns, reverse=True):
            columns.insert(3, col)

        df_result = pd.DataFrame(columns=columns)

        # 데이터프레임 처리
        for i, row in df_temp_cdata.iterrows():
            df_result.at[i, "chunk_id"] = ""
            df_result.at[i, "crawling_id"] = row["crawling_id"]
            df_result.at[i, "chunk_seq"] = row["link_seq"]

            # level과 일치한 category 컬럼에 값 삽입
            for level in range(1, self.num_unique_categories + 1):
                column_name = f"category_{level}"
                df_result.at[i, column_name] = row["category"] if row["level"] == level else np.nan

            df_result.at[i, "main_chunk"] = row["chunk"] if not self.is_empty(row["chunk"]) else ""
            df_result.at[i, "page_number"] = row["page_number"]
            df_result.at[i, "sub_chunk"] = ""
            df_result.at[i, "sub_chunk_seq"] = -1
            df_result.at[i, "sub_chunk_link"] = ""
            df_result.at[i, "category"] = row["category"]
            df_result.at[i, "level"] = row["level"]

        return df_result

    def preprocess_data(self):
        # category 데이터 정리 + chunk_id 부여
        prv_craw_id = chunk_id = ""
        category_cols = [col for col in self.df_cdata.columns if "category_" in col]

        for i, row in self.df_cdata.iterrows():
            i = cast(int, i)
            # 상위 카테고리가 비어있는 경우 이전 요소의 값을 상속받도록 처리
            for j in range(len(category_cols) - 1, 0, -1):
                if not self.is_empty(row[category_cols[j]]) and self.is_empty(row[category_cols[j - 1]]) and i > 0:
                    self.df_cdata.at[i, category_cols[j - 1]] = self.df_cdata.at[i - 1, category_cols[j - 1]]

            # '첫 row', '이전 row 와 title 이 다르면' 새로운 chunk_id 부여
            if i == 0 or row["crawling_id"] != prv_craw_id:
                chunk_id = self._generate_uuid("CH")
                self.df_cdata.at[i, "chunk_id"] = chunk_id
            # 같으면 기존 chunk_id 사용
            else:
                self.df_cdata.at[i, "chunk_id"] = chunk_id

            prv_craw_id = row["crawling_id"]

        df_result = pd.DataFrame(columns=self.df_cdata.columns)
        res_idx = 0

        # chunk 가 없는 중복 데이터 삭제 처리
        # Title 은 목차를 위해 chunk 자료가 없어도 최소 1 개는 남김
        for i, row in self.df_cdata.iterrows():
            # 첫 row 는 저장
            if i == 0:
                df_result.loc[res_idx] = row
                continue

            t_row = df_result.loc[res_idx]

            # 마지막에 저장된 row 와 같은 Title 일때
            if t_row["chunk_id"] == row["chunk_id"]:
                # 둘 다 chunk 있으면 추가
                if not self.is_empty(t_row["main_chunk"]) and not self.is_empty(row["main_chunk"]):
                    res_idx += 1
                    df_result.loc[res_idx] = row
                # 마지막에 저장된 row 에 chunk 없고 현재 row 에 chunk 있으면 엎어침
                elif self.is_empty(t_row["main_chunk"]) and not self.is_empty(row["main_chunk"]):
                    df_result.loc[res_idx] = row
                # 나머지는 유지
            # 마지막에 저장된 row 와 다르면 추가
            else:
                res_idx += 1
                df_result.loc[res_idx] = row

        self.df_cdata = df_result
        # index 재설정
        self.df_cdata.reset_index(inplace=True, drop=True)
        # Main Chunk 의 chunk_seq(PK) 값을 설정 (현재 main chunk 는 하나임.).
        self.df_cdata["chunk_seq"] = 1

        # category 컬럼들을 찾아서 처리
        category_cols = [col for col in self.df_cdata.columns if col.startswith("category_")]

        self.df_cdata[category_cols] = self.df_cdata[category_cols].applymap(lambda x: np.nan if pd.isnull(x) else x)
        # 이전 행의 값을 현재 행에 복사
        for i in range(1, len(self.df_cdata)):
            if all(self.df_cdata.loc[i, col] is None for col in category_cols[:-1]) and self.df_cdata.loc[i, category_cols[-1]]:
                self.df_cdata.loc[i, category_cols[:-1]] = self.df_cdata.loc[i - 1, category_cols[:-1]]

        # None 값을 제거하고 나머지 값을 왼쪽으로 이동시키는 함수
        def shift_left(row):
            non_nulls = [item for item in row if item is not None]
            return non_nulls + [None] * (len(row) - len(non_nulls))

        # 각 행에 대해 shift_left 함수 적용
        self.df_cdata[category_cols] = self.df_cdata[category_cols].apply(shift_left, axis=1, result_type="expand")

        arrange_data = self.df_crawling_data.copy()
        arrange_data = arrange_data[["crawling_id", "level"]].drop_duplicates()

        def update_level(row, arrange_data):
            row["level"] = arrange_data.loc[arrange_data["crawling_id"] == row["crawling_id"], "level"].values[0]
            return row

        self.df_cdata = self.df_cdata.apply(update_level, arrange_data=arrange_data, axis=1)

    def convert_to_chatsam_structure(self):
        result = self.df_cdata.copy()

        result["main_chunk"] = result["main_chunk"].replace("", np.nan)
        result["sub_chunk"] = result["sub_chunk"].replace("", np.nan)
        result["document_name"] = self.original_file_name
        result = result.rename(columns={"category": "section", "level": "section_level"})
        category_col = [s for s in result.columns if "category_" in s]
        result["section_group"] = result[category_col].apply(lambda x: "\n".join(x.dropna().values.astype(str)), axis=1)
        result["main_chunk"] = result.section_group + "\n" + result.main_chunk

        use_col = [
            "document_name",
            "section",
            "section_group",
            "section_level",
            "main_chunk",
            "sub_chunk",
            "sub_chunk_seq",
            "page_number",
            "sub_chunk_link",
        ]
        result = result[use_col]

        def update_sub_chunk(row):
            category_values = row["section_group"].split("\n")
            sub_chunk_values = row["sub_chunk"].split("\n")
            category_values.extend([s for s in sub_chunk_values if s not in category_values])
            category_values = ["" if pd.isna(val) or val == "nan" else val for val in category_values]
            row["sub_chunk"] = "\n".join(category_values)

            return row

        result.loc[pd.notna(result.sub_chunk), :] = result[pd.notna(result.sub_chunk)].apply(lambda row: update_sub_chunk(row), axis=1)

        # 여러 개행을 하나의 개행으로 변환
        result["sub_chunk"] = result["sub_chunk"].apply(lambda text: re.sub(r"\n+", "\n", str(text)))

        result.loc[result["sub_chunk"] == "nan", "sub_chunk"] = np.nan

        return result

    # title 별로 chunk 를 모은 후 max 토큰 크기로 자름
    def _split_mainchunk(self, tokenizer, max_length=512):
        # 데이터 정리용 임시 dataframe
        df_main_chunk = pd.DataFrame(columns=self.df_cdata.columns)
        res_idx = -1
        c_seq = 1  # 몇 개의 row 가 모였는지...
        prv_cat = cur_cat = c_chunk = ""

        # 일단 title 별로 내용을 모두 모은다.
        for i, row in self.df_cdata.iterrows():
            i = cast(int, i)
            row = cast(pd.Series, row)
            cur_cat = row["chunk_id"]

            # 현재 카테고리와 다음 카테고리가 다르면 chunk 를 저장
            if prv_cat != cur_cat:
                if i > 0 and not self.is_empty(c_chunk):
                    df_main_chunk.at[res_idx, "main_chunk"] += "\n" + c_chunk.strip()
                    df_main_chunk.at[res_idx, "c_seq"] = c_seq

                    c_chunk = ""
                    c_seq = 1

                res_idx += 1
                df_main_chunk.loc[res_idx] = row
                df_main_chunk.at[res_idx, "row_idx"] = i
                df_main_chunk.at[res_idx, "c_seq"] = c_seq

            # 카테고리가 같으면 모은다.
            else:
                c_chunk += row["main_chunk"] + "\n"
                c_seq += 1

            prv_cat = cur_cat

        # 나머지 처리
        if not self.is_empty(c_chunk):
            df_main_chunk.at[res_idx, "main_chunk"] += c_chunk.strip()
            df_main_chunk.at[res_idx, "c_seq"] = c_seq

        # index 재설정
        df_main_chunk.reset_index(inplace=True, drop=True)

        # 주어진 max token 에 맞게 main chunk 를 자른다.
        df_result = pd.DataFrame(columns=self.df_cdata.columns)
        res_idx = 0

        for i, row in df_main_chunk.iterrows():
            i = cast(int, i)
            logger.debug(f"chunk_id : ({i + 1}/{len(df_main_chunk)}) {row['chunk_id']} 처리중")
            # Chunk 길이 측정
            chunk_length = len(tokenizer(row["main_chunk"])["input_ids"])

            tx_cat = ""

            # 카테고리 정보를 subchunk 에 포함
            if not self.is_empty(row["main_chunk"]):
                categories = [
                    row[f"category_{i}"]
                    for i in range(1, self.num_unique_categories + 1)
                    if f"category_{i}" in row and not self.is_empty(row[f"category_{i}"])
                ]
                tx_cat = "\n".join(categories) + "\n"

            # Chunk 길이가 최대값보다 크면 잘라서 넣는다.
            if chunk_length >= max_length:
                # Chunk 를 잘라서 해당 페이지 번호와 함께 반환
                ls_main_chunk = self._gen_mainchunk(row, tokenizer, max_length)

                for sub_idx, data in enumerate(ls_main_chunk):
                    df_result.loc[res_idx] = row
                    df_result.at[res_idx, "main_chunk"] = (
                        row["main_chunk"].replace(self.tbl_stag, "").replace(self.tbl_etag, "").replace("\n\n", "\n").strip()
                    )
                    df_result.at[res_idx, "sub_chunk"] = tx_cat + data[0]
                    df_result.at[res_idx, "sub_chunk_seq"] = sub_idx + 1
                    df_result.at[res_idx, "page_number"] = data[1]
                    df_result.at[res_idx, "sub_chunk_link"] = f'Page {data[1]} of "{self.original_file_name}"'
                    res_idx += 1

            # 최대값보다 작으면 그냥 저장
            else:
                df_result.loc[res_idx] = row
                df_result.at[res_idx, "main_chunk"] = (
                    row["main_chunk"].replace(self.tbl_stag, "").replace(self.tbl_etag, "").replace("\n\n", "\n").strip()
                )
                df_result.at[res_idx, "sub_chunk"] = tx_cat + row["main_chunk"]
                df_result.at[res_idx, "sub_chunk_seq"] = 1
                df_result.at[res_idx, "sub_chunk_link"] = f'Page {row["page_number"]} of "{self.original_file_name}"'
                res_idx += 1

        # index 재설정
        df_result.reset_index(inplace=True, drop=True)

        # 정리된 데이터 재할당
        self.df_cdata = df_result

    # Chunk 를 잘라서 해당 페이지 번호와 함께 반환
    def _gen_mainchunk(self, row, tokenizer, max_length=512) -> list[tuple[str, int]]:
        split_length = max_length
        ls_result: list[tuple[str, int]] = []
        current_length = 0
        current_text: str = ""
        tbl_text: str = ""
        b_tbl_data = False

        # title 기준으로 chunk 를 모으기 전 원본 chunk 의 row index 와 chunk 범위를 설정
        row_idx = int(row["row_idx"])
        row_rng = row_idx + int(row["c_seq"])
        pg_num = int(self.df_cdata.at[row_idx, "page_number"])

        # 원본에서 해당 row chunk 부터 대상 범위를 처리
        for i in range(row_idx, row_rng):
            # Chunk 데이터를 개행으로 분리한다.
            sentences = self.df_cdata.at[i, "main_chunk"].split("\n")

            # 개행으로 분리된 데이터를 순회하며 정리
            for sentence in sentences:
                # 표 영역 시작 여부 확인
                if sentence.strip() == self.tbl_stag:
                    b_tbl_data = True
                    continue
                elif sentence.strip() == self.tbl_etag:
                    # 마지막 줄바꿈 제거
                    tbl_text = tbl_text.rstrip()
                    b_tbl_data = False

                # 표 데이터를 별도로 처리하기 위해 모은다.
                if b_tbl_data:
                    tbl_text += sentence + "\n"
                    continue

                # 표 데이터가 있다면 처리한다.
                if tbl_text != "":
                    # 표 데이터 길이
                    tbl_length = len(tokenizer(tbl_text)["input_ids"])

                    # 표 데이터 단독으로 최대 토큰 이상이면
                    if tbl_length > split_length:
                        # 기존 데이터에 최대 토큰 크기까지 표 데이터를 추가한다.
                        ls_sen = self._split_max_token(
                            current_text.strip() + "\n" + tbl_text,
                            tokenizer,
                            split_length,
                        )

                        # max 토큰으로 분리 후 남은 표 데이터는 다음 처리로 보낸다.
                        for sen in ls_sen:
                            ls_result.append((sen, pg_num))

                        current_text = ls_sen[-1] + "\n"
                        current_length = len(tokenizer(ls_sen[-1])["input_ids"])
                        pg_num = int(self.df_cdata.at[i, "page_number"])

                    # 기존 데이터와 표 데이터가 최대 토큰 초과이면
                    elif current_length + tbl_length > split_length:
                        # 기존 데이터를 저장하고 표 데이터를 새로 추가한다.
                        ls_result.append((current_text, pg_num))
                        current_text = tbl_text + "\n"
                        current_length = tbl_length
                        pg_num = int(self.df_cdata.at[i, "page_number"])

                    # 기존 데이터와 표 데이터 합이 최대 토큰 이하이면
                    else:
                        # 표 데이터를 쌓는다.
                        current_text += tbl_text + "\n"
                        current_length += tbl_length

                    tbl_text = ""

                    continue

                # 현재 문장의 길이
                sentence_length = len(tokenizer(sentence)["input_ids"])

                # 현재 문장을 포함하여 split_length 토큰을 넘지 않으면 문장을 쌓는다.
                if current_length + sentence_length <= split_length:
                    current_text += sentence + "\n"
                    current_length += sentence_length

                # split_length 토큰을 넘으면 쌓은 문장을 저장
                else:
                    ls_result.append((current_text, pg_num))
                    current_text = sentence + "\n"
                    current_length = sentence_length
                    pg_num = int(self.df_cdata.at[i, "page_number"])

        # 나머지 처리
        if current_text:
            ls_result.append((current_text, pg_num))

        return ls_result

    def _split_max_token(self, sentence: str, tokenizer, max_length=512) -> list[str]:
        # 현재 문장의 길이
        sentence_length = len(tokenizer(sentence)["input_ids"])

        # 크기가 max 를 넘지 않으면 다시 돌려보냄
        if sentence_length <= max_length:
            return list(sentence)

        # 결과값
        ls_result: list[str] = []
        cur_length = 0
        cur_text = ""

        # 개행으로 나눈다.
        ls_sen = sentence.split("\n")

        # 개행 기준으로 적정 사이즈 처리
        for sen in ls_sen:
            # 현재 문장의 길이
            sen_length = len(tokenizer(sen)["input_ids"])

            # 현재 문장을 포함하여 max 토큰이 넘지 않으면 문장을 쌓는다.
            if cur_length + sen_length <= max_length:
                cur_text += sen + "\n"
                cur_length += sen_length

            # max 토큰이 넘으면 쌓은 문장을 subchunk 로 저장
            else:
                ls_result.append(cur_text.strip())
                cur_text = sen + "\n"
                cur_length = sen_length

                # 한 개의 sen 문장이 max_length 토큰을 초과할 경우 예외처리 (개행이 없음)
                if sen_length > max_length:
                    # 캐릭터 단위로 자른다.
                    split_length = int(max_length * len(sen) / sen_length)

                    # 문자열을 최대 길이(split_length)만큼 잘라서 리스트에 추가
                    for i in range(0, len(sen), split_length):
                        # 자를게 남아 있으면 리스트에 추가
                        if i + split_length <= len(sen):
                            ls_result.append(sen[i : i + split_length])
                        # 마지막 자료이면 다음 처리로 보낸다.
                        else:
                            cur_text = sen[i:] + "\n"
                            cur_length = len(tokenizer(sen[i:])["input_ids"])

        # 나머지 처리
        if cur_text:
            ls_result.append(cur_text.strip())

        return ls_result

    def is_empty(self, tx_data):
        if isinstance(tx_data, str):
            return tx_data.strip() == ""
        else:
            return pd.isna(tx_data)

    def _generate_uuid(self, gbn):
        return gbn + datetime.today().strftime("%m%d%S") + str(uuid.uuid4())[:8]

    def _del_code_excel(self, tx_data):
        data = re.sub(re.compile(r"[\U000F0000-\U000F8FFF]"), "", tx_data)
        data = re.sub(r"[\x07]", "", data)
        data = re.sub(r"[\x00]", " ", data)

        return data

    # 범위 형식으로 표시된 페이지 정보를 모두 생성
    def _parse_page_ranges(self, page_range: Union[str, list[str]]) -> list[int]:
        page_list = []

        if isinstance(page_range, str):
            ranges = page_range.split(",")
        else:
            ranges = page_range

        for range_str in ranges:
            range_str = range_str.replace("~", "-")
            if "-" in range_str:
                start, end = map(int, range_str.split("-"))
                if not start:
                    start = 1
                if not end:
                    end = self.dla_result["pageLen"]
                if end < start:
                    start, end = end, start
                page_list.extend(range(start, end + 1))
            else:
                page = int(range_str)
                page_list.append(page)

        page_list = list(set(page_list))
        page_list.sort()

        return page_list
