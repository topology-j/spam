"""
RAG 엔진 - Qwen(Ollama) + GPT(OpenAI) 스팸 판단 + 지속 학습
"""
import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import os
import pickle
import faiss
import numpy as np
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

VS_DIR = os.path.join(os.path.dirname(__file__), "vectorstore")
os.makedirs(VS_DIR, exist_ok=True)

_index = None
_metadata = None  # {"texts": [...], "labels": [...]}
_finetune_model = None  # 파인튜닝 완료 후 apply 시 설정됨

EMBED_DIM = 1536  # text-embedding-3-small 차원


def _load_vectorstore():
    global _index, _metadata
    index_path = os.path.join(VS_DIR, "spam.index")
    meta_path = os.path.join(VS_DIR, "metadata.pkl")
    print(f"[DEBUG] VS_DIR={VS_DIR}, index={os.path.getsize(index_path) if os.path.exists(index_path) else 'missing'} bytes")
    if os.path.exists(index_path) and os.path.exists(meta_path):
        # 한글 경로 대응: Python으로 bytes 읽어서 deserialize
        with open(index_path, "rb") as f:
            _index = faiss.deserialize_index(np.frombuffer(f.read(), dtype=np.uint8))
        with open(meta_path, "rb") as f:
            _metadata = pickle.load(f)
        print(f"✅ FAISS 벡터스토어 로드 완료 ({_index.ntotal}개 벡터)")
    else:
        # 빈 인덱스 초기화
        _index = faiss.IndexFlatL2(EMBED_DIM)
        _metadata = {"texts": [], "labels": []}
        print("⚠️  벡터스토어 없음 → 빈 인덱스로 초기화 (build_vectorstore.py로 학습 데이터 추가 권장)")


def _save_vectorstore():
    index_bytes = faiss.serialize_index(_index)
    with open(os.path.join(VS_DIR, "spam.index"), "wb") as f:
        f.write(index_bytes)
    with open(os.path.join(VS_DIR, "metadata.pkl"), "wb") as f:
        pickle.dump(_metadata, f)


def _embed_query(text: str) -> np.ndarray:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=[text]
    )
    return np.array([response.data[0].embedding], dtype="float32")


def _retrieve(text: str, k: int = 5) -> list[dict]:
    if _index is None or _index.ntotal == 0:
        return []
    actual_k = min(k, _index.ntotal)
    vec = _embed_query(text)
    distances, indices = _index.search(vec, actual_k)
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx >= 0:
            results.append({
                "text": _metadata["texts"][idx],
                "label": _metadata["labels"][idx],
                "distance": float(dist)
            })
    return results


def add_to_vectorstore(text: str, label: str) -> bool:
    """
    새 예시를 vectorstore에 추가하고 즉시 저장 (지속 학습).
    label: 'spam' 또는 'ham'
    """
    global _index, _metadata
    if _index is None:
        _load_vectorstore()
    try:
        vec = _embed_query(text)
        _index.add(vec)
        _metadata["texts"].append(text)
        _metadata["labels"].append(label)
        _save_vectorstore()
        return True
    except Exception as e:
        print(f"⚠️  vectorstore 추가 실패: {e}")
        return False


def _build_prompt(query: str, examples: list[dict]) -> str:
    if examples:
        examples_text = "\n".join([
            f"[{e['label'].upper()}] {e['text'][:120]}"
            for e in examples
        ])
        context = f"[유사 메시지 예시]\n{examples_text}\n\n"
    else:
        context = ""
    return f"""당신은 스팸 메시지 탐지 전문가입니다.
{context}[판단할 메시지]
{query}

다음 형식으로 답변하세요:
판정: 스팸 또는 정상
이유: (구체적인 이유 설명)
신뢰도: 높음 / 중간 / 낮음"""


def classify_with_gpt(text: str, examples: list[dict] = None, model: str = "gpt-4o-mini") -> dict:
    active_model = _finetune_model or model
    if examples is None:
        examples = _retrieve(text)
    prompt = _build_prompt(text, examples)
    response = client.chat.completions.create(
        model=active_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=200,
    )
    answer = response.choices[0].message.content.strip()
    model_label = f"GPT ({active_model})" if _finetune_model else "GPT"
    return _parse_result(answer, model_label, examples)


def classify_with_qwen(text: str, examples: list[dict] = None) -> dict:
    if examples is None:
        examples = _retrieve(text)
    prompt = _build_prompt(text, examples)
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen2.5:1.5b",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 150}
            },
            timeout=60
        )
        response.raise_for_status()
        answer = response.json().get("response", "").strip()
        return _parse_result(answer, "Qwen2.5", examples)
    except Exception as e:
        return {"error": f"Qwen 오류: {str(e)}"}


def _parse_result(answer: str, model_name: str, examples: list[dict]) -> dict:
    first_line = answer.split("\n")[0] if answer else ""
    is_spam = "스팸" in first_line and "정상" not in first_line
    return {
        "model": model_name,
        "is_spam": is_spam,
        "raw_answer": answer,
        "retrieved_count": len(examples),
        "retrieved_examples": [
            {"text": e["text"][:100], "label": e["label"]}
            for e in examples
        ]
    }


def _has_spam_signals(text: str) -> bool:
    suspicious_terms = (
        "[url]",
        "계정",
        "결제",
        "링크",
        "제한",
        "즉시",
        "비정상",
        "접근",
    )
    text_lower = text.lower()
    return any(term in text_lower for term in suspicious_terms)


def fast_classify(text: str, k: int = 7) -> bool:
    """
    GPT 호출 없는 빠른 분류 (임베딩 유사도 다수결 투표).
    vectorstore가 비어있으면 None 반환.
    """
    examples = _retrieve(text, k=k)
    if not examples:
        return None
    first = examples[0]
    spam_votes = sum(1 for e in examples if e["label"] == "spam")
    strong_spam_match = (
        first["label"] == "spam"
        and first["distance"] <= 1.24
        and spam_votes >= 5
    )
    return strong_spam_match and _has_spam_signals(text)


_load_vectorstore()
