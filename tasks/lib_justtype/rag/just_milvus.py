import logging
import time
import uuid
from datetime import datetime

import pandas as pd
from openai import OpenAI
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, utility

from app.schemas.langgraph_data import LangGraphState
from app.schemas.session import ChunkInfo
from app.tasks.lib_justtype.common.just_env import JustEnv
from app.tasks.lib_justtype.vector.milvus import MilvusHandler

logger = logging.getLogger(__name__)


class JustMilvus:
    def __init__(self, stat: LangGraphState):
        just_env = JustEnv(stat)
        self.config = just_env.get_config("milvus")
        if self.config is None:
            logger.error('config["milvus"] is not exist')
            raise Exception('config["milvus"] is not exist')
            # self.vector_dimension = config["vector_dimension"] if config["vector_dimension"] else 1536

        self.handler = MilvusHandler(host=self.config["milvus_url"], port=self.config["milvus_port"])
        self.collection = None
        self.fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.config["dense_vector_dim"]),  # 임베딩 차원
            FieldSchema(name="chunk_category1", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="chunk_category2", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="chunk_category3", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="chunk_content", dtype=DataType.VARCHAR, max_length=65000),
            FieldSchema(name="chunk_page_num", dtype=DataType.INT32),
            FieldSchema(name="chunk_link", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="doc_type", dtype=DataType.INT8, description="0:결재문서, 1:지식문서, 2:게시판문서"),
            FieldSchema(name="doc_owners_dept", dtype=DataType.ARRAY, element_type=DataType.VARCHAR, max_length=256, max_capacity=64),
            FieldSchema(name="doc_owners_indi", dtype=DataType.ARRAY, element_type=DataType.VARCHAR, max_length=256, max_capacity=64),
            FieldSchema(name="doc_created_at", dtype=DataType.INT64, description="해당 문서 생성 메타정보 (Unix timestamp)"),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="doc_name", dtype=DataType.VARCHAR, max_length=1024),
        ]

        self.collection_name = self.config["dense_collection_name"]
        self.schema = CollectionSchema(
            fields=self.fields, description=f"dense collection({self.collection_name})의 table", enable_dynamic_field=False
        )
        self.index_params = self.config["dense_index_params"]  # {"index_type": "IVF_FLAT", "metric_type": "L2", "params": {"nlist": 1024}}
        self.search_params = self.config["dense_search_params"]  # {"metric_type": "L2", "params": {"nprobe": 1024}}

        self.question = ""  # 검색에 사용된 질문
        self.chunks = []  # 검색된 chunk들

    def drop_collection(self, collection_name: str = None):
        if collection_name:
            self.handler.drop_collection(collection_name)
        else:
            self.handler.drop_collection(self.collection_name)
        self.collection = None
        return True

    def create_collection(self, collection_name: str = None):
        collection_name = collection_name if collection_name else self.collection_name
        has = utility.has_collection(collection_name)
        if not has:
            self.drop_collection(collection_name)
        self.collection = self.handler.create_collection(self.collection_name, self.fields, 8)  # 중규모 샤드=8. 16,32가능

        return True

    def create_index(self):
        if self.collection is None:
            self.create_collection()
        # collection = self.handler.get_collection(self.collection_name)
        logger.info(self.index_params)

        self.handler.create_index(self.collection, "embedding", self.index_params)

        return True

    def load(self, partition_names: list[str] = None):
        # load할때, partition_names를 사용하는 코딩은 아직 없음.
        if self.collection is None:
            self.create_collection()
        self.collection.load()

        return True

    def encode(self, queries: []):
        # None, NaN, 비문자열 제거
        cleaned_queries = [str(q) for q in queries if isinstance(q, str) and q.strip() != "" and q.lower() != "nan"]
        if not cleaned_queries:
            raise ValueError("No valid string queries to embed!")

        open_api_params = {}
        embedding_base_url = self.config.get("embedding_base_url")
        if embedding_base_url and len(embedding_base_url) > 0:
            open_api_params["base_url"] = embedding_base_url

        embedding_api_key = self.config.get("embedding_api_key")
        if embedding_api_key and len(embedding_api_key) > 0:
            open_api_params["api_key"] = embedding_api_key

        embedding_client = OpenAI(**open_api_params)
        result = embedding_client.embeddings.create(
            input=cleaned_queries, model=self.config["embedding_model"]  # chatGPT일때는 이 값을 사용 "text-embedding-ada-002"
        )
        embeddings = [x.embedding for x in result.data]
        return embeddings

    def _uuid(self):
        return "VD" + datetime.today().strftime("%m%d%S") + str(uuid.uuid4())[:8]

    # def insert_data(self, df, retriever: JustRetriever):
    def insert_data(self, df):

        # 컬렉션 존재 여부 확인 후 가져오기 또는 생성
        if not utility.has_collection(self.collection_name):
            collection = self.create_collection(self.collection_name)
        else:
            collection = self.handler.get_collection(self.collection_name)

        # 현재 시간 (Unix timestamp)
        current_time = int(time.time())

        # CSV의 "sub_chunk" 컬럼을 기반으로 배치 임베딩 수행 (chunk_content)
        chunk_contents = df["sub_chunk"].fillna("_").tolist()
        embedded_data = self.encode(chunk_contents)

        # Milvus insert를 위한 데이터 구조 준비 (각 필드는 리스트 형태로 저장)
        insert_data = []

        # DataFrame의 각 행에 대해 나머지 필드 값 채우기
        for i, row in df.iterrows():
            section = str(row.get("section", "")) if not pd.isna(row.get("section", "")) else ""
            sub_chunk = str(row.get("sub_chunk", "")) if not pd.isna(row.get("sub_chunk", "")) else ""
            try:
                page_number = int(row.get("page_number", 0))
            except Exception:
                page_number = 0
            sub_chunk_link = str(row.get("sub_chunk_link", "")) if not pd.isna(row.get("sub_chunk_link", "")) else ""
            document_name = str(row.get("document_name", "")) if not pd.isna(row.get("document_name", "")) else ""
            logger.info(f"index={i}")
            if len(sub_chunk) == 0:
                continue
            logger.info(f"insert index={i}")
            insert_data.append(
                {
                    "id": str(self._uuid()),
                    # "embedding": embedded_data[i].tolist(),
                    "embedding": embedded_data[i],
                    "chunk_category1": section,
                    "chunk_category2": "",
                    "chunk_category3": "",
                    "chunk_content": sub_chunk,
                    "chunk_page_num": page_number,
                    "chunk_link": sub_chunk_link,
                    "doc_type": 0,
                    "doc_owners_dept": ["연구소", "연구소/IT기획팀"],
                    "doc_owners_indi": ["홍길동"],
                    "doc_created_at": current_time,
                    "doc_id": document_name,
                    "doc_name": document_name,
                }
            )

        logger.info("insert_data ready!!")

        # Milvus에 데이터 삽입 후 flush
        for data in insert_data:
            self.handler.insert_data(collection, data)
        self.handler.collection_flush(collection)
        return True

    def search_chunks(self, question, user_depts, user_individuals, doc_types, top_k=10):

        encode_result = self.encode([question])
        question_embedding = encode_result[0]

        collection = Collection(self.collection_name)
        collection.load()  # 검색할 때, 메모리로 로드하여 검색 속도를 높일 수 있다.

        # 권한 필터 조건 구성
        dept_condition = f"array_contains_any(doc_owners_dept, {user_depts})" if user_depts else ""
        individual_condition = f"array_contains_any(doc_owners_indi, {user_individuals})" if user_individuals else ""
        type_condition = f"doc_type in {doc_types}" if doc_types else ""

        filter_conditions = []
        if dept_condition or individual_condition:
            permission_filter = " or ".join([c for c in [dept_condition, individual_condition] if c])
            filter_conditions.append(f"({permission_filter})")
        if type_condition:
            filter_conditions.append(type_condition)

        final_filter = " and ".join(filter_conditions) if filter_conditions else ""

        results = collection.search(
            data=[question_embedding],
            anns_field="embedding",
            param=self.search_params,
            limit=top_k,
            expr=final_filter,
            output_fields=[
                "chunk_category1",
                "chunk_category2",
                "chunk_category3",
                "chunk_content",
                "chunk_page_num",
                "chunk_link",
                "doc_name",
            ],
        )

        # 검색 결과를 ChunkInfo 객체들로 변환하여 self.chunk_info에 저장
        self.chunks = []  # 초기화
        for hit in results[0]:
            page_number = hit.entity.get("chunk_page_num")
            try:
                page_num = int(page_number)
            except (ValueError, TypeError):
                page_num = None

            chunk_info = ChunkInfo(
                document_name=hit.entity.get("doc_name"),
                question=question,
                category_1=hit.entity.get("chunk_category1"),
                category_2=hit.entity.get("chunk_category2"),
                category_3=hit.entity.get("chunk_category3"),
                chunk=hit.entity.get("chunk_content"),
                page_number=page_num,
                main_chunk_link=hit.entity.get("chunk_link"),
                search_key="",
                simularity=max(0, 1 - hit.distance / 2),
            )
            self.chunks.append(chunk_info)

        return self.chunks
