import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
"""
FAISS vectorstore build script.
Uses train_split.csv only so validation/test data never leak into retrieval.
"""
import os
import pandas as pd
import pickle
import faiss
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

BASE = os.path.dirname(__file__)
TRAIN_CSV = os.path.join(BASE, "..", "train_split.csv")
VS_DIR = os.path.join(BASE, "vectorstore")
CACHE_EMB = os.path.join(VS_DIR, "embeddings_cache.npy")
CACHE_META = os.path.join(VS_DIR, "cache_meta.pkl")
os.makedirs(VS_DIR, exist_ok=True)


def get_embeddings(texts: list[str], batch_size: int = 100) -> np.ndarray:
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=batch,
        )
        all_embeddings.extend([e.embedding for e in response.data])
        print(f"  embeddings: {min(i + batch_size, len(texts))}/{len(texts)}")
    return np.array(all_embeddings, dtype="float32")


def _embed_and_cache(texts: list[str]) -> np.ndarray:
    embeddings = get_embeddings(texts)
    np.save(CACHE_EMB, embeddings)
    with open(CACHE_META, "wb") as f:
        pickle.dump({"texts": texts}, f)
    print("  saved embedding cache")
    return embeddings


def main():
    if not os.path.exists(TRAIN_CSV):
        raise FileNotFoundError("train_split.csv가 없습니다. split_data.py를 먼저 실행해주세요.")

    print("train_split.csv 로드 중..")
    df = pd.read_csv(TRAIN_CSV)
    df = df.dropna(subset=["text", "label"])
    texts = df["text"].tolist()
    labels = df["label"].tolist()
    print(f"samples: {len(texts)} (spam: {labels.count('spam')}, ham: {labels.count('ham')})")

    if os.path.exists(CACHE_EMB) and os.path.exists(CACHE_META):
        with open(CACHE_META, "rb") as f:
            cached_meta = pickle.load(f)
        if cached_meta.get("texts") == texts:
            print("\nusing cached embeddings")
            embeddings = np.load(CACHE_EMB)
        else:
            print("\ncache mismatch, rebuilding embeddings")
            embeddings = _embed_and_cache(texts)
    else:
        print("\ncreating embeddings (text-embedding-3-small)")
        embeddings = _embed_and_cache(texts)

    print("\nbuilding FAISS index..");
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    index_bytes = faiss.serialize_index(index)
    with open(os.path.join(VS_DIR, "spam.index"), "wb") as f:
        f.write(index_bytes)
    with open(os.path.join(VS_DIR, "metadata.pkl"), "wb") as f:
        pickle.dump({"texts": texts, "labels": labels}, f)

    print(f"\ndone: {VS_DIR}")
    print(f"  - spam.index ({index.ntotal} vectors)")
    print("  - metadata.pkl")


if __name__ == "__main__":
    main()
