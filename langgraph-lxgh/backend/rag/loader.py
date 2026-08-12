from langchain_community.document_loaders import TextLoader,JSONLoader
from langchain_core.documents import Document

def load_documents(data_dir:str="backend/rag/data")->list[Document]:
    doc=[]
    import glob
    # 把MarkDown文件加载到doc文档里面（递归搜索子目录）
    for md_path in glob.glob(f"{data_dir}/**/*.md", recursive=True):
        loader = TextLoader(md_path, encoding="utf-8")
        doc.extend(loader.load())


    for json_path in glob.glob(f"{data_dir}/**/*.json", recursive=True):
        loader = JSONLoader(
            file_path=json_path,
            jq_schema=".[].description",
            text_content=False
        )
        doc.extend(loader.load())

    for tex_path in glob.glob(f"{data_dir}/**/*.txt", recursive=True):
        loader = TextLoader(tex_path,encoding="utf-8")
        doc.extend(loader.load())


    return doc
