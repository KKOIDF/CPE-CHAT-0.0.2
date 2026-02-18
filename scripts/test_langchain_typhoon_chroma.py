import os
import tempfile
from typing import List

from langchain_openai import ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings


class SentenceTransformerEmbeddings(Embeddings):
    """Minimal LangChain Embeddings wrapper around sentence-transformers.

    This avoids needing extra integration packages (e.g., langchain-huggingface)
    and matches this repo's existing embedding stack.
    """

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self._model_name = model_name
        self._model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return vectors.tolist()

    def embed_query(self, text: str) -> List[float]:
        vector = self._model.encode([text], normalize_embeddings=True)[0]
        return vector.tolist()


def _test_typhoon_llm() -> None:
    api_key = os.getenv("TYPHOON_API_KEY", "").strip()
    base_url = os.getenv("TYPHOON_BASE_URL", "https://api.opentyphoon.ai/v1").strip()

    # Avoid guessing model names; require an explicit model.
    model = (
        os.getenv("TYPHOON_MODEL", "").strip()
        or os.getenv("LLM_MODEL", "").strip()
    )

    if not api_key:
        print("[SKIP] Typhoon LLM: set TYPHOON_API_KEY to run this test")
        return
    if not model:
        print("[SKIP] Typhoon LLM: set TYPHOON_MODEL (or LLM_MODEL) to run this test")
        return

    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout=float(os.getenv("TYPHOON_TIMEOUT_S", "60")),
    )

    resp = llm.invoke("ตอบภาษาไทยสั้นๆ: Typhoon ผ่าน LangChain ทำงานหรือยัง?")
    print("[OK] Typhoon LLM response:")
    print(resp.content)


def _test_chroma_vectorstore() -> None:
    embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3").strip() or "BAAI/bge-m3"
    embeddings = SentenceTransformerEmbeddings(embedding_model)

    # Use a temp dir to avoid writing into the repo by default.
    persist_dir = tempfile.mkdtemp(prefix="lc_chroma_demo_")

    docs = [
        Document(page_content="CPE คือการพัฒนาความรู้ต่อเนื่องของผู้ประกอบวิชาชีพ", metadata={"id": "cpe"}),
        Document(page_content="Cosmos DB เป็นฐานข้อมูล NoSQL แบบกระจายทั่วโลก", metadata={"id": "cosmos"}),
        Document(page_content="Typhoon เป็นผู้ให้บริการ LLM ที่รองรับ API สไตล์ OpenAI", metadata={"id": "typhoon"}),
    ]

    store = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=persist_dir,
        collection_name="demo",
    )

    query = "Typhoon เรียกผ่าน API แบบไหน"
    results = store.similarity_search(query, k=2)

    print("[OK] Chroma similarity_search results:")
    for i, doc in enumerate(results, 1):
        print(f"  {i}. {doc.metadata.get('id')}: {doc.page_content}")


def main() -> None:
    print("== LangChain + Typhoon + Chroma quick test ==")
    _test_typhoon_llm()
    _test_chroma_vectorstore()


if __name__ == "__main__":
    main()
