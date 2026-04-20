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

## 모델 성능 (최종)

| 모델 | Validation F1 | Test F1 |
|------|--------------|---------|
| GPT-4o-mini | 90.3% | **77.8%** |
| Qwen2.5:1.5b | 8.0% | 16.7% |
