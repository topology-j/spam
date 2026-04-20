Data Leakage Guard

Rules
- Training data for RAG must come from `train_split.csv` only.
- Validation and test data must never be written back into `vectorstore`.
- Only corrections created from `split='train'` may be stored in `training_corrections`.
- `rag_train` may reload only `training_corrections.source='improve_train'`.
- If `train_split.csv` is missing, training must fail fast instead of falling back to `train.csv`.
- Direct learning via `/rag/learn` must stay disabled by default.
- Report-based vectorstore learning must stay disabled by default.

Safe loop
1. Run `split_data.py`.
2. Build or train from `train_split.csv`.
3. Evaluate on `val` or `test`.
4. If improvement is needed, allow write-back only for `split='train'`.
5. Re-run evaluation on `val` or `test`.

Reset checklist
- Delete `backend/vectorstore/spam.index`
- Delete `backend/vectorstore/metadata.pkl`
- Delete `backend/vectorstore/embeddings_cache.npy`
- Delete `backend/vectorstore/cache_meta.pkl`
- Clear `training_corrections`
- Clear `improvement_history`

Expected clean state
- `train_split.csv` total: `3120`
- `train_split.csv` spam count: `418`
- `training_corrections`: `0`
- `improvement_history`: `0`

Recommended verification
- Run `backend/check_leakage_guard.py`
- Confirm `train_split.csv` exists
- Confirm the guard script reports `PASS`
- Rebuild vectorstore
- Confirm vector count returns near `3120` and spam count returns to `418`

Safety flags
- `ALLOW_RAG_DIRECT_LEARN=false`
- `ALLOW_REPORT_VECTORSTORE_LEARN=false`
- Only enable these temporarily when you intentionally want manual production learning.
