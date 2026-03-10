from collections.abc import Sequence

import numpy as np

from ..common.prompt_manager import PromptManager
from .data_structures import SummaryGroup, Summation


class BaseTool:
    def __init__(
        self,
        llm,
        embedding_client,
        logger,
        config,
    ):
        self.llm = llm
        self.ec = embedding_client
        self.logger = logger

    def _set_prompt_manager(self, step: str):
        return PromptManager(self.logger, step, self.llm)

    # 생성될 문장 개수 설정
    def _determine_sentence_range(self, current_depth: int = 0) -> str:
        if current_depth == 1:
            return "2~5"
        elif current_depth == 2:
            return "1~3"
        elif current_depth == 3:
            return "1~2"
        else:
            return "5~7"


class DocumentSemanticGrouper(BaseTool):
    def __init__(
        self,
        llm,
        embedding_client,
        logger,
        config,
    ):
        super().__init__(llm, embedding_client, logger, config)
        self.similarity_threshold = config["similarity_threshold"]
        self.use_dynamic_threshold = config["use_dynamic_threshold"]
        self.max_iterations = int(config["max_iterations"])
        self.prompt_max_length = int(config["prompt_max_length"])
        if not self.use_dynamic_threshold and self.similarity_threshold is None:
            raise ValueError("If not using dynamic threshold, a fixed threshold must be provided.")
        self.pm = self._set_prompt_manager("summary")

    def recursive_grouping(self, documents: Sequence[SummaryGroup], current_iteration) -> list[list[SummaryGroup]]:
        """문서를 그룹화하고 필요에 따라 재귀적으로 그룹을 분할합니다."""
        self.logger.info(f"current_iteration: {current_iteration}")
        groups = self._documents_grouping(documents)
        results = []
        for group in groups:
            combined_text = "\n\n".join([doc["summary"] for doc in group])
            token_length = self.ec.get_token_length(combined_text)

            # 그룹의 토큰 길이를 확인하고, 최대 토큰 수를 초과하면 재귀적으로 그룹화합니다.
            if (token_length < self.prompt_max_length) or (len(group) < 3) or (current_iteration >= self.max_iterations):
                results.append(group)
            else:
                self.logger.debug(f"\n\tCombined text exceeds max tokens ({token_length} > {self.prompt_max_length}), splitting group")
                results.extend(self.recursive_grouping(group, current_iteration + 1))
        return results

    def _documents_grouping(self, documents: Sequence[SummaryGroup]) -> list[list[SummaryGroup]]:
        # 각 문서의 임베딩 생성
        embeddings = self._get_embedding([doc["summary"] for doc in documents])

        if self.use_dynamic_threshold:
            # 유사도 계산
            similarities = [self._get_similarity(embeddings[i - 1], embeddings[i]) for i in range(1, len(embeddings))]

            # 동적 임계값 계산
            self.similarity_threshold = self._find_optimal_threshold(similarities, len(documents))

        groups = []
        current_group = [documents[0]]

        for i in range(1, len(documents)):
            # 연속된 페이지가 아닌 경우 그룹화 x
            if int(documents[i]["page_labels"][-1]) != int(documents[i - 1]["page_labels"][0]) + 1:
                groups.append(current_group)
                current_group = [documents[i]]
            else:
                similarity = self._get_similarity(embeddings[i - 1], embeddings[i])
                if similarity >= self.similarity_threshold:
                    current_group.append(documents[i])
                else:
                    groups.append(current_group)
                    current_group = [documents[i]]
        if current_group:
            groups.append(current_group)
        self.logger.info(f"\n\t{len(documents)} documents grouped into {len(groups)} groups based on similarity")
        return groups

    def _get_embedding(self, texts: list[str]):
        embeddings = []
        for text in texts:
            embeddings.append(self.ec.get_embedding(text))
        return embeddings

    def _get_similarity(self, vector1, vector2) -> float:
        # Ensure inputs are tensors
        if not isinstance(vector1, np.ndarray) or not isinstance(vector2, np.ndarray):
            raise ValueError("Both inputs must be NumPy arrays.")
        # Normalize the vectors
        norm1 = np.linalg.norm(vector1)
        norm2 = np.linalg.norm(vector2)

        if norm1 == 0 or norm2 == 0:
            raise ValueError("Input vectors must not be zero vectors.")

        # Calculate cosine similarity
        return np.dot(vector1, vector2) / (norm1 * norm2)

    # 생성된 청크들의 평균 문서 개수가 min-max 내에 포함되지 않으면 조절
    def _find_optimal_threshold(self, similarities: list[float], doc_count: int) -> float:
        min_chunk_size = max(doc_count // 20, 1)
        max_chunk_size = max(doc_count // 5, 4)
        threshold_adjustment = len(similarities) * 0.001
        median_score = np.median(similarities)
        std_dev = np.std(similarities)
        self.logger.debug(f"\n\tdocments count: {doc_count}, min: {min_chunk_size}, max: {max_chunk_size}")

        low = max(0.0, float(median_score - std_dev))
        high = min(1.0, float(median_score + std_dev))
        self.logger.debug(f"\n\tFinding optimal threshold between {low} and {high}")

        for _ in range(self.max_iterations):
            calculated_threshold = (low + high) / 2
            split_indices = [i + 1 for i, sim in enumerate(similarities) if sim < calculated_threshold]

            chunk_sizes = [end - start for start, end in zip([0] + split_indices, split_indices + [len(similarities) + 1])]

            median_chunk_size = np.median(chunk_sizes)
            if min_chunk_size < median_chunk_size <= max_chunk_size:
                self.logger.debug(f"\n\tMedian chunk size {median_chunk_size} / Optimal threshold found: {calculated_threshold}")
                return calculated_threshold
            elif median_chunk_size <= min_chunk_size:
                high = calculated_threshold - threshold_adjustment
                self.logger.debug(f"\n\tMedian chunk size {median_chunk_size} below minimum, adjusting high to {high}")
            else:
                low = calculated_threshold + threshold_adjustment
                self.logger.debug(f"\n\tMedian chunk size {median_chunk_size} above maximum, adjusting low to {low}")

        optimal_threshold = (low + high) / 2
        self.logger.warning(f"\n\tMax iterations reached. Returning threshold: {optimal_threshold}")
        return optimal_threshold


class PageClassifier(BaseTool):
    def __init__(
        self,
        llm,
        embedding_client,
        logger,
        config,
    ):
        super().__init__(llm, embedding_client, logger, config)
        self.page_initial_length = int(config["page_initial_length"])
        self.toc_pm = self._set_prompt_manager("analysis_toc")
        self.ref_pm = self._set_prompt_manager("analysis_ref")

    def analyze_pages(self, page_docs: dict[str, SummaryGroup]):
        """Analyzes the pages."""
        try:
            self._check_page("table_of_contents", page_docs)
            self._check_page("bibliography", page_docs)
            self.logger.info("success first page analysis")
        except Exception as e:
            self.logger.error(f"Error during page analysis: {e}", exc_info=True)
            raise f"Error during page analysis: {e}" from e

    def _check_page(self, type: str, page_docs: dict[str, SummaryGroup]):
        """Check if the page is table of contents or reference."""
        # 목차는 앞 20%, 참고문헌은 뒤 20%만 검수
        slice_idx = max(int(len(page_docs) * 0.2), 10)
        tag = f"is_{type}_page"
        if type == "table_of_contents":
            check_cutoff = list(page_docs.values())[:slice_idx]
            pm = self.toc_pm
        elif type == "bibliography":
            check_cutoff = list(page_docs.values())[-slice_idx:]
            pm = self.ref_pm

        for doc in check_cutoff:
            # 첫 번째 응답
            res1 = pm.chain.invoke(
                {
                    "user_input": doc["text"][: self.page_initial_length],
                }
            )

            # 두 번째 응답
            res2 = pm.chain.invoke(
                {
                    "user_input": doc["text"][: self.page_initial_length],
                }
            )
            # 파싱 실패시 기본값으로 False 설정
            parsed_data_1 = pm.parse_data_with_correction(res1, ["decision"])
            parsed_data_1 = parsed_data_1.get("decision", ["N"])[0]
            parsed_data_2 = pm.parse_data_with_correction(res2, ["decision"])
            parsed_data_2 = parsed_data_2.get("decision", ["N"])[0]

            # 두 번 모두 True인 경우에만 설정
            if (parsed_data_1.upper() == "Y") and (parsed_data_2.upper() == "Y"):
                doc[tag] = True
            else:
                doc[tag] = False
        self.logger.info(f"filtered {type}")

        # 특수 페이지가 한 페이지만 존재하거나 없으면 검수 생략
        toc_count = sum(1 for doc in check_cutoff if doc.get(tag))
        if toc_count > 1:
            for index, doc in enumerate(check_cutoff):
                if doc.get(tag):
                    # 해당 문서의 앞뒤 3개 문서 확인
                    start_index = max(0, index - 3)
                    end_index = min(len(check_cutoff), index + 4)
                    # 앞뒤 3개 문서 중 다른 특수 페이지가 있는지 확인
                    # 없다면 오분류로 판단하여 False로 변경
                    if all(not check_cutoff[i].get(tag) for i in range(start_index, end_index) if i != index):
                        doc[tag] = False
        self.logger.info(f"success {type} analysis")

        # 목차 페이지 추가 검수(표목차/그림목차)
        # 전체 문장 중 "표" 또는 "그림"이 들어간 문장이 80% 이상이라면 목차 페이지로 판단
        if type == "table_of_contents":
            for doc in check_cutoff:
                kwd_cnt = 0
                sentence_cnt = len(doc["sentences"])
                for sentence in doc["sentences"]:
                    if ("표" in sentence) or ("그림" in sentence):
                        kwd_cnt += 1
                if sentence_cnt == 0:
                    continue
                elif kwd_cnt / sentence_cnt > 0.8:
                    self.logger.info(f"toc page detected: {doc['page_labels'][0]}")
                    doc["is_table_of_contents_page"] = True
            self.logger.info("success check_additional_toc")


class PageFilter(BaseTool):
    def __init__(
        self,
        llm,
        embedding_client,
        logger,
        config,
    ):
        super().__init__(llm, embedding_client, logger, config)
        self.embedding_max_length = int(config["embedding_max_length"])
        self.prompt_min_length = int(config["prompt_min_length"])
        self.page_initial_length = int(config["page_initial_length"])
        self.prompt_max_length = int(config["prompt_max_length"])
        self.max_iterations = int(config["max_iterations"])
        self.pm = self._set_prompt_manager("summary")

    def filter_summary_pages(self, page_docs: dict[str, SummaryGroup]):
        """Decides which pages are targets for summarization."""
        try:
            # 마지막 table_of_contents 페이지 확인
            last_toc_index = -1
            for index, doc in enumerate(page_docs.values()):
                if doc.get("is_table_of_contents_page"):
                    last_toc_index = index

            for index, doc in enumerate(page_docs.values()):
                # 토큰 길이 확인
                doc["token_length"] = self.ec.get_token_length(doc["text"])
                # 목차 이전 페이지는 요약대상에서 제외
                if index <= last_toc_index:
                    doc["is_skip"] = True
                # 참고문헌 페이지는 요약대상에서 제외
                elif doc.get("is_bibliography_page"):
                    doc["is_skip"] = True
                # 너무 짧은 페이지는 요약대상에서 제외
                elif doc["token_length"] < self.prompt_min_length:
                    doc["is_skip"] = True
                # 요약 전처리
                else:
                    self._preprocess_text(doc)
        except Exception as e:
            self.logger.error(f"Error during page filtering: {e}", exc_info=True)
            raise f"Error during page filtering: {e}" from e

    def _preprocess_text(self, doc: SummaryGroup):
        # 너무 긴 경우 분할해서 요약 후 요약문을 병합한 텍스트로 원문을 대체
        if doc["token_length"] > self.prompt_max_length:
            self.logger.debug("Text exceeds limit, splitting text.")
            text_list = self.split_text(doc["text"])
            responses = self.pm.chain.batch(
                [
                    {
                        "title": "",
                        "user_input": text,
                        "sentence_range": self._determine_sentence_range(),
                    }
                    for text in text_list
                ]
            )
            summaries = []
            for response in responses:
                parsed_data = self.pm.parse_data_with_correction(response, ["point"])
                # 파싱 실패시 해당 텍스트 스킵
                if parsed_data == {}:
                    self.logger.error("No parsed data")
                    continue
                summaries.append("\n".join(parsed_data["point"]))
            doc["summary"] = "\n".join(summaries)
        else:
            doc["summary"] = doc["text"]

    # 페이지 내의 텍스트가 너무 길 경우 절반씩 분할
    def split_text(self, text, current_iteration: int = 0) -> list[str]:
        if self.ec.get_token_length(text) < self.prompt_max_length or current_iteration >= self.max_iterations:
            return [text]

        idx_1 = int(len(text) * 0.6)
        idx_2 = int(len(text) * 0.4)

        text_1 = text[:idx_1]
        text_2 = text[idx_2:]
        return self.split_text(text_1, current_iteration + 1) + self.split_text(text_2, current_iteration + 1)


class Summarizer(BaseTool):
    def __init__(
        self,
        llm,
        embedding_client,
        logger,
        config,
    ):
        super().__init__(llm, embedding_client, logger, config)
        self.pm = self._set_prompt_manager("summary")

    def recursive_group_and_summarize(
        self,
        document,
        grouper: DocumentSemanticGrouper,
        max_depth: int = 4,
        current_depth: int = 1,
    ):
        """문서를 재귀적으로 그룹화 및 요약 생성"""
        try:
            if current_depth >= max_depth:
                self.logger.error("Maximum recursion depth exceeded")
                return

            sentence_range = self._determine_sentence_range(current_depth)
            prev_group = document["group_list"][-1]["groups"]
            now_group = {}
            now_group_template = {"depth": current_depth, "groups": now_group}
            document["group_list"].append(now_group_template)
            self.logger.debug(f"\n\tRecursion depth {current_depth} / sentence range: {sentence_range}")
            filtered_results = [doc for doc in prev_group.values() if not doc.get("is_skip")]

            # 문서 그룹화
            grouped_documents = grouper.recursive_grouping(filtered_results, 1)

            # 해당 depth의 그룹 생성
            for i, group in enumerate(grouped_documents):
                page_labels = []
                for doc in group:
                    page_labels.extend(doc["page_labels"])
                combined_text = "\n\n".join([doc["summary"] for doc in group])

                # 그룹내 요약문들을 모아 하나의 요약문 생성
                input_data = {
                    "title": "",
                    "user_input": combined_text,
                    "sentence_range": sentence_range,
                }
                response = self.pm.chain.invoke(input_data)
                parsed_data = self.pm.parse_data_with_correction(response, ["title", "point"])
                # 파싱 실패시 해당 그룹 스킵
                if parsed_data == {}:
                    self.logger.error("No parsed data")
                    continue

                now_group[i + 1] = SummaryGroup(
                    text=combined_text,
                    page_labels=page_labels,
                    topic=parsed_data["title"][0],
                    sentences=parsed_data["point"],
                    summary="\n".join(parsed_data["point"]),
                )

            # 전체 요약 텍스트 결합
            local_summaries = "\n\n".join([doc["summary"] for doc in now_group.values()])
            total_tokens = self.ec.get_token_length(local_summaries)
            # 전체 요약을 위한 텍스트가 너무 길면 추가 그룹화
            if total_tokens > grouper.prompt_max_length:
                self.logger.info(f"\n\tTotal tokens {total_tokens} exceed max_tokens {grouper.prompt_max_length}, recursing")
                self.recursive_group_and_summarize(
                    document,
                    grouper,
                    max_depth=max_depth,
                    current_depth=current_depth + 1,
                )
            else:
                self.logger.info(f"Total tokens {total_tokens} within limit")
        except Exception as e:
            self.logger.error(f"Error during recursive grouping and summarizing: {e}", exc_info=True)
            raise f"Error during recursive grouping and summarizing: {e}" from e

    def generate_final_summary(self, document, file_name):
        """주어진 문서의 최종 요약 생성"""
        try:
            final_summary_group = document["group_list"][-1]["groups"]
            local_summaries = "\n\n".join([doc["summary"] for doc in final_summary_group.values()])

            input_data = {
                "title": file_name,
                "user_input": local_summaries,
                "sentence_range": self._determine_sentence_range(),
            }
            response = self.pm.chain.invoke(input_data)
            parsed_data = self.pm.parse_data_with_correction(response, ["key_argument", "point"])
            # 전체 요약은 파싱 실패시 스킵 불가 -> 예외 발생
            assert parsed_data != {}, "No parsed data"

            document["topic"] = parsed_data["key_argument"][0]
            document["sentences"] = parsed_data["point"]
            document["summary"] = "\n".join(parsed_data["point"])
            self.logger.debug(f"Summarized all with topic '{document['topic']}'")
        except Exception as e:
            self.logger.error(f"Error during final summary generation: {e}", exc_info=True)
            raise f"Error during final summary generation: {e}" from e

    def restructure_data(self, document):
        """response 구조에 맞게 결과 재구조화"""
        summary_list = []
        # 전문 요약
        summary_list.append(
            Summation(
                result_order=0,
                index_text="",
                start_page_text="",
                end_page_text="",
                content=document["summary"],
            )
        )
        # 국소 요약(첫번째 단계 요약)
        local_summary = document["group_list"][1]["groups"]
        for k, doc in local_summary.items():
            summary_list.append(
                Summation(
                    result_order=int(k),
                    index_text=doc["topic"],
                    start_page_text=str(doc["page_labels"][0]),
                    end_page_text=str(doc["page_labels"][-1]),
                    content=doc["summary"],
                )
            )

        return summary_list
