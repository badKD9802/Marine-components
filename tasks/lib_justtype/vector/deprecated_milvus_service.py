import json
import logging
import os
import platform
import random
import time
import uuid
from collections import defaultdict
from datetime import datetime

import pandas as pd
from pymilvus import utility
from pymilvus.client.types import LoadState
from tqdm import tqdm

from app.core import util as chatsam_util
from app.core.config import settings
from app.db.transaction import transactional
from app.orm import admin_orm
from main_init import app_path

from .milvus import MilvusHandler
from .milvus_class import MilvusConstant, MilvusDataset

# 현재 플랫폼이 Windows인 경우에만 eunjeon 사용
if os.getenv("ENV_TYPE") == "local" and platform.system() == "Windows":
    from eunjeon import Mecab
else:
    from konlpy.tag import Mecab

logger = logging.getLogger(__name__)
logger_org = logging.getLogger(__name__)


def remove_duplicates_by_key(dict_list, key):
    seen = set()
    return [d for d in dict_list if d[key] not in seen and not seen.add(d[key])]


def list_document(handler, collection_list):
    collection = handler.get_collection(MilvusConstant.COLLECTION_CHATSAM)
    # collection_name =
    res = handler.query(collection, f"collection_name in {collection_list}", ["id", "partition_name"])
    temp = []
    for hits in res:
        row = {"document_name": hits.get("partition_name")}
        temp.append(row)

    sorted_data = None
    if len(temp) > 0:
        sorted_data = sorted(temp, key=lambda x: x["document_name"])
    if sorted_data:
        return remove_duplicates_by_key(sorted_data, "document_name")
    else:
        return None


def delete_collection_chatsam(handler, collection_name):
    has = utility.has_collection(MilvusConstant.COLLECTION_CHATSAM)
    if has:
        collection = handler.get_collection(MilvusConstant.COLLECTION_CHATSAM)
        res = handler.delete_data(collection, f"collection_name == '{collection_name}'")
        handler.collection_flush(collection)
        return res
    return has


def insert_collection_chatsam(handler, data):
    has = utility.has_collection(MilvusConstant.COLLECTION_CHATSAM)
    if not has:
        collection = handler.create_collection(MilvusConstant.COLLECTION_CHATSAM, MilvusConstant.chatsam_fields, 8)
        index_params = MilvusConstant.INDEX_PARAMS
        handler.create_index(collection, "embeddings", index_params)
        handler.collection_load(collection)
    else:
        collection = handler.get_collection(MilvusConstant.COLLECTION_CHATSAM)
    # print(f"data : {data}")
    handler.insert_data(collection, data)
    handler.collection_flush(collection)
    return True


def get_collection_count(handler, collection_name):
    collection = handler.get_collection(collection_name)
    return handler.get_collection_count(collection)


def get_partition_id_by_name(handler, collection_name, partition_names):
    collection = handler.get_collection(MilvusConstant.COLLECTION_CHATSAM)
    if isinstance(partition_names, str):
        doc_list = [partition_names]
    else:
        doc_list = partition_names

    doc_name = [get_document_name(doc) for doc in doc_list]

    expr = f"collection_name == '{collection_name}' and partition_name in {doc_name}"
    res = handler.query(collection, expr, ["id"])
    # print(f"collection chatsam {expr}: {res}")
    partition_id = []
    for hits in res:
        partition_id.append(hits.get("id"))

    if len(partition_id) > 0:
        return partition_id
    return None


# ├── SearchResult
# │   └── Hits
# │       ├── ids
# │       ├── distances
# │       └── Hit
# │           ├── id
# │           ├── distance
# │           ├── score
# │           ├── vector
# │           └── get()
def dataframe_collection_by_search(
    handler,
    model,
    query,
    collection_name,
    top_k,
    output_fields=MilvusConstant.HEADER_COLUMNS,
    search_params=None,
):
    res = list_collection_by_search(handler, model, query, collection_name, top_k, output_fields, search_params)
    if len(res) > 0:
        return pd.DataFrame(res, columns=MilvusConstant.HEADER_COLUMNS_INCLUDE_ID)

    return res


