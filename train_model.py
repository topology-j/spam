import pandas as pd
import numpy as np
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.base import BaseEstimator, TransformerMixin
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


# ── 추가 피처 추출기 ─────────────────────────────────
class TextFeatures(BaseEstimator, TransformerMixin):
    """유료번호, 대문자 비율, 특수문자, 광고 약어 등 수동 피처"""
    def fit(self, X, y=None): return self
    def transform(self, X):
        feats = []
        for text in X:
            t = str(text)
            feats.append([
                # 유료 전화번호 패턴 (090..., 087..., 08...)
                len(re.findall(r'\b09\d{8,9}\b', t)),
                len(re.findall(r'\b087\d{7,8}\b', t)),
                len(re.findall(r'\b08\d{8,9}\b', t)),
                # 대문자 비율
                sum(1 for c in t if c.isupper()) / max(len(t), 1),
                # 숫자 비율
                sum(1 for c in t if c.isdigit()) / max(len(t), 1),
                # 특수문자 개수
                len(re.findall(r'[!£$€&*]', t)),
                # SMS 광고 약어
                len(re.findall(r'\b(freemsg|freeMsg|txt|Txt|ur|u r|2day|4u|4 u|wkly|wk)\b', t, re.I)),
                # URL/웹사이트
                len(re.findall(r'\b(www\.|\.co\.uk|\.biz|\.net|http)\b', t, re.I)),
                # 경품/당첨 키워드
                len(re.findall(r'\b(win|winner|won|prize|cash|reward|claim|guaranteed|awarded)\b', t, re.I)),
                # 전화 유도
                len(re.findall(r'\b(call now|call free|call 0|ring now|landline)\b', t, re.I)),
                # 무료 제공
                len(re.findall(r'\bfree\b', t, re.I)),
                # 텍스트 길이
                len(t),
            ])
        return np.array(feats)


# ── 훈련 ─────────────────────────────────────────────
print("훈련 중 (개선된 모델)...")

tfidf = TfidfVectorizer(
    max_features=20000,
    ngram_range=(1, 3),       # 1~3gram으로 확대
    sublinear_tf=True,        # TF 로그 스케일
    min_df=1,
)

from scipy.sparse import hstack
from sklearn.preprocessing import StandardScaler

X_train_tfidf = tfidf.fit_transform(X_train)
X_val_tfidf   = tfidf.transform(X_val)
X_test_tfidf  = tfidf.transform(X_test)

feat_extractor = TextFeatures()
X_train_feats = feat_extractor.fit_transform(X_train)
X_val_feats   = feat_extractor.transform(X_val)
X_test_feats  = feat_extractor.transform(X_test)

# TF-IDF + 수동 피처 합치기
from scipy.sparse import csr_matrix
X_train_all = hstack([X_train_tfidf, csr_matrix(X_train_feats)])
X_val_all   = hstack([X_val_tfidf,   csr_matrix(X_val_feats)])
X_test_all  = hstack([X_test_tfidf,  csr_matrix(X_test_feats)])

model = LogisticRegression(max_iter=1000, C=5.0, class_weight={
    'spam': 2.0,   # 스팸 가중치 높여서 재현율 향상
    'ham':  1.0,
})
model.fit(X_train_all, y_train)
print("훈련 완료!")

# ── 검증셋 평가 ──────────────────────────────────────
y_val_pred = model.predict(X_val_all)
cm_val = confusion_matrix(y_val, y_val_pred, labels=['spam','ham'])
print("\n[검증셋]")
print(f"  정확도:  {accuracy_score(y_val, y_val_pred)*100:.2f}%")
print(f"  정밀도:  {precision_score(y_val, y_val_pred, pos_label='spam')*100:.2f}%")
print(f"  재현율:  {recall_score(y_val, y_val_pred, pos_label='spam')*100:.2f}%")
print(f"  F1:      {f1_score(y_val, y_val_pred, pos_label='spam')*100:.2f}%")
print(f"  혼동행렬: TP={cm_val[0,0]} FN={cm_val[0,1]} FP={cm_val[1,0]} TN={cm_val[1,1]}")

# ── 테스트셋 평가 ────────────────────────────────────
y_test_pred = model.predict(X_test_all)
cm_test = confusion_matrix(y_test, y_test_pred, labels=['spam','ham'])
print("\n[테스트셋]")
print(f"  정확도:  {accuracy_score(y_test, y_test_pred)*100:.2f}%")
print(f"  정밀도:  {precision_score(y_test, y_test_pred, pos_label='spam')*100:.2f}%")
print(f"  재현율:  {recall_score(y_test, y_test_pred, pos_label='spam')*100:.2f}%")
print(f"  F1:      {f1_score(y_test, y_test_pred, pos_label='spam')*100:.2f}%")
print(f"  혼동행렬: TP={cm_test[0,0]} FN={cm_test[0,1]} FP={cm_test[1,0]} TN={cm_test[1,1]}")

# ── 모델 저장 ─────────────────────────────────────────
model_dir = os.path.join(base, "backend", "ml_model")
os.makedirs(model_dir, exist_ok=True)

with open(os.path.join(model_dir, "vectorizer.pkl"), "wb") as f:
    pickle.dump(tfidf, f)
with open(os.path.join(model_dir, "model.pkl"), "wb") as f:
    pickle.dump(model, f)
with open(os.path.join(model_dir, "feat_extractor.pkl"), "wb") as f:
    pickle.dump(feat_extractor, f)

print(f"\n모델 저장 완료: {model_dir}")
print("백엔드에서 ML 모델을 사용할 준비가 됐습니다.")
