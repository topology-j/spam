# SpamGuard

FastAPI + Vue3 기반 AI 스팸 감지 서비스. RAG(검색 증강 생성)를 활용해 GPT-4o-mini와 Qwen2.5를 이용한 스팸 분류 시스템.

## 사용 AI 모델

| 모델 | 용도 | 비고 |
|------|------|------|
| **GPT-4o-mini** (OpenAI) | 스팸 판별 메인 모델 | Test F1 77.8% — 최종 선정 모델 |
| **Qwen2.5:1.5b** (Ollama) | 스팸 판별 보조 모델 | 로컬 실행, 한국어 스팸에 취약 |
| **text-embedding-3-small** (OpenAI) | 텍스트 임베딩 | FAISS 벡터스토어 구축 |

## 주요 기능

- **AI 스팸 판별**: RAG 기반 GPT-4o-mini / Qwen2.5 듀얼 모델로 메시지 스팸 여부 판별
- **파일 업로드 스팸 판별**: 텍스트 파일 업로드 시 AI가 자동으로 스팸 여부 분석
- **상담사 채팅**: 상담사가 채팅 중 스팸 키워드를 직접 등록 가능
- **상담사 평가**: 사용자가 상담사에 대한 별점 및 리뷰 작성 가능
- **리뷰 조회**: 상담사·관리자·개발자가 전체 상담 평가 결과 확인 가능
- **LangSmith 연동**: 개발자 전용 LangSmith 트레이싱 페이지에서 AI 실행 이력 조회
- **관리자 대시보드**: 검증셋/테스트셋 성능 평가, 오탐/미탐 상세 확인, 사용자·키워드·신고 관리
- **BGM**: Viva la Vida - Freedom Orchestra

## 기술 스택

- **백엔드**: FastAPI, FAISS, OpenAI API, Ollama(Qwen2.5), LangSmith
- **프론트엔드**: Vue 3, TypeScript, Vite
- **DB**: SQLite

## 실행 방법

**백엔드**
```bash
cd backend
uvicorn backend:app --reload --host 0.0.0.0 --port 8001
```

**프론트엔드**
```bash
cd frontend
npm install
npm run dev
```

## 데이터셋

- `train_split.csv` / `val_split.csv` / `test_split.csv`: 스팸/정상 메시지 분류 데이터 (누수 방지 분리)
- FAISS 벡터스토어: `backend/vectorstore/` (학습 데이터 3,120개)

## 성능 개선 과정

### 1차 검증

- Validation F1: 9.5%
- 문제점
  - Recall 5.0%
  - 스팸 20건 중 1건만 탐지
- 원인
  - 모델이 지나치게 보수적으로 정상 메시지로 분류

### 2차 검증

- 오분류 사례 분석 및 판정 로직 개선
- Validation F1: 66.7%

### 3차 검증

- RAG 판정 로직 수정
- Vector Store 반영 문제 수정
- Validation F1: 97.4%

## 트러블슈팅 1 - 실행 경로 및 Vector Store 반영 문제

### 문제

추가 개선을 진행했음에도 검증 결과가 계속 동일하게 출력됨.

### 분석

- 실행 중인 서버 확인
- 검증 함수 확인
- val_text별 예측 결과 확인
- retrieve 문서 확인

### 원인

- Stale 서버가 8000 포트를 점유
- 최신 코드가 아닌 이전 코드 실행
- 최신 Vector Store가 실제 검증에 반영되지 않음

### 해결

- 실행 경로 정리
- 최신 Vector Store 재적용

### 결과

- Validation F1 66.7% -> 97.4%

## 트러블슈팅 2 - 데이터 누수(Data Leakage)

### 문제

테스트 수행 시 GPT/Qwen 모두 F1 100.0% 기록

사용자 판단:

> 결과가 지나치게 높아 데이터 누수를 의심

### 원인 분석

Vector Store에 Validation/Test 데이터가 포함됨.

Overlap 확인 결과:

- Train: 120 / 120
- Validation: 29 / 40
- Test: 17 / 40

원인:

- `/rag/improve` 수행 시 Validation/Test 오분류 결과가 Vector Store에 다시 저장됨

### 해결

- Validation/Test 데이터 writeback 차단
- Train 데이터만 학습 반영
- 오염된 Vector Store 재생성

### 결과

누수로 인한 100% 결과는 공식 결과에서 제외

## 최종 성능

| 모델 | Validation F1 | Test F1 |
|------|--------------|---------|
| GPT-4o-mini | 90.3% | **77.8%** |
| Qwen2.5:1.5b | 8.0% | 16.7% |

최종 평가는 데이터 누수 제거 후 수행한 결과를 기준으로 사용하였다.
