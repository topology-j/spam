# SpamGuard

FastAPI + Vue3 기반 스팸 감지 서비스. RAG(검색 증강 생성)를 활용해 GPT-4o-mini와 Qwen2.5를 이용한 스팸 분류 시스템.

## 기술 스택

- **백엔드**: FastAPI, FAISS, OpenAI API, Ollama(Qwen2.5)
- **프론트엔드**: Vue 3, TypeScript, Vite
- **DB**: SQLite

## 실행 방법

**백엔드**
```powershell
cd backend
uvicorn backend:app --reload --host 0.0.0.0 --port 8000
```

**프론트엔드**
```powershell
cd frontend
npm install
npm run dev
```

## 주요 기능

- 실시간 스팸 메시지 감지 (채팅 기반)
- RAG 기반 듀얼 모델 평가 (GPT / Qwen)
- 관리자 대시보드: 검증셋/테스트셋 성능 평가, 오탐/미탐 상세 결과 확인
- 스팸 키워드 관리, 신고 처리, 사용자 관리

## 데이터셋

- `train.csv` / `val.csv` / `test.csv`: 스팸/정상 메시지 분류 데이터
- FAISS 벡터스토어: `backend/vectorstore/`
