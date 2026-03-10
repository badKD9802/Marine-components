from collections import defaultdict

import fitz
import numpy as np
import openparse
import pandas as pd
import pdfplumber
from openparse import Bbox, Node, TextElement, processing
from pdfminer.layout import LTAnno, LTChar


class PDFParser:
    """
    PDF 파일을 처리하는 클래스
    """

    def __init__(self, file_path):
        self.file_path = file_path
        self.pdf_document = fitz.open(file_path)

    def extract_pdf_info(self):
        """
        PDF 파일에서 페이지 수를 추출
        """
        return self.pdf_document.page_count

    def parse_pdf_with_openparse(self):
        """
        OpenParse를 사용하여 PDF 파일을 파싱
        """
        pymupdf_table_parser = openparse.DocumentParser(
            processing_pipeline=CustomIngestionPipeline(),
            table_args={"parsing_algorithm": "pymupdf", "table_output_format": "html"},
            # "table_output_format": "markdown"}
        )
        parsed_pymupdf_table_doc = pymupdf_table_parser.parse(self.file_path)
        pdf_with_tables = openparse.Pdf(self.file_path)
        return parsed_pymupdf_table_doc, pdf_with_tables

    def save_image_with_bboxes(self, pdf_with_tables, nodes, name, image_output_path, page_nums=None, annotations=None):
        """
        PDF에 바운딩 박스를 그려 이미지를 저장
        """
        # 241115 주석처리(이미지 저장 중단)
        # assert nodes, "At least one node is required."

        # bboxes = [node.bbox for node in nodes]
        # flattened_bboxes = _prepare_bboxes_for_drawing(bboxes, annotations)
        # marked_up_doc = pdf_with_tables._draw_bboxes(flattened_bboxes, nodes[0].coordinate_system)
        # if not page_nums:
        #     page_nums = list(range(marked_up_doc.page_count))
        # for i, page_num in enumerate(page_nums, start=1):
        #     page = marked_up_doc[page_num]
        #     img_data = page.get_pixmap()
        #     img_data.save(f"{image_output_path}/{name}_{i}.png")
        pass

    def group_text_with_openparse(self, parsed_doc):
        """
        OpenParse 결과를 기반으로 텍스트를 그룹화
        페이지 별 type 별 text, table 수집
        """
        type_pages = {}

        for node in parsed_doc.nodes:
            node_type = "_".join(list(node.variant))  # type 정보 추출 및 결합
            for element in node.__dict__["elements"]:
                page_number = element.__dict__["page"] + 1
                raw_text = element.__dict__.get("text", "")

                if node_type in ["table_text", "text_table", "table"]:
                    # "table"에 해당하는 값에서 "\n" 제거
                    cleaned_text = raw_text.replace("\n", "").strip()
                else:
                    # 다른 경우에는 그대로 사용
                    cleaned_text = raw_text.strip()

                if cleaned_text:
                    if page_number not in type_pages:
                        type_pages[page_number] = {"text": [], "table": []}

                    if node_type in ["table_text", "text_table", "table"]:
                        type_pages[page_number]["table"].append(cleaned_text)
                    elif node_type in type_pages[page_number]:
                        type_pages[page_number][node_type].append(cleaned_text)
                    else:
                        type_pages[page_number][node_type] = [cleaned_text]

        return {"contents": type_pages}

    def parse_pdf_with_pdfplumber(self, name, text_output_path, image_output_path, rotated_pages=None):
        with pdfplumber.open(self.file_path) as pdf:
            elements = {}
            for page_number, page in enumerate(pdf.pages, start=1):
                bbox = self.calculate_search_bbox(page)
                if rotated_pages and page_number in rotated_pages:
                    bbox = (bbox[1], bbox[0], bbox[3], bbox[2])
                elements[page_number] = self.extract_text_and_tables_within_bbox(page, bbox)

                output_image_path = f"{image_output_path}/{name}_{page_number}.png"
                self.draw_bbox_on_pdf(page, bbox, elements[page_number], output_image_path)

            type_data = {}
            for page_number, page_elements in elements.items():
                type_page_data = {"text": [], "table": []}

                for element in page_elements:
                    node_type = element["type"]
                    raw_text_content = str(element["content"])

                    if node_type == "text":
                        type_page_data["text"].append(raw_text_content)

                    # HTML
                    elif node_type == "table":
                        df = pd.DataFrame(element["content"][1:], columns=element["content"][0])
                        df = df.replace("\n", "", regex=True)
                        html_table = df.to_html(index=False, escape=False).replace("\n", "")
                        type_page_data["table"].append(html_table)

                    # # MARKDOWN
                    # elif node_type == 'table':
                    #     df = pd.DataFrame(element['content'][1:], columns=element['content'][0])
                    #     df = df.replace('\n', '', regex=True)
                    #     markdown_table = df.to_markdown(index=False)
                    #     type_page_data["table"].append(markdown_table)

                if type_page_data["text"] or type_page_data["table"]:
                    type_data[page_number] = type_page_data

        return {"contents": type_data}

    def calculate_search_bbox(self, page):
        # 페이지 크기 가져오기
        width, height = float(page.width), float(page.height)
        margin = 20  # 여백 설정

        # 페이지의 전체 텍스트 추출
        words = page.extract_words()
        if not words:
            return (0, 0, width, height)  # 내용이 없는 페이지는 전체 영역을 사용

        # 텍스트의 Bounding Box 계산
        min_x = max(min(word["x0"] for word in words) - margin, 0)
        min_y = max(min(word["top"] for word in words) - margin, 0)
        max_x = min(max(word["x1"] for word in words) + margin, width)
        max_y = min(max(word["bottom"] for word in words) + margin, height)

        # Bounding Box 좌표 출력 (디버깅 용도)
        # print(f"Page: {page.page_number}, BBox: ({min_x}, {min_y}, {max_x}, {max_y})")

        # 좌표 검증
        if min_x > max_x or min_y > max_y:
            return (0, 0, width, height)  # 비정상적인 좌표일 경우 전체 영역을 사용

        return (min_x, min_y, max_x, max_y)

    def extract_text_and_tables_within_bbox(self, page, bbox):
        text_and_tables = []

        tables = page.find_tables()
        table_bboxes = [table.bbox for table in tables if bbox[0] < table.bbox[0] < bbox[2] and bbox[1] < table.bbox[1] < bbox[3]]

        for table in tables:
            table_bbox = table.bbox
            if bbox[0] < table_bbox[0] < bbox[2] and bbox[1] < table_bbox[1] < bbox[3]:
                table_content = table.extract()
                text_and_tables.append({"type": "table", "content": table_content, "top": table_bbox[1], "bbox": table_bbox})

        words = page.extract_words()
        text_blocks = []
        current_block = []
        current_top = None

        for word in words:
            word_bbox = (word["x0"], word["top"], word["x1"], word["bottom"])
            if any(tb[0] <= word_bbox[0] <= tb[2] and tb[1] <= word_bbox[1] <= tb[3] for tb in table_bboxes):
                continue
            if not (bbox[0] < word_bbox[0] < bbox[2] and bbox[1] < word_bbox[1] < bbox[3]):
                continue
            if current_top is None or abs(word["top"] - current_top) > 10:
                if current_block:
                    text_blocks.append(
                        {
                            "type": "text",
                            "content": " ".join(w["text"] for w in current_block),
                            "top": current_top,
                            "bbox": (current_block[0]["x0"], current_block[0]["top"], current_block[-1]["x1"], current_block[0]["bottom"]),
                        }
                    )
                    current_block = []
                current_top = word["top"]
            current_block.append(word)

        if current_block:
            text_blocks.append(
                {
                    "type": "text",
                    "content": " ".join(w["text"] for w in current_block),
                    "top": current_top,
                    "bbox": (current_block[0]["x0"], current_block[0]["top"], current_block[-1]["x1"], current_block[0]["bottom"]),
                }
            )

        text_and_tables.extend(text_blocks)

        return text_and_tables

    # 241115 주석처리(이미지 저장 중단)
    def draw_bbox_on_pdf(self, page, bbox, elements, output_image_path):
        # img = page.to_image(resolution=150)
        # img.draw_rect(bbox, stroke="red", stroke_width=2, fill=None)

        # for element in elements:
        #     element_bbox = element['bbox']
        #     if element_bbox[0] < element_bbox[2] and element_bbox[1] < element_bbox[3]:
        #         if element['type'] == 'table':
        #             img.draw_rect(element_bbox, stroke="blue", stroke_width=2, fill=None)
        #         elif element['type'] == 'text':
        #             img.draw_rect(element_bbox, stroke="green", stroke_width=2, fill=None)

        # img.save(output_image_path)
        pass


