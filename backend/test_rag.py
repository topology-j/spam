from dotenv import load_dotenv
import os
load_dotenv('.env', override=True)
print('OPENAI_API_KEY:', os.getenv('OPENAI_API_KEY', 'NOT SET')[:20])
try:
    from rag_engine import classify_with_gpt
    print('RAG import: OK')
except Exception as e:
    print('RAG import FAIL:', e)
