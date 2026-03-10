from .pdf_loader import PDFLoader

# from .HWPLoader import HWPLoader
# from .docx_loader import DOCXLoader
# from .hwpx_loader import HWPXLoader


def get_loader(file_path, file_type, output_path, document_id):
    """
    파일 타입에 따라 적절한 데이터 로더를 반환
    """
    if file_type == "application/pdf":
        return PDFLoader(file_path, output_path, document_id)
    # elif file_type == 'application/x-hwp':
    #     return HWPLoader(file_path, output_path, document_id)
    # elif file_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
    #     return DOCXLoader(file_path, output_path, document_id)
    # elif file_type == 'application/zip':
    #     return HWPXLoader(file_path, output_path, document_id)
    else:
        raise ValueError("Unsupported file type")
