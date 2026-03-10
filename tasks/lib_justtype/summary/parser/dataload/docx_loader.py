import os

from ..parsing import PDFParser, convert_docx_to_pdf
from ..utils import resave_pdf, save_json_file  # , extract_file_name
from .base_loader import BaseLoader


class DOCXLoader(BaseLoader):
    """
    DOCX 파일을 처리하는 데이터 로더 클래스
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

        self.convert_pdf_file = os.path.join(convert_file_path, f"{self.document_id}.pdf")

        if not os.path.exists(self.convert_pdf_file):
            print(f"convert_pdf_file : {self.convert_pdf_file}")
            convert_docx_to_pdf(self.file_path, convert_file_path)
        else:
            print(f"convert_pdf_file : {self.convert_pdf_file}")
        parser = PDFParser(self.convert_pdf_file)
        return parser.extract_pdf_info()

    def parse(self, text_output_path, image_output_path):
        # 241204) name 대신 id 사용
        # name = extract_file_name(self.convert_pdf_file)
        parser = PDFParser(self.convert_pdf_file)
        try:
            try:
                parsed_pymupdf_table_doc, pdf_with_tables = parser.parse_pdf_with_openparse()
            except Exception as e:
                print(f"Error : {str(e)}")
                print("Openparse dataload 불가로 fitz로 다시저장 후 reload 진행")
                resave_pdf(self.file_path, self.file_path)
                parsed_pymupdf_table_doc, pdf_with_tables = parser.parse_pdf_with_openparse()

            annotations = ["_".join(list(node.variant)) for node in parsed_pymupdf_table_doc.nodes]
            parser.save_image_with_bboxes(
                pdf_with_tables, parsed_pymupdf_table_doc.nodes, self.document_id, image_output_path, annotations=annotations
            )
            text = parser.group_text_with_openparse(parsed_pymupdf_table_doc)
            tool_ = "Openparse"
            error_ = None
        except Exception as e:
            print(f"Error: {str(e)}")
            print("Openparse Error -> Pdfplumber Start")
            text = parser.parse_pdf_with_pdfplumber(self.document_id, text_output_path, image_output_path)
            tool_ = "Pdfplumber"
            error_ = str(e)

        text_output = {"metadata": {"document_id": self.document_id}}
        text_output.update(text)
        save_json_file(text_output, os.path.join(text_output_path, f"{self.document_id}.json"))

        return text_output, tool_, error_

    def get_convert_pdf_file(self):
        return self.convert_pdf_file