class CustomIngestionPipeline(processing.IngestionPipeline):
    """
    커스텀 인게스쳔 파이프라인
    """

    def __init__(self):
        self.transformations = [
            NewRemoveTextInsideTables(),
            processing.RemoveRepeatedElements(),  # 241114) 추가
            processing.CombineBullets(),
            processing.CombineNodesSpatially(x_error_margin=0, y_error_margin=5, criteria="both_small"),
            processing.RemoveMetadataElements(min_y0_pct=0.1, max_y0_pct=0.95),
            processing.CombineHeadingsWithClosestText(),
        ]


class NewRemoveTextInsideTables(processing.ProcessingStep):
    """
    테이블 내부 텍스트를 제거하는 커스텀 처리 단계
    """

    def process(self, nodes: list[Node]) -> list[Node]:
        tables_by_page = defaultdict(list)
        for node in nodes:
            if node.variant == {"table"}:
                for table_element in node.elements:
                    tables_by_page[table_element.page].append(table_element.bbox)

        updated_nodes = []
        for node in nodes:
            if node.variant == {"table"}:
                updated_nodes.append(node)
                continue

            new_elements = []
            for element in node.elements:
                if isinstance(element, TextElement):
                    if not self.intersects_any_table(element.bbox, tables_by_page[element.page]):
                        new_elements.append(element)
                else:
                    new_elements.append(element)

            if new_elements and len(new_elements) != len(node.elements):
                updated_nodes.append(Node(elements=tuple(new_elements)))
            elif len(new_elements) == len(node.elements):
                updated_nodes.append(node)

        return updated_nodes

    def intersects_any_table(self, text_bbox: Bbox, table_bboxes: list[Bbox]) -> bool:
        for table_bbox in table_bboxes:
            if self.intersects(text_bbox, table_bbox):
                return True
        return False

    @staticmethod
    def intersects(text_bbox: Bbox, table_bbox: Bbox) -> bool:
        return (
            text_bbox.x0 >= table_bbox.x0
            and text_bbox.x1 <= table_bbox.x1
            and text_bbox.y0 >= table_bbox.y0
            and text_bbox.y1 <= table_bbox.y1
        )


