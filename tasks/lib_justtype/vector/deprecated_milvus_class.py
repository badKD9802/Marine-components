import logging
import os
import platform

from pymilvus import DataType, FieldSchema

# 현재 플랫폼이 Windows인 경우에만 eunjeon 사용
if os.getenv("ENV_TYPE") == "local" and platform.system() == "Windows":
    pass
else:
    pass

logger = logging.getLogger(__name__)


# dataframe을 vector collection의 스키마 정보를 참조해서 dict로 return
# insert 용 데이타 생성
class MilvusDataset:
    def __init__(self, df, embeddings, field2column, embedding_field):
        self.df = df
        self.embeddings = embeddings
        self.field2column = field2column
        self.embedding_field = embedding_field

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        items = {}
        for field, column in self.field2column.items():
            value = self.df.iloc[idx][column]
            if column == "page_number" and isinstance(value, str):
                value = -1
            elif self.df.iloc[idx][column] is None:
                value = ""
            if column not in ["page_number", "sub_chunk_seq"] and not isinstance(value, str):
                items[field] = str(value)
            else:
                items[field] = value
        items[self.embedding_field] = self.embeddings[idx].tolist()

        return items


# index_type
# FLAT: FLAT는 소규모의 백만 규모 데이터 세트에서 완벽하게 정확하고 정확한 검색 결과를 찾는 시나리오에 가장 적합합니다.
# IVF_FLAT : IVF_FLAT는 양자화 기반 인덱스이며 정확도와 쿼리 속도 간의 이상적인 균형을 추구하는 시나리오에 가장 적합합니다.
# IVF_PQ : IVF_PQ는 양자화 기반 인덱스이며 정확성을 희생하더라도 높은 쿼리 속도를 추구하는 시나리오에 가장 적합합니다.
# HNSW : HNSW는 그래프 기반 인덱스이며 검색 효율성에 대한 요구가 높은 시나리오에 가장 적합합니다.
# ANNOY : ANNOY는 트리 기반 인덱스이며 높은 재현율을 추구하는 시나리오에 가장 적합합니다.
#
# metric_type / 부동 소수점 임베딩
# 유클리드 거리(L2) : 이 메트릭은 일반적으로 컴퓨터 비전(CV) 분야에서 사용됩니다.
# 내적(IP) : 이 메트릭은 일반적으로 자연어 처리(NLP) 분야에서 사용됩니다.

# metric_type / 바이너리 임베딩
# 해밍 : 이 메트릭은 일반적으로 자연어 처리(NLP) 분야에서 사용됩니다.
# Jaccard : 이 메트릭은 일반적으로 분자 유사성 검색 분야에서 사용됩니다.
# Tanimoto : 이 메트릭은 일반적으로 분자 유사성 검색 분야에서 사용됩니다.
# 상부 구조 : 이 메트릭은 일반적으로 분자의 유사한 상부 구조를 검색하는 데 사용됩니다.
# 하위 구조 : 이 메트릭은 일반적으로 분자의 유사한 하위 구조를 검색하는 데 사용됩니다.
# 빠른 검색을 용이하게 하기 위해 IVF(Inverted File Index) 또는 HNSW(Hierarchical Navigable Small World)


class MilvusConstant:
    COLLECTION_CHATSAM = "chatsam"
    EMBEDDING_FILED_NAME = "embeddings"

    HEADER_COLUMNS = [
        "document_name",
        "category_1",
        "category_2",
        "category_3",
        "main_chunk",
        "sub_chunk",
        "sub_chunk_seq",
        "question",
        "answer",
        "page_number",
        "main_chunk_link",
        "search_key",
    ]

    HEADER_COLUMNS_INCLUDE_ID = [
        "id",
        "document_name",
        "category_1",
        "category_2",
        "category_3",
        "main_chunk",
        "sub_chunk",
        "sub_chunk_seq",
        "question",
        "answer",
        "page_number",
        "main_chunk_link",
        "search_key",
    ]

    FILL_VALUES = {
        "document_name": "",
        "category_1": "",
        "category_2": "",
        "category_3": "",
        "main_chunk": "",
        "sub_chunk": "",
        "sub_chunk_seq": -1,
        "question": "",
        "answer": "",
        "page_number": -1,
        "main_chunk_link": "",
        "search_key": "",
        "mecab_data": [],
    }

    VECTOR_DIMENSION = 1024
    chatsam_fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=30, is_primary=True),
        FieldSchema(name="collection_name", dtype=DataType.VARCHAR, max_length=200),
        FieldSchema(name="partition_name", dtype=DataType.VARCHAR, max_length=300),
        FieldSchema(name="embeddings", dtype=DataType.FLOAT_VECTOR, dim=8),
    ]

    service_fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=50),
        FieldSchema(name="document_name", dtype=DataType.VARCHAR, max_length=500),
        FieldSchema(name="category_1", dtype=DataType.VARCHAR, max_length=500),
        FieldSchema(name="category_2", dtype=DataType.VARCHAR, max_length=500),
        FieldSchema(name="category_3", dtype=DataType.VARCHAR, max_length=500),
        FieldSchema(name="main_chunk", dtype=DataType.VARCHAR, max_length=65000),
        FieldSchema(name="sub_chunk", dtype=DataType.VARCHAR, max_length=50000),
        FieldSchema(name="sub_chunk_seq", dtype=DataType.INT32, max_length=10),
        FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=20000),
        FieldSchema(name="answer", dtype=DataType.VARCHAR, max_length=65000),
        FieldSchema(name="page_number", dtype=DataType.INT32, max_length=10),
        FieldSchema(name="main_chunk_link", dtype=DataType.VARCHAR, max_length=500),
        FieldSchema(name="search_key", dtype=DataType.VARCHAR, max_length=50),
        FieldSchema(name=EMBEDDING_FILED_NAME, dtype=DataType.FLOAT_VECTOR, dim=VECTOR_DIMENSION),
        FieldSchema(
            name="mecab_data",
            dtype=DataType.ARRAY,
            element_type=DataType.VARCHAR,
            max_capacity=2048,
            max_length=500,
        ),
    ]

    log_qna_fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=20000),
        FieldSchema(name="answer", dtype=DataType.VARCHAR, max_length=65000),
        FieldSchema(name="search_key", dtype=DataType.VARCHAR, max_length=50),
        FieldSchema(name=EMBEDDING_FILED_NAME, dtype=DataType.FLOAT_VECTOR, dim=VECTOR_DIMENSION),
    ]

    service_column_2field = {
        "document_name": "document_name",
        "category_1": "category_1",
        "category_2": "category_2",
        "category_3": "category_3",
        "main_chunk": "main_chunk",
        "sub_chunk": "sub_chunk",
        "sub_chunk_seq": "sub_chunk_seq",
        "question": "question",
        "answer": "answer",
        "page_number": "page_number",
        "main_chunk_link": "main_chunk_link",
        "search_key": "search_key",
    }
    log_qna_column_2field = {
        "question": "question",
        "answer": "answer",
        "search_key": "search_key",
    }
    INDEX_PARAMS = {
        "metric_type": "COSINE",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 1024},
    }
    # nprobe 작은값은 빠른검색 , 클수록 메모리 사용 많음 4-16
    #        큰값은 메모리 절약, 검색속도 느림 32,64,128
    SEARCH_PARAMS = {"metric_type": "COSINE", "params": {"nprobe": 64}}
