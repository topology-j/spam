from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt, JWTError
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List
import os
import io
import pickle

# ─────────────────────────────
# APP
# ─────────────────────────────
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────
# CONFIG
# ─────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# ─────────────────────────────
# DB
# ─────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "spam_chat.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        nickname TEXT,
        name TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        detail_address TEXT,
        postal_code TEXT,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS spam_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        email_content TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        counselor_id INTEGER,
        counselor_note TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (counselor_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS spam_keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS chat_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        message TEXT NOT NULL,
        is_spam INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS counselor_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL UNIQUE,
        reviewer_id INTEGER NOT NULL,
        counselor_id INTEGER,
        stars INTEGER NOT NULL,
        comment TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (report_id) REFERENCES spam_reports(id),
        FOREIGN KEY (reviewer_id) REFERENCES users(id),
        FOREIGN KEY (counselor_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS user_spam_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        rule_type TEXT NOT NULL,
        value TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)
    conn.commit()
    # detail_address 컬럼 마이그레이션
    try:
        conn.execute("ALTER TABLE users ADD COLUMN detail_address TEXT")
        conn.commit()
    except Exception:
        pass
    # 리뷰 카테고리 별점 마이그레이션
    for col in ["accuracy_stars", "processing_stars", "clarity_stars", "speed_stars"]:
        try:
            conn.execute(f"ALTER TABLE counselor_reviews ADD COLUMN {col} INTEGER")
            conn.commit()
        except Exception:
            pass
    conn.close()


def seed():
    conn = get_db()
    cur = conn.cursor()
    users = [
        ("admin", "admin123", "admin", "관리자", "관리자", "010-0000-0000", "admin@spam.com", "서울시", "00000"),
        ("counselor1", "counselor123", "counselor", "상담원1", "상담원", "010-1111-1111", "counselor1@spam.com", "서울시", "11111"),
        ("user1", "user123", "user", "유저1", "사용자", "010-2222-2222", "user1@spam.com", "서울시", "22222"),
        ("green314", "1234", "developer", "그린", "개발자", "010-3333-3333", "green@spam.com", "서울시", "33333"),
    ]
    for username, pw, role, nickname, name, phone, email, address, postal_code in users:
        cur.execute("SELECT id FROM users WHERE username=?", (username,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO users (username, password_hash, nickname, name, phone, email, address, postal_code, role) VALUES (?,?,?,?,?,?,?,?,?)",
                (username, pwd_context.hash(pw), nickname, name, phone, email, address, postal_code, role)
            )

    # 기본 스팸 키워드
    keywords = ["무료", "당첨", "클릭", "긴급", "송금", "비밀번호", "계좌번호", "피싱", "광고"]
    for kw in keywords:
        cur.execute("INSERT OR IGNORE INTO spam_keywords (keyword) VALUES (?)", (kw,))

    # 기본 시스템 설정
    cur.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('report_enabled', 'true')")

    conn.commit()
    conn.close()


init_db()
seed()

# ─────────────────────────────
# AUTH
# ─────────────────────────────
def create_token(user_id, username, role):
    exp = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": str(user_id), "username": username, "role": role, "exp": exp},
        SECRET_KEY, algorithm=ALGORITHM
    )


def get_current_user(cred: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(cred.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return {"id": int(payload["sub"]), "username": payload["username"], "role": payload["role"]}
    except JWTError:
        raise HTTPException(status_code=401, detail="인증 오류")


def require_role(*roles):
    def checker(user=Depends(get_current_user)):
        effective = "admin" if user["role"] == "developer" else user["role"]
        if effective not in roles:
            raise HTTPException(status_code=403, detail="권한 없음")
        return user
    return checker


# ─────────────────────────────
# ML 모델 로드 (TF-IDF + 로지스틱 회귀)
# ─────────────────────────────
_ML_DIR = os.path.join(os.path.dirname(__file__), "ml_model")
_vectorizer = None
_ml_model = None

def _load_ml_model():
    global _vectorizer, _ml_model
    vec_path   = os.path.join(_ML_DIR, "vectorizer.pkl")
    model_path = os.path.join(_ML_DIR, "model.pkl")
    if os.path.exists(vec_path) and os.path.exists(model_path):
        with open(vec_path, "rb") as f:
            _vectorizer = pickle.load(f)
        with open(model_path, "rb") as f:
            _ml_model = pickle.load(f)
        print("✅ ML 모델 로드 완료 (TF-IDF + 로지스틱 회귀)")
    else:
        print("⚠️  ML 모델 없음 → 키워드 방식으로 동작")

_load_ml_model()


# ─────────────────────────────
# 스팸 감지 (ML 우선, 키워드 보조)
# ─────────────────────────────
def detect_spam(text: str) -> bool:
    # ML 모델이 있으면 ML 사용
    if _vectorizer is not None and _ml_model is not None:
        vec = _vectorizer.transform([text])
        pred = _ml_model.predict(vec)[0]
        if pred == "spam":
            return True
        # ML이 ham으로 판단해도 키워드에 있으면 스팸으로 추가 체크
    # 키워드 보조
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT keyword FROM spam_keywords")
    keywords = [row["keyword"] for row in cur.fetchall()]
    conn.close()
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


# ─────────────────────────────
# LOGIN / REGISTER
# ─────────────────────────────
class LoginReq(BaseModel):
    username: str
    password: str


class RegisterReq(BaseModel):
    username: str
    password: str
    nickname: str
    name: str
    phone: str
    email: str
    address: str
    detail_address: Optional[str] = ""
    postal_code: str


@app.post("/auth/login")
def login(req: LoginReq):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=?", (req.username,))
    user = cur.fetchone()
    conn.close()
    if not user or not pwd_context.verify(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다")
    return {"token": create_token(user["id"], user["username"], user["role"]), "username": user["username"], "role": user["role"]}


@app.post("/auth/register")
def register(req: RegisterReq):
    if len(req.username) < 2 or len(req.username) > 30:
        raise HTTPException(status_code=400, detail="아이디는 2~30자여야 합니다")
    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="비밀번호는 4자 이상이어야 합니다")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username=?", (req.username,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="이미 사용 중인 아이디입니다")
    cur.execute(
        "INSERT INTO users (username, password_hash, nickname, name, phone, email, address, detail_address, postal_code, role) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (req.username, pwd_context.hash(req.password), req.nickname, req.name, req.phone, req.email, req.address, req.detail_address, req.postal_code, "user")
    )
    conn.commit()
    conn.close()
    return {"message": "회원가입 완료"}


# ─────────────────────────────
# USERS
# ─────────────────────────────
@app.get("/users/me")
def get_me(user=Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, nickname, name, phone, email, address, detail_address, postal_code, role, created_at FROM users WHERE id=?", (user["id"],))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="유저 없음")
    return dict(row)


class ProfileUpdateReq(BaseModel):
    nickname: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    detail_address: Optional[str] = None
    postal_code: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


@app.patch("/users/me")
def update_me(req: ProfileUpdateReq, user=Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (user["id"],))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="유저 없음")

    new_hash = row["password_hash"]
    if req.new_password:
        if not req.current_password or not pwd_context.verify(req.current_password, row["password_hash"]):
            conn.close()
            raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다")
        new_hash = pwd_context.hash(req.new_password)

    cur.execute("""
        UPDATE users SET
            nickname = COALESCE(?, nickname),
            name = COALESCE(?, name),
            phone = COALESCE(?, phone),
            email = COALESCE(?, email),
            address = COALESCE(?, address),
            detail_address = COALESCE(?, detail_address),
            postal_code = COALESCE(?, postal_code),
            password_hash = ?
        WHERE id = ?
    """, (req.nickname, req.name, req.phone, req.email, req.address, req.detail_address, req.postal_code, new_hash, user["id"]))
    conn.commit()
    conn.close()
    return {"message": "수정 완료"}


@app.get("/admin/users")
def get_users(user=Depends(require_role("admin"))):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, nickname, name, phone, email, address, postal_code, role, created_at FROM users ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


class RoleUpdateReq(BaseModel):
    role: str


@app.patch("/admin/users/{user_id}/role")
def update_user_role(user_id: int, req: RoleUpdateReq, user=Depends(require_role("admin"))):
    caller_role = user["role"]
    if caller_role == "developer":
        allowed = {"user", "counselor", "admin", "developer"}
    else:
        allowed = {"user", "counselor", "admin"}
    if req.role not in allowed:
        raise HTTPException(status_code=403, detail="해당 역할로 변경할 권한이 없습니다")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id=?", (user_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    cur.execute("UPDATE users SET role=? WHERE id=?", (req.role, user_id))
    conn.commit()
    conn.close()
    return {"message": "역할이 변경되었습니다"}


# ─────────────────────────────
# SPAM REPORTS
# ─────────────────────────────
class ReportReq(BaseModel):
    email_content: str


class ReportUpdateReq(BaseModel):
    status: str
    counselor_note: Optional[str] = ""
    keywords: Optional[List[str]] = []


@app.get("/spam-reports")
def get_reports(user=Depends(require_role("admin", "counselor"))):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.*, u.username as requester
        FROM spam_reports r
        JOIN users u ON r.user_id = u.id
        ORDER BY r.created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/spam-reports/my")
def get_my_reports(user=Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.*, rv.id as review_id, rv.stars as review_stars, rv.comment as review_comment,
               u.nickname as counselor_nickname, u.username as counselor_username
        FROM spam_reports r
        LEFT JOIN counselor_reviews rv ON rv.report_id = r.id
        LEFT JOIN users u ON r.counselor_id = u.id
        WHERE r.user_id = ?
        ORDER BY r.created_at DESC
    """, (user["id"],))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/spam-reports")
def create_report(req: ReportReq, user=Depends(get_current_user)):
    if not req.email_content.strip():
        raise HTTPException(status_code=400, detail="내용을 입력해주세요")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM system_settings WHERE key='report_enabled'")
    row = cur.fetchone()
    if row and row["value"] == "false":
        conn.close()
        raise HTTPException(status_code=403, detail="현재 상담 요청이 비활성화되어 있습니다")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO spam_reports (user_id, email_content) VALUES (?, ?)",
        (user["id"], req.email_content.strip())
    )
    conn.commit()
    conn.close()
    return {"message": "신고 접수 완료"}


@app.patch("/spam-reports/{report_id}")
def update_report(report_id: int, req: ReportUpdateReq, user=Depends(require_role("admin", "counselor"))):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE spam_reports SET status=?, counselor_note=?, counselor_id=? WHERE id=?",
        (req.status, req.counselor_note, user["id"], report_id)
    )
    # 완료 처리 시 키워드 추가
    if req.keywords:
        for kw in req.keywords:
            cur.execute("INSERT OR IGNORE INTO spam_keywords (keyword) VALUES (?)", (kw,))
    conn.commit()
    conn.close()
    return {"message": "업데이트 완료"}


# ─────────────────────────────
# SYSTEM SETTINGS
# ─────────────────────────────
@app.get("/settings")
def get_settings(user=Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM system_settings")
    rows = cur.fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


class SettingUpdateReq(BaseModel):
    value: str


@app.patch("/settings/{key}")
def update_setting(key: str, req: SettingUpdateReq, user=Depends(require_role("admin"))):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)", (key, req.value))
    conn.commit()
    conn.close()
    return {"message": "설정 변경 완료"}


# ─────────────────────────────
# SPAM KEYWORDS
# ─────────────────────────────
@app.get("/spam-keywords")
def get_keywords(user=Depends(require_role("admin"))):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM spam_keywords ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.delete("/spam-keywords/{kw_id}")
def delete_keyword(kw_id: int, user=Depends(require_role("admin"))):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM spam_keywords WHERE id=?", (kw_id,))
    conn.commit()
    conn.close()
    return {"message": "삭제 완료"}


# ─────────────────────────────
# CHAT
# ─────────────────────────────
class ChatReq(BaseModel):
    message: str


@app.post("/chat")
def chat(req: ChatReq, user=Depends(get_current_user)):
    text = req.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="메시지를 입력해주세요")

    is_spam = detect_spam(text)

    conn = get_db()
    cur = conn.cursor()
    # 사용자 메시지 저장
    cur.execute(
        "INSERT INTO chat_logs (user_id, username, role, message, is_spam) VALUES (?,?,?,?,?)",
        (user["id"], user["username"], "user", text, 1 if is_spam else 0)
    )
    # AI 응답 생성
    if is_spam:
        reply = f"⚠️ 스팸으로 감지되었습니다. 해당 메일에는 스팸 특징이 포함되어 있습니다. 주의하세요."
    else:
        reply = f"✅ 정상 메일로 판단됩니다. 스팸 키워드가 감지되지 않았습니다."

    cur.execute(
        "INSERT INTO chat_logs (user_id, username, role, message, is_spam) VALUES (?,?,?,?,?)",
        (user["id"], user["username"], "ai", reply, None)
    )
    conn.commit()
    conn.close()
    return {"reply": reply, "is_spam": is_spam}


@app.post("/chat/file")
async def chat_file(file: UploadFile = File(...), user=Depends(get_current_user)):
    content = await file.read()
    filename = file.filename or "파일"
    text = ""

    if filename.lower().endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content))
            for page in reader.pages:
                text += (page.extract_text() or "")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF 읽기 실패: {str(e)}")
    else:
        try:
            text = content.decode("utf-8")
        except Exception:
            text = content.decode("latin-1", errors="ignore")

    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="파일에서 텍스트를 추출할 수 없습니다")

    is_spam = detect_spam(text)
    if is_spam:
        reply = f"⚠️ [{filename}] 스팸으로 감지되었습니다. 파일 내용에 스팸 키워드가 포함되어 있습니다."
    else:
        reply = f"✅ [{filename}] 정상 파일로 판단됩니다. 스팸 키워드가 감지되지 않았습니다."

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chat_logs (user_id, username, role, message, is_spam) VALUES (?,?,?,?,?)",
        (user["id"], user["username"], "user", f"[파일업로드] {filename}", 1 if is_spam else 0)
    )
    cur.execute(
        "INSERT INTO chat_logs (user_id, username, role, message, is_spam) VALUES (?,?,?,?,?)",
        (user["id"], user["username"], "ai", reply, None)
    )
    conn.commit()
    conn.close()
    return {"reply": reply, "is_spam": is_spam, "filename": filename, "text_preview": text[:500]}


@app.get("/chat/history")
def chat_history(user=Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM chat_logs WHERE user_id=? ORDER BY created_at ASC",
        (user["id"],)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/chat/all")
def chat_all(user=Depends(require_role("admin", "counselor"))):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM chat_logs ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────
# COUNSELOR REVIEWS
# ─────────────────────────────
class ReviewReq(BaseModel):
    report_id: int
    stars: int
    comment: Optional[str] = ""
    accuracy_stars: Optional[int] = None
    processing_stars: Optional[int] = None
    clarity_stars: Optional[int] = None
    speed_stars: Optional[int] = None


@app.post("/counselor-reviews")
def create_review(req: ReviewReq, user=Depends(get_current_user)):
    if not (1 <= req.stars <= 5):
        raise HTTPException(status_code=400, detail="별점은 1~5 사이여야 합니다")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT counselor_id FROM spam_reports WHERE id=? AND user_id=?", (req.report_id, user["id"]))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="신고를 찾을 수 없습니다")
    cur.execute(
        "INSERT OR IGNORE INTO counselor_reviews (report_id, reviewer_id, counselor_id, stars, comment, accuracy_stars, processing_stars, clarity_stars, speed_stars) VALUES (?,?,?,?,?,?,?,?,?)",
        (req.report_id, user["id"], row["counselor_id"], req.stars, req.comment,
         req.accuracy_stars, req.processing_stars, req.clarity_stars, req.speed_stars)
    )
    conn.commit()
    conn.close()
    return {"message": "평가 완료"}


@app.get("/counselor-reviews")
def get_reviews(user=Depends(require_role("admin"))):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT rv.*, u1.username as reviewer, u2.username as counselor_name, r.email_content
        FROM counselor_reviews rv
        JOIN users u1 ON rv.reviewer_id = u1.id
        LEFT JOIN users u2 ON rv.counselor_id = u2.id
        JOIN spam_reports r ON rv.report_id = r.id
        ORDER BY rv.created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/counselor-reviews/mine")
def get_my_reviews(user=Depends(require_role("counselor"))):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT rv.*, u.username as reviewer, r.email_content
        FROM counselor_reviews rv
        JOIN users u ON rv.reviewer_id = u.id
        JOIN spam_reports r ON rv.report_id = r.id
        WHERE rv.counselor_id = ?
        ORDER BY rv.created_at DESC
    """, (user["id"],))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────
# USER SPAM RULES
# ─────────────────────────────
class SpamRuleReq(BaseModel):
    rule_type: str
    value: str


@app.get("/user-spam-rules")
def get_spam_rules(user=Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_spam_rules WHERE user_id=? ORDER BY created_at DESC", (user["id"],))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/user-spam-rules")
def add_spam_rule(req: SpamRuleReq, user=Depends(get_current_user)):
    if req.rule_type not in ("keyword", "sentence", "email"):
        raise HTTPException(status_code=400, detail="잘못된 규칙 타입입니다")
    if not req.value.strip():
        raise HTTPException(status_code=400, detail="값을 입력해주세요")
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO user_spam_rules (user_id, rule_type, value) VALUES (?,?,?)",
        (user["id"], req.rule_type, req.value.strip())
    )
    conn.commit()
    conn.close()
    return {"message": "규칙 추가 완료"}


@app.delete("/user-spam-rules/{rule_id}")
def delete_spam_rule(rule_id: int, user=Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM user_spam_rules WHERE id=? AND user_id=?", (rule_id, user["id"]))
    conn.commit()
    conn.close()
    return {"message": "삭제 완료"}


# ─────────────────────────────
# AI 성능 평가
# ─────────────────────────────
class EvalItem(BaseModel):
    text: str
    label: str  # 'spam' or 'ham'

def _run_evaluation(items):
    tp = tn = fp = fn = 0
    results = []
    for item in items:
        predicted = detect_spam(item["text"])
        actual = item["label"] == "spam"
        if actual and predicted:          tp += 1
        elif not actual and not predicted: tn += 1
        elif not actual and predicted:     fp += 1
        elif actual and not predicted:     fn += 1
        results.append({
            "text": item["text"][:120],
            "label": item["label"],
            "predicted": "spam" if predicted else "ham",
            "correct": predicted == actual,
        })
    total = len(items)
    accuracy  = (tp + tn) / total if total else 0
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall    = tp / (tp + fn) if (tp + fn) else 0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    return {
        "total": total,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "results": results,
    }

@app.post("/ai/evaluate")
def ai_evaluate(items: list[EvalItem], user=Depends(require_role("admin"))):
    if not items:
        raise HTTPException(status_code=400, detail="평가 데이터가 없습니다")
    data = [{"text": it.text, "label": it.label.strip().lower()} for it in items]
    return _run_evaluation(data)

@app.get("/ai/evaluate/auto")
def ai_evaluate_auto(user=Depends(require_role("admin"))):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT message, is_spam FROM chat_logs WHERE role='user' AND is_spam IS NOT NULL ORDER BY created_at DESC LIMIT 500"
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail="평가할 레이블된 데이터가 없습니다.")
    data = [{"text": r["message"], "label": "spam" if r["is_spam"] == 1 else "ham"} for r in rows]
    result = _run_evaluation(data)
    result["source"] = "chat_logs"
    result["note"] = f"chat_logs에서 자동 수집된 {len(data)}개 레이블 데이터"
    return result

@app.get("/ai/evaluate/testset")
def ai_evaluate_testset(split: str = "test", user=Depends(require_role("admin"))):
    if split not in ("test", "val"):
        raise HTTPException(status_code=400, detail="split은 'test' 또는 'val'이어야 합니다")
    conn = get_db()
    cur = conn.cursor()
    # eval_testset 테이블 없으면 안내
    try:
        cur.execute("SELECT text, label FROM eval_testset WHERE split=?", (split,))
        rows = cur.fetchall()
    except Exception:
        conn.close()
        raise HTTPException(status_code=404, detail="테스트 데이터가 없습니다. split_data.py를 먼저 실행해주세요.")
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail=f"{split} 데이터가 없습니다. split_data.py를 먼저 실행해주세요.")
    data = [{"text": r["text"], "label": r["label"]} for r in rows]
    result = _run_evaluation(data)
    result["source"] = split
    result["note"] = f"{'테스트' if split=='test' else '검증'} 데이터셋 {len(data)}개 (spam.csv에서 분할)"
    return result


# ─────────────────────────────
# ROOT
# ─────────────────────────────
@app.get("/")
def root():
    return {"status": "ok"}
