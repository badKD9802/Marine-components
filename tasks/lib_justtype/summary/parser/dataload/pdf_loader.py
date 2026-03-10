import os

from ..parsing import PDFParser, process_pdf_nodes_by_page
from ..utils import resave_pdf, save_json_file  # , extract_file_name
from .base_loader import BaseLoader


class PDFLoader(BaseLoader):
    """
    PDF 파일을 처리하는 데이터 로더 클래스
    """

    def load(self):
        parser = PDFParser(self.file_path)
        return parser.extract_pdf_info()

    def parse(self, text_output_path, image_output_path):
        parser = PDFParser(self.file_path)
        try:
            try:
                parsed_pymupdf_table_doc, pdf_with_tables = parser.parse_pdf_with_openparse()
                reorder_nodes = process_pdf_nodes_by_page(parsed_pymupdf_table_doc)

            except Exception as e:
                print(f"Error : {str(e)}")
                print("Openparse dataload 불가로 fitz로 다시저장 후 reload 진행")
                resave_pdf(self.file_path, self.file_path)
                parsed_pymupdf_table_doc, pdf_with_tables = parser.parse_pdf_with_openparse()
                reorder_nodes = process_pdf_nodes_by_page(parsed_pymupdf_table_doc)

            annotations = ["_".join(list(node.variant)) for node in reorder_nodes.nodes]
            parser.save_image_with_bboxes(
                pdf_with_tables, reorder_nodes.nodes, self.document_id, image_output_path, annotations=annotations
            )
            text = parser.group_text_with_openparse(reorder_nodes)
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
