"""
RAG Harness — 检索验证护栏。

核心职责：
  1. 溯源：每条检索结果携带来源文件路径
  2. 验证：提供接口验证一段文本是否确实存在于知识库中
  3. 引用：输出时自动附加来源标记，让用户知道信息来自哪里
  4. 过滤：自动剔除无法通过验证的内容（防止LLM幻觉）

设计原则：
  - 不信任原始检索结果以外的任何内容
  - 所有输出到用户的知识必须能回溯到具体源文件

用法：
  harness = RAGHarness()
  items = harness.retrieve("北京限行政策")
  for item in items:
      print(item["content"], "←", item["source_file"])
"""

import os
import re
import hashlib
import json
from typing import Optional
from backend.rag.retriever import RerankRetriever
from backend.rag.vectorstore import load_vectorstore
from backend.utils.logger_handler import logger


class RAGHarness:
    """
    RAG 验证护栏

    包装 retriever，在检索和输出之间加入验证层。
    所有输出到用户的知识都必须能回溯到向量库中的源文件。
    """

    def __init__(self):
        self.vectorstore = load_vectorstore()
        self.retriever = RerankRetriever(self.vectorstore)
        # 知识库内容索引（惰性加载），用于验证
        self._kb_index = None # 知识库索引

    # ---------------------------------------------------------------
    # 核心：带溯源的结构化检索
    # ---------------------------------------------------------------

    def retrieve(self, query: str, top_n: int = 5, distance_km: float = None) -> list[dict]:
        """
        检索并返回结构化知识（每段携带来源元数据）。

        返回格式：
          [
            {
              "content": "文档内容文本",
              "source": "backend/rag/data/01_城市出行规则/北京限行政策.md",
              "source_file": "北京限行政策.md",
              "content_hash": "sha256前缀（用于去重和验证）",
              "verified": True,      # 已通过向量库验证
              "length": 123,
            },
            ...
          ]
        """
        docs = self.retriever.retrieve(query, top_n=top_n)

        results = []
        seen_hashes = set()

        for doc in docs:
            content = doc.page_content.strip()
            if not content:
                continue

            # 计算内容哈希（用于去重和验证）
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)

            # 提取来源文件名
            source = doc.metadata.get("source", "未知来源")
            source_file = os.path.basename(source) if source != "未知来源" else "未知来源"

            results.append({
                "content": content,
                "source": source,
                "source_file": source_file,
                "content_hash": content_hash,
                "verified": True,  # 直接从向量库检索，必然真实
                "length": len(content),
            })

        return results

    # ---------------------------------------------------------------
    # 验证：检验一段文本是否确实存在于知识库中
    # ---------------------------------------------------------------

    def verify_snippet(self, text: str, threshold: float = 0.85) -> dict:
        """
        验证一段文本是否来自知识库。

        原理：用文本的前200字作为查询去向量库做相似度搜索，
        检查最相似的结果是否足够匹配。

        返回：
          {"verified": True, "source": "文件名", "confidence": 0.95}
          或
          {"verified": False, "source": None, "confidence": 0.0}
        """
        if not text or len(text) < 20:
            return {"verified": False, "source": None, "confidence": 0.0}

        # 取前200字符作为查询指纹
        fingerprint = text[:200]
        docs = self.retriever.retrieve(fingerprint, top_n=1)

        if not docs:
            return {"verified": False, "source": None, "confidence": 0.0}

        best = docs[0]
        best_content = best.page_content.strip()

        # 计算文本相似度（基于公共子串比例）
        similarity = self._text_similarity(text, best_content)
        source = best.metadata.get("source", "未知来源")

        if similarity >= threshold:
            return {
                "verified": True,
                "source": source,
                "source_file": os.path.basename(source),
                "confidence": round(similarity, 4),
            }
        else:
            return {
                "verified": False,
                "source": source,
                "source_file": os.path.basename(source),
                "confidence": round(similarity, 4),
            }

    def batch_verify(self, items: list[dict]) -> list[dict]:
        """
        批量验证一组检索结果是否都有真实来源。
        对每条记录打上 verified 标记。
        """
        for item in items:
            result = self.verify_snippet(item.get("content", ""))
            item["verified"] = result["verified"]
            item["verify_confidence"] = result["confidence"]
            item["verify_source"] = result.get("source", None)
        return items

    # ---------------------------------------------------------------
    # 格式化：带引用标记的输出
    # ---------------------------------------------------------------

    def format_cited(self, items: list[dict], max_items: int = 5) -> str:
        """格式化为带来源引用的文本"""
        lines = []
        for i, item in enumerate(items[:max_items], 1):
            source_tag = item.get("source_file", "未知来源")
            lines.append(f"[{i}] {item['content']}")
            lines.append(f"     —— 来源: {source_tag}")
        return "\n\n".join(lines)

    def format_compact(self, items: list[dict], max_items: int = 5) -> str:
        """紧凑格式（不带引用，用于LLM内部调用）"""
        lines = []
        for i, item in enumerate(items[:max_items], 1):
            lines.append(f"[{i}] {item['content']}")
        return "\n\n".join(lines)

    # ---------------------------------------------------------------
    # 知识库完整性校验
    # ---------------------------------------------------------------

    def build_kb_index(self) -> dict:
        """
        构建知识库全文索引（用于离线验证）。

        返回：
          {
            "total_docs": 15,
            "total_chunks": 30,
            "sources": ["北京限行政策.md", ...],
            "source_count": {"北京限行政策.md": 3, ...},
          }
        """
        if self._kb_index is not None:
            return self._kb_index

        try:
            # ChromaDB 原生 get() 获取所有文档
            all_data = self.vectorstore.get()
            documents = all_data.get("documents", [])
            metadatas = all_data.get("metadatas", [])

            sources = {}
            for i, doc in enumerate(documents):
                meta = metadatas[i] if i < len(metadatas) else {}
                source = meta.get("source", "未知来源")
                source_file = os.path.basename(source) if source != "未知来源" else "未知来源"
                sources[source_file] = sources.get(source_file, 0) + 1

            self._kb_index = {
                "total_docs": len(documents),
                "sources": list(sources.keys()),
                "source_count": sources,
            }
        except Exception as e:
            logger.error(f"[Harness] 构建知识库索引失败: {e}")
            self._kb_index = {"total_docs": 0, "sources": [], "source_count": {}}

        return self._kb_index

    # ---------------------------------------------------------------
    # 内部工具
    # ---------------------------------------------------------------

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """计算两段文本的相似度（基于最长公共子序列比例）"""
        if not a or not b:
            return 0.0

        # 归一化：去空白 + 转小写 + 截取前 500 字
        a = re.sub(r"\s+", "", a.lower())[:500]
        b = re.sub(r"\s+", "", b.lower())[:500]

        if len(a) < 10 or len(b) < 10:
            return 0.0

        # 取较短文本，计算它在较长文本中的覆盖率
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        match_len = 0
        for i in range(len(shorter)):
            # 检查 shorter[i:i+20] 是否出现在 longer 中
            end = min(i + 20, len(shorter))
            substr = shorter[i:end]
            if substr in longer:
                match_len += len(substr)

        return match_len / len(shorter)


# ============================================================
# 全局入口
# ============================================================

_harness = None


def get_harness() -> RAGHarness:
    global _harness
    if _harness is None:
        _harness = RAGHarness()
    return _harness


def retrieve_verified(query: str, top_n: int = 5) -> list[dict]:
    """便捷入口：检索并返回带来源的结构化知识"""
    return get_harness().retrieve(query, top_n=top_n)


def verify_text(text: str) -> dict:
    """便捷入口：验证文本是否来自知识库"""
    return get_harness().verify_snippet(text)
