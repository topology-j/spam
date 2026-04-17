"""
GPT 파인튜닝 스크립트 (OpenAI Fine-tuning API)
GPU 불필요 - 클라우드에서 학습

사용법:
  python finetune_gpt.py submit   # 파인튜닝 작업 제출
  python finetune_gpt.py status <job_id>  # 상태 확인
  python finetune_gpt.py list     # 모든 작업 목록
  python finetune_gpt.py models   # 완료된 파인튜닝 모델 목록
"""
import os
import sys
import json
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

BASE = os.path.dirname(__file__)
TRAIN_CSV = os.path.join(BASE, "..", "train.csv")
JSONL_PATH = os.path.join(BASE, "finetune_train.jsonl")
JOBS_PATH = os.path.join(BASE, "finetune_jobs.json")

SYSTEM_PROMPT = "당신은 스팸 메시지 탐지 전문가입니다. 주어진 메시지가 스팸인지 판단하세요."


def csv_to_jsonl(max_samples: int = 1000):
    """train.csv → OpenAI fine-tuning JSONL 형식 변환"""
    df = pd.read_csv(TRAIN_CSV).dropna(subset=["text", "label"])
    # 클래스 균형 맞추기 (spam 전체 + ham 동수)
    spam_df = df[df["label"] == "spam"]
    ham_df = df[df["label"] == "ham"].sample(n=min(len(spam_df) * 3, len(df[df["label"] == "ham"])), random_state=42)
    balanced = pd.concat([spam_df, ham_df]).sample(frac=1, random_state=42)
    balanced = balanced.head(max_samples)

    lines = []
    for _, row in balanced.iterrows():
        label_text = "스팸" if row["label"] == "spam" else "정상"
        lines.append(json.dumps({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"다음 메시지가 스팸인지 판단해주세요:\n\n{row['text']}"},
                {"role": "assistant", "content": f"판정: {label_text}"}
            ]
        }, ensure_ascii=False))

    with open(JSONL_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ JSONL 생성: {len(lines)}개 샘플 → {JSONL_PATH}")
    spam_cnt = balanced[balanced["label"] == "spam"].shape[0]
    ham_cnt = balanced[balanced["label"] == "ham"].shape[0]
    print(f"   spam: {spam_cnt}, ham: {ham_cnt}")
    return JSONL_PATH


def submit(model: str = "gpt-4o-mini-2024-07-18", max_samples: int = 1000):
    """파인튜닝 작업 제출"""
    print("1. JSONL 변환 중...")
    jsonl_path = csv_to_jsonl(max_samples)

    print("2. 파일 업로드 중...")
    with open(jsonl_path, "rb") as f:
        uploaded = client.files.create(file=f, purpose="fine-tune")
    print(f"   파일 ID: {uploaded.id}")

    print("3. 파인튜닝 작업 제출 중...")
    job = client.fine_tuning.jobs.create(
        training_file=uploaded.id,
        model=model,
        hyperparameters={"n_epochs": 3}
    )
    print(f"✅ 작업 제출 완료!")
    print(f"   Job ID: {job.id}")
    print(f"   Status: {job.status}")
    print(f"   Model: {job.model}")

    # 작업 ID 저장
    jobs = _load_jobs()
    jobs.append({"job_id": job.id, "model": model, "status": job.status, "fine_tuned_model": None})
    _save_jobs(jobs)
    return job.id


def check_status(job_id: str):
    """작업 상태 확인 및 완료 시 모델 ID 저장"""
    job = client.fine_tuning.jobs.retrieve(job_id)
    print(f"Job ID: {job.id}")
    print(f"Status: {job.status}")
    print(f"Model: {job.model}")
    if job.fine_tuned_model:
        print(f"Fine-tuned model: {job.fine_tuned_model}")
        # jobs 파일 업데이트
        jobs = _load_jobs()
        for j in jobs:
            if j["job_id"] == job_id:
                j["status"] = job.status
                j["fine_tuned_model"] = job.fine_tuned_model
        _save_jobs(jobs)
    return job


def list_jobs():
    jobs = client.fine_tuning.jobs.list(limit=10)
    for j in jobs.data:
        model_str = f" → {j.fine_tuned_model}" if j.fine_tuned_model else ""
        print(f"[{j.status}] {j.id} ({j.model}{model_str})")


def list_models():
    """완료된 파인튜닝 모델만 출력"""
    jobs = client.fine_tuning.jobs.list(limit=20)
    models = [(j.id, j.fine_tuned_model) for j in jobs.data if j.fine_tuned_model]
    if not models:
        print("완료된 파인튜닝 모델이 없습니다.")
    for job_id, model_id in models:
        print(f"{job_id}: {model_id}")


def _load_jobs():
    if os.path.exists(JOBS_PATH):
        with open(JOBS_PATH, "r") as f:
            return json.load(f)
    return []


def _save_jobs(jobs):
    with open(JOBS_PATH, "w") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)


def get_latest_model() -> str | None:
    """완료된 파인튜닝 모델 중 가장 최근 것 반환"""
    jobs = _load_jobs()
    for j in reversed(jobs):
        if j.get("fine_tuned_model"):
            return j["fine_tuned_model"]
    return None


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "submit":
        model = args[1] if len(args) > 1 else "gpt-4o-mini-2024-07-18"
        submit(model=model)
    elif args[0] == "status":
        if len(args) < 2:
            print("사용법: python finetune_gpt.py status <job_id>")
        else:
            check_status(args[1])
    elif args[0] == "list":
        list_jobs()
    elif args[0] == "models":
        list_models()
    else:
        print("사용법: submit | status <job_id> | list | models")