def list_collection_by_search(
    handler,
    embedded_ask,
    collection_name,
    top_k=10,
    output_fields=MilvusConstant.HEADER_COLUMNS,
    search_params=None,
):
    start_time = time.time()
    collection = handler.get_collection(collection_name)
    if search_params is None:
        search_params = MilvusConstant.SEARCH_PARAMS

    # if isinstance(query, str):
    #     query_embedding = [model.encode(query, convert_to_tensor=False)]
    # else:
    #     query_embedding = [query]

    res = handler.search(
        collection,
        [embedded_ask],
        MilvusConstant.EMBEDDING_FILED_NAME,
        search_params,
        output_fields,
        limit=top_k,
    )

    temp = []
    for hits in res:
        for hit in hits:
            result = {}
            result["id"] = hit.id
            result["distance"] = hit.distance
            for col in output_fields:
                result[col] = hit.get(col)
            # logger.debug(f"search result : {result}")
            temp.append(result)
    return temp


# def dataframe_partition_by_search(handler,
#                                   model,
#                                   query,
#                                   collection_name,
#                                   doc_names,
#                                   top_k=10,
#                                   output_fields=MilvusConstant.HEADER_COLUMNS,
#                                   search_params=None):
#     res = list_partition_by_search(handler, model, query, collection_name, doc_names,
#                                    top_k, output_fields, search_params)
#     if len(res) > 0:
#         return pd.DataFrame(res, columns=MilvusConstant.HEADER_COLUMNS_INCLUDE_ID)
#
#     return res


def list_partition_by_search(
    handler,
    embedded_ask,
    collection_name,
    doc_names,
    top_k=10,
    output_fields=MilvusConstant.HEADER_COLUMNS,
    search_params=None,
):
    start_time = time.time()
    collection = handler.get_collection(collection_name)

    if len(doc_names) == 0:
        partition_names = None
    else:
        partition_names = doc_names

    partition_ids = None
    if partition_names:
        partition_ids = get_partition_id_by_name(handler, collection_name, partition_names)

    if search_params is None:
        search_params = MilvusConstant.SEARCH_PARAMS

    # logger.debug(f"partition query : {query_embedding}")
    temp = []
    # if partition_names is None or partition_ids:      # 무조건 True가 되는 조건이므로 삭제
    res = handler.search(
        collection,
        [embedded_ask],
        MilvusConstant.EMBEDDING_FILED_NAME,
        search_params,
        output_fields,
        partition_ids,
        limit=top_k,
    )

    for hits in res:
        for hit in hits:
            result = {}
            result["id"] = hit.id
            result["distance"] = hit.distance
            for col in output_fields:
                result[col] = hit.get(col)
            # logger.debug(f"search result : {result}")
            temp.append(result)

    return temp


def list_milvus_by_query(
    handler,
    collection_name,
    expr,
    doc_names=None,
    output_fields=MilvusConstant.HEADER_COLUMNS,
):
    collection = handler.get_collection(collection_name)

    if doc_names is None or len(doc_names) == 0:
        partition_names = None
    else:
        partition_names = doc_names

    partition_ids = None
    if partition_names:
        partition_ids = get_partition_id_by_name(handler, collection_name, partition_names)

    sorted_data = []
    if partition_names is None or partition_ids:
        all_rows = []
        batch_size = 10000
        total_rows = handler.get_collection_count(collection)

        for offset in range(0, total_rows, batch_size):
            res = handler.query(collection, expr, output_fields, partition_ids, offset, batch_size)
            all_rows.extend(res)

        if len(all_rows) > 0:
            sorted_data = sorted(all_rows, key=lambda x: x["id"])

    return sorted_data


