import pandas as pd
import sqlite3
from sklearn.model_selection import train_test_split
import os

# ── 데이터 로드 ──────────────────────────────────────
df = pd.read_csv(r"C:\Users\green\Desktop\archive2\spam.csv", encoding="latin-1")
df = df[['v1', 'v2']].copy()
df.columns = ['label', 'text']
df = df.dropna(subset=['text', 'label'])
df['label'] = df['label'].str.strip().str.lower()  # 'ham' or 'spam'

print(f"전체 데이터: {len(df)}개")
print(df['label'].value_counts())

# ── 분할: 70 / 15 / 15 ──────────────────────────────
train_df, temp_df = train_test_split(df, test_size=0.30, random_state=42, stratify=df['label'])
val_df, test_df   = train_test_split(temp_df, test_size=0.50, random_state=42, stratify=temp_df['label'])

print(f"\n훈련(train): {len(train_df)}개")
print(f"검증(val):   {len(val_df)}개")
print(f"테스트(test):{len(test_df)}개")

# ── CSV 저장 ─────────────────────────────────────────
out_dir = r"C:\Users\green\Desktop\스팸데이터"
train_df.to_csv(os.path.join(out_dir, "train.csv"), index=False, encoding="utf-8-sig")
val_df.to_csv(os.path.join(out_dir, "val.csv"),   index=False, encoding="utf-8-sig")
test_df.to_csv(os.path.join(out_dir, "test.csv"),  index=False, encoding="utf-8-sig")
print("\nCSV 저장 완료: train.csv / val.csv / test.csv")

# ── 테스트 데이터 → DB 저장 (평가 탭에서 사용) ────────
db_path = r"C:\Users\green\Desktop\스팸데이터\backend\spam_chat.db"
conn = sqlite3.connect(db_path)

conn.execute("""
    CREATE TABLE IF NOT EXISTS eval_testset (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        label TEXT NOT NULL,
        split TEXT NOT NULL DEFAULT 'test'
    )
""")
conn.execute("DELETE FROM eval_testset")  # 기존 데이터 초기화

for _, row in test_df.iterrows():
    conn.execute("INSERT INTO eval_testset (text, label, split) VALUES (?, ?, 'test')",
                 (row['text'], row['label']))

# 검증 데이터도 저장
for _, row in val_df.iterrows():
    conn.execute("INSERT INTO eval_testset (text, label, split) VALUES (?, ?, 'val')",
                 (row['text'], row['label']))

conn.commit()
conn.close()
print(f"\nDB 저장 완료: 테스트 {len(test_df)}개 + 검증 {len(val_df)}개 → eval_testset 테이블")
print("\n완료! 관리자 패널 AI 성능 평가 탭에서 바로 사용 가능합니다.")
