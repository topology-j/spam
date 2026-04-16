import sqlite3
db = r"C:\Users\green\Desktop\스팸데이터\backend\spam_chat.db"
conn = sqlite3.connect(db)
conn.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('report_enabled', 'true')")
conn.commit()
row = conn.execute("SELECT * FROM system_settings WHERE key='report_enabled'").fetchone()
print("현재 값:", row)
conn.close()