def custom_extract_chars(text_line):
    """
    텍스트 라인에서 문자 요소 추출
    """

    class CharElement:
        def __init__(self, text, fontname, size):
            self.text = text
            self.fontname = fontname
            self.size = size

        @property
        def is_bold(self):
            return "Bold" in self.fontname or "bold" in self.fontname

        @property
        def is_italic(self):
            return "Italic" in self.fontname or "italic" in self.fontname

    def decode_fontname(fontname):
        try:
            return fontname.decode("utf-8")
        except (AttributeError, UnicodeDecodeError):
            try:
                return fontname.decode("latin1")
            except (AttributeError, UnicodeDecodeError):
                return fontname

    chars = []
    last_fontname = next((char.fontname for char in text_line if isinstance(char, LTChar)), "")
    last_size = next((char.size for char in text_line if isinstance(char, LTChar)), 0.0)

    for char in text_line:
        if not isinstance(char, LTChar) and not isinstance(char, LTAnno):
            continue
        if isinstance(char, LTChar):
            last_fontname = decode_fontname(char.fontname)
            last_size = char.size
        chars.append(CharElement(text=char.get_text(), fontname=last_fontname, size=last_size))

    return chars


openparse.text.pdfminer.core._extract_chars = custom_extract_chars


# multi-column 판별 로직 추가
class ColumnDetector:
    """
    PDF 문서의 텍스트 블록을 분석하여 single-column인지 multi-column인지 판별합니다.
    """

    def __init__(self, column_threshold: float = 0.2):
        self.column_threshold = column_threshold  # 열 간 x축 간격 기준

    def is_multi_column(self, nodes: list[Node], page_width: float) -> bool:
        """
        각 페이지에서 x축 정보와 너비를 분석하여 multi-column인지 판단하고 중간 결과 출력.
        """
        column_positions = []
        widths = []

        # 각 노드의 x축 정보를 수집하고, 각 노드의 너비를 계산
        for node in nodes:
            for element in node.elements:
                column_positions.append((element.bbox.x0, element.bbox.x1))
                widths.append(element.bbox.x1 - element.bbox.x0)

        # 각 노드의 중앙 너비를 계산
        median_width = np.median(widths)

        # 1차로 x축 간격 기준으로 multi-column 판별
        x_gap_check = self._analyze_columns(column_positions, page_width)

        # 2차로 텍스트 블록 중앙 너비가 페이지 너비의 절반보다 작으면 multi-column으로 판단
        width_check = median_width < (page_width / 2)

        # 최종 판단
        if x_gap_check and width_check:
            return True  # multi-column으로 판별
        else:
            return False  # single-column으로 판별

    def _analyze_columns(self, x_positions: list[tuple], page_width: float) -> bool:
        """
        x축 정보를 기반으로 텍스트 블록들이 다른 열에 속하는지 확인하고 결과를 출력.
        """
        x_positions.sort()
        first_x0, first_x1 = x_positions[0]
        current_column = [(first_x0, first_x1)]

        for x0, x1 in x_positions[1:]:
            # 절대값으로 gap ratio를 계산하여 열 간격을 정확히 측정
            gap_ratio = abs(x0 - current_column[-1][1]) / page_width

            # 절대값 Gap ratio가 threshold를 넘는 경우에만 multi-column으로 판별
            if gap_ratio > self.column_threshold:
                return True  # 다단으로 판단

            current_column.append((x0, x1))

        return False


