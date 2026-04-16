import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
import pickle
import os

base = r"C:\Users\green\Desktop\스팸데이터"

# ── 데이터 로드 ──────────────────────────────────────
train_df = pd.read_csv(os.path.join(base, "train.csv"))
val_df   = pd.read_csv(os.path.join(base, "val.csv"))
test_df  = pd.read_csv(os.path.join(base, "test.csv"))

X_train, y_train = train_df["text"], train_df["label"]
X_val,   y_val   = val_df["text"],   val_df["label"]
X_test,  y_test  = test_df["text"],  test_df["label"]

# ── 훈련 ─────────────────────────────────────────────
print("훈련 중...")
vectorizer = TfidfVectorizer(max_features=10000, ngram_range=(1, 2))
X_train_vec = vectorizer.fit_transform(X_train)
X_val_vec   = vectorizer.transform(X_val)
X_test_vec  = vectorizer.transform(X_test)

model = LogisticRegression(max_iter=1000)
model.fit(X_train_vec, y_train)
print("훈련 완료!")

# ── 검증셋 평가 ──────────────────────────────────────
y_val_pred = model.predict(X_val_vec)
print("\n[검증셋]")
print(f"  정확도:  {accuracy_score(y_val, y_val_pred)*100:.2f}%")
print(f"  정밀도:  {precision_score(y_val, y_val_pred, pos_label='spam')*100:.2f}%")
print(f"  재현율:  {recall_score(y_val, y_val_pred, pos_label='spam')*100:.2f}%")
print(f"  F1:      {f1_score(y_val, y_val_pred, pos_label='spam')*100:.2f}%")

# ── 테스트셋 평가 ────────────────────────────────────
y_test_pred = model.predict(X_test_vec)
print("\n[테스트셋]")
print(f"  정확도:  {accuracy_score(y_test, y_test_pred)*100:.2f}%")
print(f"  정밀도:  {precision_score(y_test, y_test_pred, pos_label='spam')*100:.2f}%")
print(f"  재현율:  {recall_score(y_test, y_test_pred, pos_label='spam')*100:.2f}%")
print(f"  F1:      {f1_score(y_test, y_test_pred, pos_label='spam')*100:.2f}%")
cm = confusion_matrix(y_test, y_test_pred, labels=['spam','ham'])
print(f"  혼동행렬: TP={cm[0,0]} FN={cm[0,1]} FP={cm[1,0]} TN={cm[1,1]}")

# ── 모델 저장 ─────────────────────────────────────────
model_dir = os.path.join(base, "backend", "ml_model")
os.makedirs(model_dir, exist_ok=True)

with open(os.path.join(model_dir, "vectorizer.pkl"), "wb") as f:
    pickle.dump(vectorizer, f)
with open(os.path.join(model_dir, "model.pkl"), "wb") as f:
    pickle.dump(model, f)

print(f"\n모델 저장 완료: {model_dir}")
print("백엔드에서 ML 모델을 사용할 준비가 됐습니다.")