def dataframe_milvus_by_query(
    handler,
    collection_name,
    expr,
    doc_names=None,
    output_fields=MilvusConstant.HEADER_COLUMNS,
):
    if len(doc_names) == 0:
        partition_names = None
    else:
        partition_names = doc_names
    all_rows = list_milvus_by_query(handler, collection_name, expr, partition_names, output_fields)
    if len(all_rows) > 0:
        return pd.DataFrame(all_rows, columns=MilvusConstant.HEADER_COLUMNS_INCLUDE_ID)

    return all_rows


def generate_uuid(gbn):
    return gbn + datetime.today().strftime("%m%d%S") + str(uuid.uuid4())[:8]


def excel_to_vector(xls_file, path, site):
    xls_file_path = f"{path[:-3]}excel{os.sep}{site}{os.sep}{xls_file}"
    # logger.debug(f"default path : {xls_file_path}")
    if not os.path.exists(xls_file_path):
        xls_file_path = os.path.join(app_path, "data", xls_file)
    try:
        logger.debug(f"excel path : {xls_file_path}")
        df = pd.read_excel(xls_file_path, engine="openpyxl")
        if "search_key" not in df.columns:
            df["search_key"] = None
        df_fill = df.fillna(MilvusConstant.FILL_VALUES)
        df_fill["sub_chunk_seq"] = df_fill["sub_chunk_seq"].astype(int)
        return df_fill.sort_values(by="document_name")
    except Exception as e:
        raise Exception(f"Excel file({xls_file_path}) is not exists.") from e


def get_document_name(doc_name):
    _split = doc_name.split("/")
    if len(_split) == 0:
        d_name = doc_name
    elif len(_split) == 1:
        d_name = _split[0]
    else:
        d_name = _split[1]
    # if d_name.rfind('.') >= 0:    # SAM: 확장자가 없는 경우, 엉뚱한 "."에서 자른다.
    #     return d_name[:d_name.rfind('.')]
    # else:
    #     return d_name
    return d_name


def dataset_to_vector_old(milvus_handler, collection, collection_name, dataset, search_type, q_column):
    compare_doc_name = ""
    document_id = ""
    delete_collection_chatsam(milvus_handler, collection_name)
    logger.info(f"delete_collection_chatsam   : {collection_name}")
    if search_type == "bert_bm25":
        mecab = Mecab()
    out_index = 1
    for data in tqdm(iter(dataset), total=len(dataset)):
        if data["document_name"] == "":
            continue
        doc_name = get_document_name(data["document_name"])
        if doc_name != compare_doc_name:
            compare_doc_name = doc_name
            document_id = generate_uuid("VT")
            milvus_handler.create_partition(collection, document_id, description=compare_doc_name)
            chatsam_data = {
                "id": document_id,
                "collection_name": collection_name,
                "partition_name": compare_doc_name,
                "embeddings": [random.random() for _ in range(8)],
            }
            insert_collection_chatsam(milvus_handler, chatsam_data)
            milvus_handler.collection_flush(collection)  # SAM: doc 바뀔때마다 한 번씩 메모리를 DiSK로 옮기자.
        data["document_id"] = document_id
        tokenized_corpus = []
        # SAM: corpus를 더이상 vectordb에 넣을 필요없다. 이제부터 메모리에 올려놓고 쓴다.
        # if search_type == "bert_bm25":
        #     doc = data[q_column]
        #     tokenized_corpus = mecab.morphs(doc)
        data["mecab_data"] = tokenized_corpus
        logger.debug(f"insert data {out_index}: {doc_name}")
        milvus_handler.insert_data(collection, data, partition_name=document_id)
        out_index = out_index + 1
    milvus_handler.collection_flush(collection)
    logger.debug(f"insert data count : {collection.num_entities}")
    return collection.num_entities