def reorder_nodes_for_multi_column(nodes: list[Node], page_width: float) -> list[Node]:
    """
    Multi-column 문서에서 노드들을 x축 기준으로 분류한 후 y축 기준으로 재정렬 (페이지 단위).
    """
    columns = defaultdict(list)

    # 노드를 x축 기준으로 분류 (왼쪽 열과 오른쪽 열로 나눔)
    for node in nodes:
        first_element = node.elements[0]
        x_center = (first_element.bbox.x0 + first_element.bbox.x1) / 2
        column_key = determine_column(x_center, page_width)  # 좌우 열 구분
        columns[column_key].append(node)

    # 각 열에서 y축 기준으로 정렬 (y값이 큰 것부터 작은 것 순으로)
    for column_key in columns:
        columns[column_key].sort(key=lambda node: node.elements[0].bbox.y0, reverse=True)

    # 좌에서 우로 열 순서대로 노드를 다시 배열
    reordered_nodes = []
    for column_key in sorted(columns.keys()):
        reordered_nodes.extend(columns[column_key])

    return reordered_nodes


def determine_column(x_center: float, page_width: float) -> int:
    """
    x축의 중간값을 기준으로 열 번호를 결정 (0부터 시작)
    """
    column_width = page_width / 2  # 기본적으로 두 열로 나눔
    return int(x_center // column_width)


def process_pdf_nodes_by_page(parsed_doc):
    """
    PDF의 노드를 페이지 단위로 처리 (각 페이지별로 single-column 또는 multi-column 방식을 적용).
    """
    nodes_by_page = defaultdict(list)
    detector = ColumnDetector()

    # 전체 페이지의 노드 리스트를 저장할 변수
    all_nodes = []

    # 각 노드를 페이지별로 분류
    for node in parsed_doc.nodes:
        if node.elements:
            page = node.elements[0].bbox.page  # 노드가 속한 페이지 번호
            nodes_by_page[page].append(node)

    # 각 페이지별로 노드 처리
    # for page, nodes in nodes_by_page.items():
    for _, nodes in nodes_by_page.items():
        page_width = nodes[0].elements[0].bbox.page_width

        # 각 페이지가 single-column인지 multi-column인지 판별
        is_multi_column = detector.is_multi_column(nodes, page_width)

        # 각 페이지별로 노드 정렬
        if not is_multi_column:
            # Single-column 문서라면 기존 방식으로 y축 기준 순서대로 처리
            nodes.sort(key=lambda node: node.elements[0].bbox.y0, reverse=True)
        else:
            # Multi-column 문서라면 노드들의 읽기 순서를 재조정
            nodes = reorder_nodes_for_multi_column(nodes, page_width)

        # 정렬된 노드를 전체 노드 리스트에 추가
        all_nodes.extend(nodes)

    # 전체 페이지의 노드 정보를 parsed_pymupdf_table_doc과 동일한 형식으로 반환
    parsed_doc.nodes = all_nodes
    return parsed_doc


########################## 241205 확장자 제한으로 사용하지 않는 코드 주석 처리

# def convert_hwp_to_html(hwp_path, html_path):
#     """
#     HWP 파일을 HTML로 변환
#     """
#     try:
#         os.makedirs(html_path, exist_ok=True)
#         print(f"Successfully make_path: {html_path}")
#         subprocess.run(['hwp5html', hwp_path, '--output', html_path], check=True)
#         print(f"Successfully converted {hwp_path} to HTML in {html_path}")
#         # Remove WMF files in bindata directory
#         bindata_path = os.path.join(html_path, 'bindata')
#         remove_wmf_files(bindata_path)
#     except subprocess.CalledProcessError as e:
#         print(f"Error converting {hwp_path} to HTML: {e}")

# def remove_wmf_files(bindata_path):
#     """
#     bindata 디렉토리 내의 WMF 파일을 삭제
#     """
#     try:
#         for root, dirs, files in os.walk(bindata_path):
#             for file in files:
#                 if file.lower().endswith('.wmf'):
#                     os.remove(os.path.join(root, file))
#                     print(f"Removed WMF file: {file}")
#     except Exception as e:
#         print(f"Error removing WMF files: {e}")

# def remove_wmf_references(html_file):
#     """
#     HTML 파일에서 WMF 이미지 참조를 제거
#     """
#     try:
#         with open(html_file, 'r', encoding='utf-8') as file:
#             soup = BeautifulSoup(file, 'html.parser')

#         # WMF 이미지 참조 제거
#         for img_tag in soup.find_all('img'):
#             src = img_tag['src']
#             if src.lower().endswith('.wmf'):
#                 img_tag.decompose()  # 이미지 태그를 제거

#         with open(html_file, 'w', encoding='utf-8') as file:
#             file.write(str(soup))

#         print(f"Successfully removed WMF references in {html_file}")
#     except Exception as e:
#         print(f"Error removing WMF references in {html_file}: {e}")

# def convert_html_to_pdf(html_dir, pdf_path):
#     """
#     HTML 디렉토리를 PDF로 변환
#     """
#     try:
#         index_file = os.path.join(html_dir, 'index.xhtml')
#         remove_wmf_references(index_file)  # WMF 참조 제거
#         default_css = """
#         @page {
#             size: A4;
#             margin-top: 1cm;
#             margin-right: 0.2cm;
#             margin-bottom: 1cm;
#             margin-left: 0.2cm;
#         }
#         body {
#             margin: 0;
#             padding: 0;
#             font-family: "NanumGothic", serif;
#             font-size: 8pt;  # 여기서 기본 글자 크기를 조정합니다
#         }
#         h1, h2, h3, h4, h5, h6, p {
#             margin: 0;
#             padding: 0;
#         }
#         table {
#             width: 100%;
#             border-collapse: collapse;
#         }
#         td, th {
#             padding: 0.5cm;
#             border: 1px solid #000;
#         }
#         """
#         HTML(index_file).write_pdf(pdf_path, stylesheets=[CSS(string=default_css)])
#         print(f"Successfully converted {index_file} to {pdf_path}")
#     except Exception as e:
#         print(f"Error converting {index_file} to PDF: {e}")

# def convert_docx_to_pdf(docx_path, output_dir):
#     """
#     DOCX파일을 PDF로 변환하는 함수
#     """
#     try:
#         subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', docx_path, '--outdir', output_dir], check=True)
#         pdf_file = os.path.join(output_dir, os.path.basename(docx_path).replace('.docx', '.pdf'))
#         print(f"Successfully converted {docx_path} to {pdf_file}")
#     except subprocess.CalledProcessError as e:
#         print(f"Error converting {docx_path} to PDF: {e}")

# def unzip_hwpx(file_path, extract_to='./convert_file/hwpx_contents'):
#     """
#     HWPX 파일을 압축 해제
#     """
#     with zipfile.ZipFile(file_path, 'r') as zip_ref:
#         zip_ref.extractall(extract_to)

# def get_namespaces(xml_file):
#     """
#     XML 파일에서 네임스페이스 추출
#     """
#     tree = etree.parse(xml_file)
#     root = tree.getroot()
#     return root.nsmap

# def extract_all_text(xml_file, ns):
#     """
#     XML 파일에서 모든 텍스트 추출
#     """
#     tree = etree.parse(xml_file)
#     root = tree.getroot()

#     text = []
#     for t in root.xpath('.//hp:t', namespaces=ns):
#         if t.text:
#             text.append(t.text)
#     return ' '.join(text)

# def extract_table_text(xml_file, ns):
#     """
#     XML 파일에서 표 내 텍스트 추출
#     """
#     tree = etree.parse(xml_file)
#     root = tree.getroot()

#     table_text = []
#     for table in root.xpath('.//hp:tbl', namespaces=ns):
#         for t in table.xpath('.//hp:t', namespaces=ns):
#             if t.text:
#                 table_text.append(t.text)
#     return ' '.join(table_text)

# def extract_tables_from_section(xml_file, ns):
#     """
#     XML 파일에서 표를 HTML 형식으로 추출
#     """
#     tree = etree.parse(xml_file)
#     root = tree.getroot()

#     tables = []
#     for table in root.xpath('.//hp:tbl', namespaces=ns):
#         html_table = '<table>'
#         for row in table.xpath('.//hp:tr', namespaces=ns):
#             html_table += '<tr>'
#             for cell in row.xpath('.//hp:tc', namespaces=ns):
#                 html_table += '<td>'
#                 for para in cell.xpath('.//hp:p', namespaces=ns):
#                     for run in para.xpath('.//hp:run', namespaces=ns):
#                         for t in run.xpath('.//hp:t', namespaces=ns):
#                             if t.text:
#                                 html_table += t.text
#                 html_table += '</td>'
#             html_table += '</tr>'
#         html_table += '</table>'
#         tables.append(html_table)
#     return tables

# def detect_left_bounding_line(page, min_height_ratio=0.8):
#     """
#     페이지 이미지에서 외곽선을 감지하고, 감지된 외곽선의 x 좌표를 반환합니다.
#     외곽선의 길이가 페이지 높이의 min_height_ratio 이상인 경우만 유효한 외곽선으로 간주합니다.
#     """
#     # 페이지 이미지를 가져오기
#     img = page.to_image(resolution=150).original

#     # 이미지를 그레이스케일로 변환
#     gray = cv2.cvtColor(np.array(img), cv2.COLOR_BGR2GRAY)

#     # 엣지 감지
#     edges = cv2.Canny(gray, 50, 150)

#     # 윤곽선 찾기
#     contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

#     # 가장 왼쪽에 있는 윤곽선을 찾기
#     min_x = float('inf')
#     page_height = img.height

#     for contour in contours:
#         x, y, w, h = cv2.boundingRect(contour)
#         # 윤곽선의 높이가 페이지 높이의 min_height_ratio 이상인 경우만 유효한 외곽선으로 간주
#         if h >= page_height * min_height_ratio and x < min_x:
#             min_x = x

#     return min_x if min_x != float('inf') else None

# def get_text_length(img):
#     text = pytesseract.image_to_string(img, lang='kor')
#     return len(text.strip()), text

# def crop_center(image, crop_width, crop_height):
#     img_width, img_height = image.size
#     crop_left = (img_width - crop_width) // 2
#     crop_top = (img_height - crop_height) // 2
#     crop_right = crop_left + crop_width
#     crop_bottom = crop_top + crop_height
#     return image.crop((crop_left, crop_top, crop_right, crop_bottom))

# def detect_and_rotate_pdf_pages(pdf_path, output_path):
#     """
#     각 페이지별 회전이 필요한지 탐색
#     """
#     pdf_document = fitz.open(pdf_path)

#     rotated_pages = []

#     for page_number in range(len(pdf_document)):
#         page = pdf_document.load_page(page_number)

#         # 페이지를 이미지로 변환
#         pix = page.get_pixmap(dpi=300)
#         img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

#         # 중앙 부분을 자르기
#         crop_width, crop_height = pix.width // 2, pix.height // 2
#         cropped_img = crop_center(img, crop_width, crop_height)

#         # 핵심 텍스트 추출
#         text_length, text = get_text_length(cropped_img)

#         if text_length < 50:
#             continue

#         osd = pytesseract.image_to_osd(cropped_img, config='--psm 0')
#         rotation_angle = int(re.search(r'(?<=Rotate: )\d+', osd).group(0))

#         if rotation_angle != 0:
#             rotated_pages.append(page_number + 1)  # 페이지 번호는 1부터 시작
#             print(f"rotation_angle_detecting : {rotation_angle} degrees")
#             page.set_rotation(360)
#             print(f"Page {page_number + 1} rotated by 360 degrees.")

#     if rotated_pages:
#         if os.path.exists(output_path):
#             os.remove(output_path)
#         pdf_document.save(output_path)
#         pdf_document.close()
#     else:
#         output_path = pdf_path

#     return output_path, rotated_pages
