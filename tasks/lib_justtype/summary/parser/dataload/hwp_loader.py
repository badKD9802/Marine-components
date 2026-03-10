import os

from ..parsing import PDFParser, convert_html_to_pdf, convert_hwp_to_html
from ..utils import save_json_file  # , extract_file_name
from .base_loader import BaseLoader


class HWPLoader(BaseLoader):
    """
    HWP 파일을 처리하는 데이터 로더 클래스
    """

    def load(self):
        # name_ = extract_file_name(self.file_path)
        # if "$" in name_:
        #     self.document_id = name_.split("$")[0]
        #     name = name_.split("$")[1]
        # else:
        #     self.document_id = name_
        #     name = name_

        # 241115) output 경로 수정
        # 241204) 파일명 수정
        convert_file_path = os.path.join(self.output_path, "convert_file")
        if not os.path.exists(convert_file_path):
            os.makedirs(convert_file_path)

        if not os.path.exists(os.path.join(convert_file_path, f"{self.document_id}.pdf")):
            convert_html_dir = os.path.join(convert_file_path, "convert_hwp_to_html")
            convert_hwp_to_html(self.file_path, convert_html_dir)

            self.convert_pdf_file = os.path.join(convert_file_path, f"{self.document_id}.pdf")
            print(f"convert_html_dir : {convert_html_dir}")
            print(f"convert_pdf_file : {self.convert_pdf_file}")
            convert_html_to_pdf(convert_html_dir, self.convert_pdf_file)
        else:
            self.convert_pdf_file = os.path.join(convert_file_path, f"{self.document_id}.pdf")
        parser = PDFParser(self.convert_pdf_file)
        return parser.extract_pdf_info()

    def parse(self, text_output_path, image_output_path):
        # 241204) name 대신 id 사용
        # name = extract_file_name(self.convert_pdf_file)
        parser = PDFParser(self.convert_pdf_file)
        try:
            text = parser.parse_pdf_with_pdfplumber(self.document_id, text_output_path, image_output_path)
            tool_ = "Pdfplumber"
            error_ = None
        except Exception as e:
            print("HWP -> Pdfplumber Error")
            print(f"Error: {str(e)}")
            text = {}
            tool_ = "Pdfplumber"
            error_ = str(e)

        text_output = {"metadata": {"document_id": self.document_id}}
        text_output.update(text)
        save_json_file(text_output, os.path.join(text_output_path, f"{self.document_id}.json"))

        return text_output, tool_, error_

    def get_convert_pdf_file(self):
        return self.convert_pdf_file
