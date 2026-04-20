import csv
import os
import sqlite3
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
DB_PATH = os.path.join(BACKEND, "spam_chat.db")
TRAIN_SPLIT = os.path.join(ROOT, "train_split.csv")
BACKEND_PY = os.path.join(BACKEND, "backend.py")
BUILD_VECTORSTORE_PY = os.path.join(BACKEND, "build_vectorstore.py")
VECTORSTORE_DIR = os.path.join(BACKEND, "vectorstore")


def check(condition: bool, label: str, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {label}{suffix}")
    return condition


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def count_train_split():
    total = 0
    spam = 0
    with open(TRAIN_SPLIT, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            if (row.get("label") or "").strip().lower() == "spam":
                spam += 1
    return total, spam


def table_count(conn: sqlite3.Connection, table: str) -> int:
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return int(cur.fetchone()[0])


def main() -> int:
    ok = True

    backend_text = read_text(BACKEND_PY)
    build_text = read_text(BUILD_VECTORSTORE_PY)

    ok &= check(
        '"train": os.path.join(base_dir, "..", "train_split.csv")' in backend_text,
        "load_dataset_rows uses train_split.csv for train",
    )
    ok &= check(
        '"val": os.path.join(base_dir, "..", "val_split.csv")' in backend_text,
        "load_dataset_rows uses val_split.csv for val",
    )
    ok &= check(
        'raise HTTPException(status_code=400, detail="train_split.csv媛 ?놁뒿?덈떎. split_data.py瑜?癒쇱? ?ㅽ뻾?댁＜?몄슂.")' in backend_text,
        "rag_train fails fast when train_split.csv is missing",
    )
    ok &= check(
        "training_corrections WHERE source='improve_train'" in backend_text,
        "rag_train reloads only improve_train corrections",
    )
    ok &= check(
        "VALUES (?, ?, 'improve_train')" in backend_text,
        "rag_improve stores only improve_train corrections",
    )
    ok &= check(
        'if not dry_run and split == "train":' in backend_text,
        "rag_improve write-back allowed only for train split",
    )
    ok &= check(
        'ALLOW_RAG_DIRECT_LEARN = os.getenv("ALLOW_RAG_DIRECT_LEARN", "false").strip().lower() == "true"' in backend_text,
        "direct learning is disabled by default",
    )
    ok &= check(
        'ALLOW_REPORT_VECTORSTORE_LEARN = os.getenv("ALLOW_REPORT_VECTORSTORE_LEARN", "false").strip().lower() == "true"' in backend_text,
        "report-based learning is disabled by default",
    )
    ok &= check(
        "_ensure_learning_enabled(" in backend_text and "ALLOW_RAG_DIRECT_LEARN" in backend_text,
        "rag_learn is guarded by an explicit allow flag",
    )
    ok &= check(
        "if ALLOW_REPORT_VECTORSTORE_LEARN:" in backend_text,
        "report-based vectorstore learning is guarded by an explicit allow flag",
    )
    ok &= check(
        'TRAIN_CSV = os.path.join(BASE, "..", "train_split.csv")' in build_text,
        "build_vectorstore.py points to train_split.csv",
    )
    ok &= check(
        'FileNotFoundError("train_split.csv媛 ?놁뒿?덈떎. split_data.py瑜?癒쇱? ?ㅽ뻾?댁＜?몄슂.")' in build_text,
        "build_vectorstore.py fails fast without train_split.csv",
    )
    ok &= check(
        'os.path.join(BASE, "..", "train.csv")' not in build_text,
        "build_vectorstore.py has no train.csv fallback",
    )

    ok &= check(os.path.exists(TRAIN_SPLIT), "train_split.csv exists")
    if os.path.exists(TRAIN_SPLIT):
        total, spam = count_train_split()
        ok &= check(total == 3120, "train_split total count", f"expected 3120, got {total}")
        ok &= check(spam == 418, "train_split spam count", f"expected 418, got {spam}")

    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        try:
            corrections = table_count(conn, "training_corrections")
            history = table_count(conn, "improvement_history")
            ok &= check(corrections == 0, "training_corrections is empty", f"got {corrections}")
            ok &= check(history == 0, "improvement_history is empty", f"got {history}")
        finally:
            conn.close()
    else:
        ok &= check(False, "spam_chat.db exists")

    vector_files = [
        "spam.index",
        "metadata.pkl",
        "embeddings_cache.npy",
        "cache_meta.pkl",
    ]
    present = [name for name in vector_files if os.path.exists(os.path.join(VECTORSTORE_DIR, name))]
    ok &= check(
        not present,
        "vectorstore artifacts are cleared before rebuild",
        "present: " + ", ".join(present) if present else "",
    )

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
