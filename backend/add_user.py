import sqlite3
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
conn = sqlite3.connect('spam_chat.db')
conn.execute(
    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
    ("man2", pwd_context.hash("1234"), "counselor")
)
conn.commit()
conn.close()
print("man2 계정 생성 완료")
