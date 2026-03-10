import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI

# import tritonclient.http as httpclient
# from tritonclient.utils import triton_to_np_dtype
from transformers import AutoTokenizer

# from app.justtype.rag import util
from app.tasks.lib_justtype.common import util


def load_model(model_config):
    if "url" in model_config:
        model_config["base_url"] = model_config.pop("url")

    llm = ChatOpenAI(**model_config)

    return llm


class DataClient(Embeddings):
    def __init__(self, config):
        self.embed_model = util.embedding_model(model_name="dragonkue/BGE-m3-ko")
        # self.tokenizer = util.get_tokenizer("dragonkue/BGE-m3-ko")
        # self.embed_model = SentenceTransformer("dragonkue/BGE-m3-ko")
        self.tokenizer = AutoTokenizer.from_pretrained("dragonkue/BGE-m3-ko")
        self.batch_size = config["batch_size"]

    # np.array
    def get_embedding(self, text: str):
        return self.embed_model.encode(text)

    # list
    def embed_query(self, query: str) -> list[float]:
        return self.embed_model.encode(query).tolist()

    def _embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_model.encode(texts)

    # list
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]
            embeddings_batch = self._embed_documents(batch_texts)
            embeddings.append(embeddings_batch)
        embeddings = np.vstack(embeddings)
        return embeddings.tolist()

    def get_token_length(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False))


# class TritonClientURL:
#     """외부에서 실행되는 triton inference server의 호출을 위한 class

#     Args:
#         url (``str``): 호출할 triton inference server의 URL
#         model_name(``str``): 호출할 triton inference server 내 model의 이름
#         port (``Optional[int]``): triton inference server의 GRPC 통신 port 번호

#     Attributes:
#         inputs (``List[Dict[str, Any]]``): 지정된 model의 입력
#         outputs (``List[Dict[str, Any]]``): 지정된 model의 출력

#     Methods:
#         __call__:
#             Model 호출 수행

#             Args:
#                 *args (``NDArray[DTypeLike]``): Model 호출 시 사용될 입력 (``self.inputs``)

#             Returns:
#                 ``Dict[str, NDArray[DTypeLike]]``: 호출된 model의 결과
#     """

#     def __init__(self, url: str, model_name: str, port: Optional[int] = 8001) -> None:
#         self.server_url = f"{url}:{port}"
#         self.model_name = model_name
#         self.triton_client = httpclient.InferenceServerClient(
#             url=self.server_url, verbose=False
#         )
#         self.info = self.triton_client.get_model_config(model_name)
#         assert self.info["name"] == model_name
#         self.inputs = self.info["input"]
#         self.outputs = self.info["output"]

#     def __call__(self, *args: NDArray[DTypeLike]) -> Dict[str, NDArray[DTypeLike]]:
#         assert len(self.inputs) == len(args)
#         triton_inputs = []
#         for input_info, arg in zip(self.inputs, args):
#             triton_inputs.append(self._set_input(input_info, arg))
#         triton_outputs = []
#         for output in self.outputs:
#             triton_outputs.append(httpclient.InferRequestedOutput(output["name"]))
#         response = self.triton_client.infer(
#             model_name=self.model_name, inputs=triton_inputs, outputs=triton_outputs
#         )
#         response.get_response()
#         triton_results = {}
#         for output in self.outputs:
#             triton_results[output["name"]] = response.as_numpy(output["name"])
#         return triton_results

#     def _set_input(self, input_info: Dict[str, List[int]], value: NDArray[DTypeLike]):
#         triton_dtype = input_info["data_type"][5:]
#         if triton_dtype == "STRING":
#             triton_dtype = "BYTES"
#         value = value.astype(triton_to_np_dtype(triton_dtype))
#         return httpclient.InferInput(
#             input_info["name"],
#             value.shape,
#             triton_dtype,
#         ).set_data_from_numpy(value)


# class DataClient(Embeddings):
#     def __init__(self, config):
#         self.batch_size = config["batch_size"]
#         self.tokenizer = AutoTokenizer.from_pretrained(config["model_name"])
#         self.triton_client = TritonClientURL(
#             url=config["url"],
#             port=config["port"],
#             model_name=config["model_name"],
#         )
#         # # 연결 테스트
#         # self._test_connection()

