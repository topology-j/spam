"""
FAISS 벡터스토어 구축 스크립트
train.csv → OpenAI 임베딩 → FAISS 인덱스 저장

임베딩 캐시: embeddings_cache.npy / cache_texts.pkl
→ 이미 캐시가 있으면 API 호출 없이 재사용
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
# train_split.csv 없으면 train.csv 폴백
if not os.path.exists(TRAIN_CSV):
    TRAIN_CSV = os.path.join(BASE, "..", "train.csv")
VS_DIR = os.path.join(BASE, "vectorstore")
CACHE_EMB = os.path.join(VS_DIR, "embeddings_cache.npy")
CACHE_META = os.path.join(VS_DIR, "cache_meta.pkl")
os.makedirs(VS_DIR, exist_ok=True)


def get_embeddings(texts: list[str], batch_size=100) -> np.ndarray:
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=batch
        )
        all_embeddings.extend([e.embedding for e in response.data])
        print(f"  임베딩 진행: {min(i+batch_size, len(texts))}/{len(texts)}")
    return np.array(all_embeddings, dtype="float32")


def main():
    print("train.csv 로드 중...")
    df = pd.read_csv(TRAIN_CSV)
    df = df.dropna(subset=["text", "label"])
    texts = df["text"].tolist()
    labels = df["label"].tolist()
    print(f"총 {len(texts)}개 샘플 (spam: {labels.count('spam')}, ham: {labels.count('ham')})")

    # 캐시 확인
    if os.path.exists(CACHE_EMB) and os.path.exists(CACHE_META):
        with open(CACHE_META, "rb") as f:
            cached_meta = pickle.load(f)
        if cached_meta.get("texts") == texts:
            print("\n✅ 캐시된 임베딩 재사용 (API 호출 없음)")
            embeddings = np.load(CACHE_EMB)
        else:
            print("\n⚠️  데이터 변경 감지 → 임베딩 재생성")
            embeddings = _embed_and_cache(texts)
    else:
        print("\n임베딩 생성 중 (OpenAI text-embedding-3-small)...")
        embeddings = _embed_and_cache(texts)

    print("\nFAISS 인덱스 구축 중...")
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    # 한글 경로 대응: serialize_index → Python bytes write
    index_bytes = faiss.serialize_index(index)
    with open(os.path.join(VS_DIR, "spam.index"), "wb") as f:
        f.write(index_bytes)
    with open(os.path.join(VS_DIR, "metadata.pkl"), "wb") as f:
        pickle.dump({"texts": texts, "labels": labels}, f)

    print(f"\n완료! 벡터스토어 저장: {VS_DIR}")
    print(f"  - spam.index ({index.ntotal}개 벡터)")
    print(f"  - metadata.pkl")


def _embed_and_cache(texts):
    embeddings = get_embeddings(texts)
    np.save(CACHE_EMB, embeddings)
    with open(CACHE_META, "wb") as f:
        pickle.dump({"texts": texts}, f)
    print("  임베딩 캐시 저장 완료")
    return embeddings


if __name__ == "__main__":
    main()
