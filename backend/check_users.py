import sqlite3
conn = sqlite3.connect('spam_chat.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT id, username, role FROM users').fetchall()
for r in rows:
    print(dict(r))
conn.close()