#     def _test_connection(self):
#         try:
#             self.embed_query("안녕하세요")
#         except Exception as e:
#             raise f"Error during embedding model connection: {e}"

#     def _get_inputs(self, text):
#         if isinstance(text, str):
#             assert text != "", "text must not be empty"
#         elif isinstance(text, list):
#             assert len(text) > 0, "texts must not be empty"
#         else:
#             raise ValueError("text must be a string or a list of strings")

#         results = self.tokenizer(text, return_tensors="np", padding=True, truncation=True)
#         input_ids = results["input_ids"]
#         attention_mask = results["attention_mask"]
#         return input_ids, attention_mask

#     # np.array
#     def get_embedding(self, text: str):
#         input_ids, attention_mask = self._get_inputs(text)
#         output = self.triton_client(input_ids, attention_mask)
#         return output["sentence_embedding"][0]

#     # list
#     def embed_query(self, query: str) -> List[float]:
#         input_ids, attention_mask = self._get_inputs(query)
#         output = self.triton_client(input_ids, attention_mask)
#         output = output["sentence_embedding"][0]
#         return output.tolist()

#     def _embed_documents(self, texts: List[str]) -> List[List[float]]:
#         input_ids, attention_mask = self._get_inputs(texts)
#         output = self.triton_client(input_ids, attention_mask)
#         output = output["sentence_embedding"]
#         return output

#     # list
#     def embed_documents(self, texts: List[str]) -> List[List[float]]:
#         embeddings = []
#         for i in range(0, len(texts), self.batch_size):
#             batch_texts = texts[i:i + self.batch_size]
#             embeddings_batch = self._embed_documents(batch_texts)
#             embeddings.append(embeddings_batch)
#         embeddings = np.vstack(embeddings)
#         return embeddings.tolist()

#     def get_token_length(self, text: str) -> int:
#         return len(self.tokenizer.encode(text, add_special_tokens=False))

# def _process_texts(self, texts: Union[str, List[str]]) -> tuple[np.ndarray, bool]:
#     """텍스트를 처리하여 numpy array로 변환"""
#     is_single = isinstance(texts, str)
#     if is_single:
#         texts = [texts]
#     text_array = np.array([[t.encode('utf-8')] for t in texts], dtype=np.object_)
#     return text_array, is_single

# def get_embedding_and_length(self, texts: Union[str, List[str]]) -> tuple[np.ndarray, Union[int, List[int]]]:
#     """텍스트의 임베딩과 토큰 수를 함께 반환합니다.

#     Args:
#         texts: 단일 문자열 또는 문자열 리스트

#     Returns:
#         tuple:
#             - np.ndarray: 문장 임베딩 (단일: (1024,), 배치: (batch_size, 1024))
#             - Union[int, List[int]]: 토큰 수 (단일: 정수, 배치: 정수 리스트)
#     """
#     text_array, is_single = self._process_texts(texts)
#     result = self.triton_client(text_array)

#     embeddings = result['sentence_embedding']
#     token_lengths = result['token_length'].squeeze(-1)

#     if is_single:
#         embeddings = embeddings.squeeze(0)
#         token_lengths = token_lengths[0]
#     else:
#         token_lengths = token_lengths.tolist()

#     return embeddings, token_lengths

# def get_token_length(self, text: str) -> int:
#     _, token_length = self.get_embedding_and_length(text)
#     return int(token_length)

# # np.array
# def get_embedding(self, text: str):
#     embedding, _ = self.get_embedding_and_length(text)
#     return embedding

# # list
# def embed_query(self, query: str) -> List[float]:
#     embedding, _ = self.get_embedding_and_length(query)
#     return embedding.tolist()

# # np.array
# def _embed_documents(self, texts: List[str]):
#     embeddings, _ = self.get_embedding_and_length(texts)
#     return embeddings

# # list
# def embed_documents(self, texts: List[str]) -> List[List[float]]:
#     embeddings = []
#     for i in range(0, len(texts), self.batch_size):
#         batch_texts = texts[i:i + self.batch_size]
#         embeddings_batch = self._embed_documents(batch_texts)
#         embeddings.append(embeddings_batch)
#     embeddings = np.vstack(embeddings)
#     return embeddings.tolist()