def dataset_to_vector(milvus_handler, collection, collection_name, dataset: MilvusDataset):
    delete_collection_chatsam(milvus_handler, collection_name)
    logger.info(f"delete_collection_chatsam   : {collection_name}")
    has = utility.has_collection(MilvusConstant.COLLECTION_CHATSAM)
    if not has:
        collection_chatsam = milvus_handler.create_collection(MilvusConstant.COLLECTION_CHATSAM, MilvusConstant.chatsam_fields, 8)
        milvus_handler.create_index(collection_chatsam, "embeddings", MilvusConstant.INDEX_PARAMS)
        milvus_handler.collection_load(collection_chatsam)
    else:
        collection_chatsam = milvus_handler.get_collection(MilvusConstant.COLLECTION_CHATSAM)

    # collection_chatsam = milvus_handler.get_collection(MilvusConstant.COLLECTION_CHATSAM)
    # print(f"data : {data}")

    out_index = 1
    partition_index = 1
    doc_partition_map = defaultdict(str)

    # 파티션 생성을 위한 준비 작업
    for data in dataset:
        if data["document_name"] == "":
            continue
        doc_name = get_document_name(data["document_name"])
        if doc_partition_map[doc_name] == "":
            doc_partition_map[doc_name] = generate_uuid("VT")

    # 파티션 생성
    for doc_name, document_id in doc_partition_map.items():
        milvus_handler.create_partition(collection, document_id, description=doc_name)
        chatsam_data = {
            "id": document_id,
            "collection_name": collection_name,
            "partition_name": doc_name,
            "embeddings": [random.random() for _ in range(8)],
        }
        # insert_collection_chatsam(milvus_handler, chatsam_data)
        milvus_handler.insert_data(collection_chatsam, chatsam_data)
        logger.debug(f"insert partition {partition_index}: {doc_name}")
        partition_index += 1

    milvus_handler.collection_flush(collection)
    milvus_handler.collection_flush(collection_chatsam)

    # 데이터 삽입
    for data in dataset:
        if data["document_name"] == "":
            continue
        doc_name = get_document_name(data["document_name"])
        document_id = doc_partition_map[doc_name]
        data["document_id"] = document_id

        tokenized_corpus = []
        data["mecab_data"] = tokenized_corpus
        logger.debug(f"insert data {out_index}: {doc_name}")
        milvus_handler.insert_data(collection, data, partition_name=document_id)
        out_index += 1
        # if out_index % 1000 == 0:
        #     milvus_handler.collection_flush(collection)

    milvus_handler.collection_flush(collection)  # HHHHHHHHHHHHHH 일부씩 flush해야 한다.
    logger.debug(f"insert data count : {collection.num_entities}")
    return collection.num_entities


def dataset_to_vector_no_partition(milvus_handler, collection, dataset):
    # if search_type == "bert_bm25":
    #     mecab = Mecab()
    out_index = 1
    for data in tqdm(iter(dataset), total=len(dataset)):
        logger.debug(f"insert data {out_index}: {data['question']}")
        milvus_handler.insert_data(collection, data)
        out_index = out_index + 1
    milvus_handler.collection_flush(collection)
    logger.debug(f"insert vector data count : {len(dataset)}")
    return collection.num_entities


def delete_vector(milvus_handler, collection, dataset):
    out_index = 1
    tmp = []
    if isinstance(dataset, list):
        tmp = dataset
    else:
        for data in tqdm(iter(dataset), total=len(dataset)):
            out_index = out_index + 1
            tmp.append(data["search_key"])
    expr = f"search_key in {tmp}"
    logger.info(f"delete expr : {expr}")
    milvus_handler.delete_data(collection, expr)
    milvus_handler.collection_flush(collection)
    logger.debug(f"delete vector data count : {len(dataset)}")
    return collection.num_entities


def action_model(name, action_str="get", device_opt=None):
    return chatsam_util.action_model(name, action_str, device_opt)


