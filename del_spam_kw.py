import sqlite3
db = r"C:\Users\green\Desktop\스팸데이터\backend\spam_chat.db"
conn = sqlite3.connect(db)
conn.execute("DELETE FROM spam_keywords WHERE keyword='스팸'")
conn.commit()
print("삭제 완료")
conn.close()
