import logging

from openai import OpenAI, AsyncOpenAI

# 전역적으로 사용할 클라이언트 인스턴스를 저장할 변수
_openai_client = None
_async_openai_client = None
_milvus_clients: dict = {}  # key: "host:port" → (AsyncMilvusClient, MilvusClient)
_kiwi_instance = None
_kiwi_stopwords = None
_reranker_client = None
logger = logging.getLogger(__name__)

def get_openai_client(embedding_config: dict):
    """
    OpenAI 동기 클라이언트를 위한 싱글턴 인스턴스를 반환합니다.
    """
    global _openai_client
    if _openai_client is None:
        # logger.info("Initializing a new GLOBAL OpenAI client instance.")
        try:
            # [FIX] api_key가 유효한 값일 때만 파라미터에 추가하도록 수정
            params = {
                "base_url": embedding_config.get("embedding_base_url"),
            }
            api_key = embedding_config.get("embedding_api_key")
            
            if not api_key or api_key.strip().upper() in ["EMPTY", "NONE", "NULL"]:
                params["api_key"] = "NA"
            else:
                params["api_key"] = api_key
            
            # base_url이 없는 경우 params에서 제거하여 라이브러리 기본값 사용 방지
            if not params.get("base_url"):
                del params["base_url"]
                logger.warning("embedding_base_url is not configured. OpenAI client might default to public API.")

            _openai_client = OpenAI(**params)

        except Exception as e:
            logger.error(f"Failed to initialize GLOBAL OpenAI client: {e}", exc_info=True)
            return None
    return _openai_client

def get_async_openai_client(embedding_config: dict):
    """
    OpenAI 비동기 클라이언트를 위한 싱글턴 인스턴스를 반환합니다.
    """
    global _async_openai_client
    if _async_openai_client is None:
        # logger.info("Initializing a new GLOBAL AsyncOpenAI client instance.")
        try:
            params = {
                "base_url": embedding_config.get("embedding_base_url"),
            }
            api_key = embedding_config.get("embedding_api_key")
            
            if not api_key or api_key.strip().upper() in ["EMPTY", "NONE", "NULL"]:
                params["api_key"] = "NA"
            else:
                params["api_key"] = api_key

            if not params.get("base_url"):
                del params["base_url"]
                logger.warning("embedding_base_url is not configured. AsyncOpenAI client might default to public API.")

            _async_openai_client = AsyncOpenAI(**params)

        except Exception as e:
            logger.error(f"Failed to initialize GLOBAL AsyncOpenAI client: {e}", exc_info=True)
            return None
    return _async_openai_client


def get_milvus_clients(milvus_config: dict) -> tuple:
    """
    Milvus 클라이언트 싱글턴 (host:port 기준).
    Returns (AsyncMilvusClient, MilvusClient) tuple.
    """
    global _milvus_clients
    url = milvus_config.get("milvus_url", "localhost")
    port = milvus_config.get("milvus_port", "19530")
    key = f"{url}:{port}"

    if key not in _milvus_clients:
        try:
            from pymilvus import AsyncMilvusClient, MilvusClient
            uri = f"{url}:{port}"
            async_client = AsyncMilvusClient(uri=uri)
            sync_client = MilvusClient(uri=uri)
            _milvus_clients[key] = (async_client, sync_client)
            logger.info(f"Milvus clients initialized for {key}")
        except Exception as e:
            logger.error(f"Failed to initialize Milvus clients for {key}: {e}", exc_info=True)
            return None, None

    return _milvus_clients[key]


def get_kiwi():
    """
    Kiwi 토크나이저 싱글턴 (model_type='sbg').
    Returns (kiwi, stopwords) tuple.
    """
    global _kiwi_instance, _kiwi_stopwords
    if _kiwi_instance is None:
        from kiwipiepy import Kiwi
        from kiwipiepy.utils import Stopwords
        _kiwi_instance = Kiwi(model_type="sbg")
        _kiwi_stopwords = Stopwords()
        logger.info("Kiwi tokenizer initialized (singleton)")
    return _kiwi_instance, _kiwi_stopwords


def get_reranker_client():
    """
    httpx 리랭커 클라이언트 싱글턴.
    """
    global _reranker_client
    if _reranker_client is None or _reranker_client.is_closed:
        import httpx
        _reranker_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10
            )
        )
        logger.info("Reranker HTTP client initialized (singleton)")
    return _reranker_client
