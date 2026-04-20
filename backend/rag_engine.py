"""
RAG 엔진 - Qwen(Ollama) + GPT(OpenAI) 스팸 판단 + 지속 학습
"""
import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

# LangSmith SDK uses LANGSMITH_* env vars. Keep compatibility with older
# LANGCHAIN_* settings already present in this project.
if os.getenv("LANGCHAIN_TRACING_V2") and not os.getenv("LANGSMITH_TRACING"):
    os.environ["LANGSMITH_TRACING"] = os.getenv("LANGCHAIN_TRACING_V2", "")
if os.getenv("LANGCHAIN_API_KEY") and not os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "")
if os.getenv("LANGCHAIN_PROJECT") and not os.getenv("LANGSMITH_PROJECT"):
    os.environ["LANGSMITH_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "")
if os.getenv("LANGCHAIN_ENDPOINT") and not os.getenv("LANGSMITH_ENDPOINT"):
    os.environ["LANGSMITH_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT", "")
if not os.getenv("LANGSMITH_ENDPOINT"):
    os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"

import pickle
import faiss
import numpy as np
import requests
from openai import OpenAI
from langsmith import traceable
from langsmith.wrappers import wrap_openai

print(
    "[LangSmith] "
    f"TRACING={os.getenv('LANGSMITH_TRACING')} "
    f"PROJECT={os.getenv('LANGSMITH_PROJECT')} "
    f"ENDPOINT={os.getenv('LANGSMITH_ENDPOINT')} "
    f"KEY={os.getenv('LANGSMITH_API_KEY','')[:15]}..."
)

client = wrap_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

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
        with open(index_path, "rb") as f:
            _index = faiss.deserialize_index(np.frombuffer(f.read(), dtype=np.uint8))
        with open(meta_path, "rb") as f:
            _metadata = pickle.load(f)
        print(f"✅ FAISS 벡터스토어 로드 완료 ({_index.ntotal}개 벡터)")
    else:
        _index = faiss.IndexFlatL2(EMBED_DIM)
        _metadata = {"texts": [], "labels": []}
        print("⚠️  벡터스토어 없음 → 빈 인덱스로 초기화 (build_vectorstore.py로 학습 데이터 추가 권장)")


def _save_vectorstore():
    index_bytes = faiss.serialize_index(_index)
    with open(os.path.join(VS_DIR, "spam.index"), "wb") as f:
        f.write(index_bytes)
    with open(os.path.join(VS_DIR, "metadata.pkl"), "wb") as f:
        pickle.dump(_metadata, f)


@traceable(name="embed_query")
def _embed_query(text: str) -> np.ndarray:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=[text]
    )
    return np.array([response.data[0].embedding], dtype="float32")


@traceable(name="retrieve")
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
판정 규칙:
- 스팸 특징이 명확할 때만 "스팸"으로 판정하세요.
- 조금이라도 애매하면 반드시 "정상"으로 판정하세요.
- 링크 유도, 계정 확인 요구, 결제/인증 유도, 긴급/제한/차단 위협, 금융기관 사칭이 명확하면 "스팸"입니다.
- 일반 안내, 업무 연락, 인사말, 맥락이 불충분한 짧은 문장은 "정상"으로 두세요.

{context}[판단할 메시지]
{query}

다음 형식으로 답변하세요:
판정: 스팸 또는 정상
이유: (구체적인 이유 설명)
신뢰도: 높음 / 중간 / 낮음"""


@traceable(name="classify_with_gpt")
def classify_with_gpt(text: str, examples: list[dict] = None, model: str = "gpt-4o-mini") -> dict:
    print(f"[LangSmith] classify_with_gpt path active model={_finetune_model or model}")
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
    return _parse_result(answer, model_label, text, examples)


@traceable(name="classify_with_qwen")
def classify_with_qwen(text: str, examples: list[dict] = None) -> dict:
    print("[LangSmith] classify_with_qwen path active")
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
        return _parse_result(answer, "Qwen2.5", text, examples)
    except Exception as e:
        return {"error": f"Qwen 오류: {str(e)}"}


def _has_clear_spam_signal(text: str, examples: list[dict]) -> bool:
    text_lower = text.lower()
    suspicious_terms = (
        "[url]",
        "http://",
        "https://",
        "계정",
        "결제",
        "인증",
        "로그인",
        "링크",
        "접속",
        "확인 바랍니다",
        "즉시",
        "제한",
        "차단",
        "정지",
        "비정상",
        "신한",
        "국민",
        "농협",
        "우리은행",
        "하나은행",
        "카카오뱅크",
    )
    signal_hits = sum(1 for term in suspicious_terms if term in text_lower)
    first = examples[0] if examples else None
    strong_retrieval_match = bool(
        first
        and first["label"] == "spam"
        and first["distance"] <= 1.25
    )
    return signal_hits >= 2 or (signal_hits >= 1 and strong_retrieval_match)


def _parse_result(answer: str, model_name: str, text: str, examples: list[dict]) -> dict:
    lines = [line.strip() for line in (answer or "").splitlines() if line.strip()]
    verdict_line = next((line for line in lines if line.startswith("판정:")), lines[0] if lines else "")
    model_says_spam = "스팸" in verdict_line and "정상" not in verdict_line
    clear_spam_signal = _has_clear_spam_signal(text, examples)
    is_spam = model_says_spam or clear_spam_signal
    return {
        "model": model_name,
        "is_spam": is_spam,
        "raw_answer": answer,
        "model_says_spam": model_says_spam,
        "clear_spam_signal": clear_spam_signal,
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


@traceable(name="fast_classify")
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
    # 가장 가까운 이웃이 spam이고 거리가 가까우면 신호 강함
    closest_is_spam = first["label"] == "spam" and first["distance"] <= 1.5
    # 다수결: 7개 중 3개 이상 스팸
    majority_spam = spam_votes >= 3
    strong_spam_match = closest_is_spam or majority_spam
    return strong_spam_match and _has_spam_signals(text)


_load_vectorstore()
