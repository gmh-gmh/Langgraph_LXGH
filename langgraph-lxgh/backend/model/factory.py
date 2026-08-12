from dotenv import load_dotenv
import os
import requests
from abc import ABC, abstractmethod
from typing import Optional
from langchain_core.embeddings import Embeddings
from langchain_community.chat_models.tongyi import BaseChatModel
from langchain.chat_models import init_chat_model

load_dotenv(override=True)

# 统一从环境变量读取，支持 MaaS / 公共 DashScope 两种端点
_api_key = os.getenv("DASHSCOPE_API_KEY")
_base_url = os.getenv("DASHSCOPE_BASE_URL", "https://llm-tchp236805grfatc.cn-beijing.maas.aliyuncs.com/compatible-mode/v1")


multimodal_model = init_chat_model(
    model_provider="openai",
    model="qwen3.5-omni-flash",#qwen3.5-omni-flash
    base_url=_base_url,
    api_key=_api_key,
)

class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass


class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return init_chat_model(
            model_provider="openai",
            model="qwen3.7-max",
            base_url=_base_url,
            api_key=_api_key,
        )


class MaaSEmbeddings(Embeddings):
    """自定义 Embeddings 类，兼容 MaaS 端点格式"""

    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """嵌入文档列表"""
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        """嵌入单个查询"""
        return self._embed([text])[0]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """调用 MaaS embedding API"""
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": texts,  # 纯字符串列表
        }

        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()

        result = response.json()
        # 按 index 排序（API 可能乱序返回）
        embeddings = sorted(result["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in embeddings]


class EmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return MaaSEmbeddings(
            model="text-embedding-v3",
            api_key=_api_key,
            base_url=_base_url,
        )

class VisualFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return multimodal_model


class RerankFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        # MaaS 端点不支持 DashScope 原生 SDK 的 rerank 接口，
        # 返回 None 让调用方降级处理（跳过重排序，直接用初检结果）
        return None




chat_model = ChatModelFactory().generator()
embed_model = EmbeddingsFactory().generator()
visual_model = VisualFactory().generator()
rerank_model = RerankFactory().generator()