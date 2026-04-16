import os
from dotenv import load_dotenv
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

# =========================
# 1. API KEY
# =========================
load_dotenv(override=True)

client = OpenAI()

# =========================
# 2. DATA
# =========================
texts = [
    "스팸 메일은 광고성 이메일이다",
    "피싱 메일은 개인정보 탈취이다",
    "무료, 당첨, 클릭 유도는 스팸 특징이다",
    "긴급 송금 요청은 피싱일 가능성이 높다",
    "업무 관련 일정 안내는 정상 메일이다"
]

# =========================
# 3. EMBEDDING + FAISS
# =========================
embeddings = OpenAIEmbeddings(api_key=os.environ["OPENAI_API_KEY"])
vectorstore = FAISS.from_texts(texts, embeddings)

# =========================
# 4. RETRIEVE
# =========================
def retrieve(query, top_k=2):
    docs = vectorstore.similarity_search(query, k=top_k)
    return [d.page_content for d in docs]

# =========================
# 5. GPT CALL
# =========================
def gpt_llm(prompt):
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content

# =========================
# 6. RAG CLASSIFY
# =========================
def rag_classify(query):
    docs = retrieve(query)
    context = "\n".join(docs)

    prompt = f"""
다음 문서를 기반으로 이메일이 스팸인지 판단해라.

문서:
{context}

질문:
{query}

반드시 아래 형식으로만 답해:
Spam: Yes 또는 No
이유: 20자 이내
"""

    return gpt_llm(prompt)

# =========================
# 7. TEST
# =========================
print(rag_classify("이 이메일은 무료 당첨입니다 클릭하세요"))
print(rag_classify("회의 일정 알려드립니다"))
