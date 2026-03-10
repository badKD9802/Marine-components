import os
import subprocess

from ..parsing import extract_all_text, extract_table_text, extract_tables_from_section, get_namespaces, unzip_hwpx
from ..utils import save_json_file  # , extract_file_name
from .base_loader import BaseLoader


class HWPXLoader(BaseLoader):
    """
    HWPX 파일을 처리하는 데이터 로더 클래스
    """

    def load(self):
        # 241115) output 경로 수정
        self.unzip_file_path = os.path.join(self.output_path, "convert_file", "hwpx_contents")
        if not os.path.exists(self.unzip_file_path):
            os.makedirs(self.unzip_file_path)
        unzip_hwpx(self.file_path, self.unzip_file_path)
        return "Unknown"

    def parse(self, text_output_path, image_output_path):
        # 섹션 파일 경로와 텍스트 및 표 추출
        section_file = os.path.join(self.unzip_file_path, "Contents", "section0.xml")
        # 네임스페이스 추출
        namespaces = get_namespaces(section_file)
        # 모든 텍스트와 테이블 내 텍스트 추출
        all_text_content = extract_all_text(section_file, namespaces)
        table_text_content = extract_table_text(section_file, namespaces)

        # 테이블 내 텍스트를 제외한 텍스트 추출
        # text_content = ' '.join([text for text in all_text_content.split() if text not in table_text_content.split()])
        text_content = [text for text in all_text_content.split() if text not in table_text_content.split()]
        tables_html = extract_tables_from_section(section_file, namespaces)
        # table_content = [table for table in tables_html]  # HHHHHHHHH ruff의 요청에 의해서 아래 라인으로 수정함.
        table_content = list(tables_html)

        text = {"contents": {"1": {"text": text_content, "table": table_content}}}

        # name_ = extract_file_name(self.file_path)
        # if "$" in name_:
        #     document_id = name_.split("$")[0]
        #     name = name_.split("$")[1]
        # else:
        #     document_id = name_
        #     name = name_

        text_output = {"metadata": {"document_id": self.document_id}}
        text_output.update(text)
        save_json_file(text_output, f"{text_output_path}/{self.document_id}.json")

        # 소스 파일과 목적지 파일 경로
        source_file = os.path.join(self.unzip_file_path, "Preview", "PrvImage.png")
        destination_file = os.path.join(image_output_path, f"{self.document_id}_1.png")

        # cp 명령어 실행
        try:
            subprocess.run(["cp", source_file, destination_file], check=True)
            print(f"Copied {source_file} to {destination_file}")
        except subprocess.CalledProcessError as e:
            print(f"Error occurred while copying: {e}")

        return text_output, None, None
