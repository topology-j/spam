import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(".env", override=True)

try:
    import rag_engine
    idx = rag_engine._index
    meta = rag_engine._metadata
    print(f"RAG available: True")
    print(f"vector_count: {idx.ntotal if idx else 0}")
    if meta:
        print(f"spam: {meta['labels'].count('spam')}")
        print(f"ham: {meta['labels'].count('ham')}")
except Exception as e:
    print(f"RAG available: False")
    print(f"Error: {e}")
