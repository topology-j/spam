"""
train.csv → train_split.csv (80%) + val_split.csv (20%)
test.csv는 건드리지 않음 (최종 1회 평가용)

실행: python split_data.py
"""
import pandas as pd
import sqlite3
import os
from sklearn.model_selection import train_test_split

BASE = os.path.dirname(os.path.abspath(__file__))
TRAIN_CSV  = os.path.join(BASE, "train.csv")
TRAIN_SPLIT = os.path.join(BASE, "train_split.csv")
VAL_SPLIT   = os.path.join(BASE, "val_split.csv")
DB_PATH     = os.path.join(BASE, "backend", "spam_chat.db")

df = pd.read_csv(TRAIN_CSV)
df = df.dropna(subset=["text", "label"])
df["label"] = df["label"].str.strip().str.lower()

print(f"train.csv 전체: {len(df)}개")
print(df["label"].value_counts().to_string())

train_df, val_df = train_test_split(df, test_size=0.20, random_state=42, stratify=df["label"])

print(f"\ntrain_split: {len(train_df)}개  (spam: {(train_df['label']=='spam').sum()}, ham: {(train_df['label']=='ham').sum()})")
print(f"val_split:   {len(val_df)}개  (spam: {(val_df['label']=='spam').sum()}, ham: {(val_df['label']=='ham').sum()})")

train_df.to_csv(TRAIN_SPLIT, index=False, encoding="utf-8-sig")
val_df.to_csv(VAL_SPLIT,   index=False, encoding="utf-8-sig")
print(f"\nCSV 저장 완료: {TRAIN_SPLIT}")
print(f"               {VAL_SPLIT}")

# val_split → DB eval_testset (split='val')
# test.csv → DB eval_testset (split='test') — 기존 유지 or 덮어씀
conn = sqlite3.connect(DB_PATH)
conn.execute("""
    CREATE TABLE IF NOT EXISTS eval_testset (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        label TEXT NOT NULL,
        split TEXT NOT NULL DEFAULT 'test'
    )
""")

# val만 초기화 후 재삽입 (test는 건드리지 않음)
conn.execute("DELETE FROM eval_testset WHERE split='val'")
for _, row in val_df.iterrows():
    conn.execute("INSERT INTO eval_testset (text, label, split) VALUES (?, ?, 'val')", (row["text"], row["label"]))

# test.csv가 DB에 없으면 넣어줌
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM eval_testset WHERE split='test'")
if cur.fetchone()[0] == 0:
    test_csv = os.path.join(BASE, "test.csv")
    if os.path.exists(test_csv):
        test_df = pd.read_csv(test_csv).dropna(subset=["text", "label"])
        for _, row in test_df.iterrows():
            conn.execute("INSERT INTO eval_testset (text, label, split) VALUES (?, ?, 'test')", (row["text"], row["label"]))
        print(f"test.csv → DB 저장: {len(test_df)}개")

conn.commit()
conn.close()

val_cnt = len(val_df)
cur2 = sqlite3.connect(DB_PATH).cursor()
cur2.execute("SELECT split, COUNT(*) FROM eval_testset GROUP BY split")
print(f"\nDB eval_testset: {dict(cur2.fetchall())}")
print("\n완료!")