def deprecated_action_tokenizer(name, action_str="get"):
    return chatsam_util.deprecated_action_tokenizer(name, action_str)


@transactional
async def make_qna_logs(session, log_info):
    try:
        if isinstance(log_info, dict):
            info = chatsam_util.DotDict(log_info)
        else:
            info = log_info
        milvus_handler = MilvusHandler(host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)

        apply_all = True
        is_create = False
        collection_name = f"{info.service_path}_log_qna"
        if info.data and len(info.data) > 0:
            apply_all = False
            data = info.data
        else:
            data = info.service_path

        has = utility.has_collection(collection_name)
        logger.info(f"Does collection {collection_name} exist in Milvus: {has}")
        if info.job in ["delete", "revoke"]:
            collection = milvus_handler.get_collection(collection_name)
            if milvus_handler.load_state(collection_name) != LoadState.Loaded:
                milvus_handler.collection_load(collection)
            delete_vector(milvus_handler, collection, info.data)
            if info.job == "delete":
                await admin_orm.delete_log_qna(session, info.data)
            else:
                await admin_orm.update_log_qna_revoke(session, info.data)
            return True

        svc_list = await admin_orm.select_service_use_qna_log(session, info.service_path)
        if len(svc_list) > 0:
            svc = svc_list[0]
            if has and apply_all:
                logger.info(f"Delete existing data.[{collection_name}]")
                milvus_handler.drop_collection(collection_name)
                has = False

            if not has:
                logger.info("collection create.")
                collection = milvus_handler.create_collection(
                    collection_name,
                    MilvusConstant.log_qna_fields,
                    MilvusConstant.VECTOR_DIMENSION,
                )

                if svc["index_params"] and svc["index_params"] != "None":
                    index_params = json.loads(svc["index_params"])
                    index_params["metric_type"] = "COSINE"  # metric_type은 COSINE으로 해야 함
                else:
                    index_params = MilvusConstant.INDEX_PARAMS

                logger.info(f"create index : {index_params}")

                index_params = MilvusConstant.INDEX_PARAMS
                milvus_handler.create_index(collection, MilvusConstant.EMBEDDING_FILED_NAME, index_params)

                milvus_handler.create_index(collection, "search_key")
                is_create = True
            else:
                collection = milvus_handler.get_collection(collection_name)

            logger.info("collection load")
            if milvus_handler.load_state(collection_name) != LoadState.Loaded:
                milvus_handler.collection_load(collection)

            embedder = chatsam_util.action_model(svc["model_name"])
            field2column = {v: k for k, v in MilvusConstant.log_qna_column_2field.items()}

            source_data = await admin_orm.select_log_qna_use_vector(session, data)
            df = pd.DataFrame(source_data, columns=MilvusConstant.HEADER_COLUMNS)

            q_column_list = df["question"].tolist()

            logger.info("embeddings operations can take a long time to start.")
            embeddings = embedder.encode(q_column_list, convert_to_tensor=False)  # 다음 line에서 BM25 mecab.morphs(doc)를 하면 좋다.
            # 정확히는 db에 넣을 필요가 없다. (조건을 검색을 못 하고, 매번 full select이다)
            logger.info("embeddings operations end.")
            # 새로운 차원의 벡터 확인

            dataset = MilvusDataset(df, embeddings, field2column, MilvusConstant.EMBEDDING_FILED_NAME)

            if not is_create:
                # 먼저 삭제를 한다..
                delete_vector(milvus_handler, collection, dataset)

            ins_count = dataset_to_vector_no_partition(milvus_handler, collection, dataset)
            logger.debug(f"insert {collection_name} : {ins_count}")
            # apply_all이 아니면 apply update
            if not apply_all:
                logger.debug("********* update apply ")
                await admin_orm.update_log_qna_apply(session, data)
        return True
    except Exception as e:
        raise Exception(f"make_qna_logs Exception: {e}") from e
