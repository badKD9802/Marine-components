class BaseLoader:
    """
    데이터 로더의 기본 클래스
    """

    def __init__(self, file_path, output_path, document_id):
        self.file_path = file_path
        self.output_path = output_path
        self.document_id = document_id

    def load(self):
        raise NotImplementedError("load method must be implemented by subclasses")

    def parse(self, text_output_path, image_output_path):
        raise NotImplementedError("parse method must be implemented by subclasses")
