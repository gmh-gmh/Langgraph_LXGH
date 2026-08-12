"""
知识库数据导入脚本。

将 backend/rag/data/ 下的知识文档加载、切分、嵌入后存入 ChromaDB。

用法（在项目根目录下执行）：
    python -m backend.rag.ingest
"""

from backend.rag.loader import load_documents
from backend.rag.splitter import split_documents
from backend.rag.vectorstore import create_vectorstore, load_vectorstore


def ingest():
    print("=" * 50)
    print("开始导入知识库数据...")
    print("=" * 50)

    # 1. 加载源文档
    print("\n[1/4] 加载源文档...")
    docs = load_documents()
    if not docs:
        print("   [失败] 未找到任何文档！请检查 backend/rag/data/ 目录下是否有 .md / .txt / .json 文件。")
        return
    print(f"   [OK] 共加载 {len(docs)} 个原始文档")

    # 2. 文档切分
    print("\n[2/4] 切分文档...")
    split_docs = split_documents(docs)
    print(f"   [OK] 切分为 {len(split_docs)} 个文档块 (chunk_size=500, overlap=50)")

    # 3. 创建向量库
    print("\n[3/4] 创建向量库并嵌入文档...")
    print("   正在调用 DashScope 嵌入 API，需要几秒钟...")
    try:
        vectorstore = create_vectorstore(split_docs)
        print(f"   [OK] 向量库创建成功！")
        print(f"   存储位置: chroma_db/")
        print(f"   嵌入文档数: {len(split_docs)}")
    except Exception as e:
        print(f"   [失败] 创建向量库失败: {e}")
        print("   请检查 DASHSCOPE_API_KEY 是否正确配置。")
        return

    # 4. 验证
    print("\n[4/4] 验证导入结果...")
    try:
        vs = load_vectorstore()
        count = vs._collection.count()
        print(f"   [OK] ChromaDB 中共有 {count} 条嵌入记录")
    except Exception as e:
        print(f"   [警告] 验证时出错: {e}")

    print("\n" + "=" * 50)
    print("知识库导入完成！")
    print("=" * 50)


if __name__ == "__main__":
    ingest()
