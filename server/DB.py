from typing import Any
import socket
import struct
import threading
import sqlite3
import uuid #生成唯一ID
from common import send_json, recv_json, send_text

inv_lock = threading.Lock()
FORMAT = 'utf-8'
DB_PATH = "all_info.db"
PORT = 16211
SERVER = '140.113.17.12'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")      
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS User (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT NOT NULL UNIQUE,         
            password TEXT NOT NULL,
            room_id TEXT,   
            user_code TEXT,
            is_connected INTEGER NOT NULL DEFAULT 0       
        );
        """)        
       
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_name ON User(name);")
        conn.execute("UPDATE User SET is_connected = 0")

        #遊玩紀錄表
        conn.execute("""
        CREATE TABLE IF NOT EXISTS PlayRecord (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            game_name TEXT NOT NULL,
            play_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 評論表
        conn.execute("""
        CREATE TABLE IF NOT EXISTS Review (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_name TEXT NOT NULL,
            username TEXT NOT NULL,
            version TEXT,
            rating INTEGER CHECK(rating >= 1 AND rating <= 5),
            comment TEXT,
            review_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        conn.commit()

def ok(data):
    return {"ok": True, "data": data}

def err(code, msg):
    return {"ok": False, "error": {"code": code, "message": msg}}

def db_request(req: dict) -> dict:
    op = req.get("op")
    if not op: return err("no_op", "missing 'op'")

    #每次處理請求時才建立連線
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        #查user
        if op == "get_user_by_name":
            name = req.get("name")
            if not name:
                return err("bad_request", "missing 'name'")
            cur.execute("SELECT * FROM User WHERE name = ?", (name,))
            row = cur.fetchone()
            if not row:
                return err("not_found", f"user '{name}' not found")
            user = dict(row)
            return ok({"user": user})

        #建立user
        elif op == "create_user":
            name = req.get("name")
            password = req.get("password")
            user_type_raw = req.get("user_type")  

            if not name or not password:
                print("missing name or password")
                return err("bad_request", "missing name or password")

            #user_type: 0=玩家、1=開發者
            try:
                user_type = int(user_type_raw) if user_type_raw is not None else 0
            except ValueError:
                user_type = 0

            #給開發者一組 UUID
            dev_code = str(uuid.uuid4()) if user_type == 1 else None

            try:
                cur.execute(
                    """
                    INSERT INTO User
                    (name, password, room_id, user_code, is_connected)
                    VALUES (?, ?, NULL, ?, 1)
                    """,
                    (name, password, dev_code)
                )
            except sqlite3.IntegrityError:
                print("user already exists")
                return err("user_exists", f"user '{name}' already exists")

            user_id = cur.lastrowid
            conn.commit()

            cur.execute("SELECT * FROM User WHERE id = ?", (user_id,))
            row = cur.fetchone()
            user = dict(row)
            return ok({"user": user})


        #設定user登入/出
        elif op == "set_user_connected":
            user_id = req.get("user_id") #登入更新
            username = req.get("username") #登出更新
            is_connected = req.get("is_connected")
            
            if is_connected is None:
                return err("bad_request", "missing 'is_connected'")
            
            if user_id:
                cur.execute(
                    "UPDATE User SET is_connected = ? WHERE id = ?",
                    (int(bool(is_connected)), user_id)
                )
                if cur.rowcount == 0:
                    return err("not_found", f"user id {user_id} not found")
                conn.commit()
                cur.execute("SELECT * FROM User WHERE id = ?", (user_id,))
            elif username:
                cur.execute(
                    "UPDATE User SET is_connected = ? WHERE name = ?",
                    (int(bool(is_connected)), username)
                )
                if cur.rowcount == 0:
                    return err("not_found", f"user '{username}' not found")
                conn.commit()
                cur.execute("SELECT * FROM User WHERE name = ?", (username,))
            else:
                return err("bad_request", "missing 'user_id' or 'username'")
            
            row = cur.fetchone()
            user = dict(row)
            return ok({"user": user})
        
        elif op == "add_play_record":
            cur.execute("INSERT INTO PlayRecord (username, game_name) VALUES (?, ?)", 
                       (req['username'], req['game_name']))
            conn.commit()
            return ok({})

        elif op == "check_play_eligibility":
            cur.execute("SELECT 1 FROM PlayRecord WHERE username = ? AND game_name = ?", 
                       (req['username'], req['game_name']))
            return ok({"eligible": cur.fetchone() is not None})

        elif op == "submit_review":
            cur.execute("INSERT INTO Review (game_name, username, version, rating, comment) VALUES (?, ?, ?, ?, ?)",
                       (req['game_name'], req['username'], req.get('version', '1'), req['rating'], req['comment']))
            conn.commit()
            return ok({})

        elif op == "get_game_reviews":
            cur.execute("SELECT username, version, rating, comment FROM Review WHERE game_name = ?", (req['game_name'],))
            reviews = [dict(row) for row in cur.fetchall()]
            return ok({"reviews": reviews})

        else:
            return err("unknown_op", f"unknown op '{op}'")
    finally:
        conn.close()

def db_loop(db_sock):
    while True:
        raw = recv_json(db_sock)
        if raw is None: break
        try:
            resp = db_request(raw)
        except Exception as e:
            resp = err("db_exception", str(e))

        send_json(db_sock, resp)

#TCP
DB = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
DB.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    DB.connect((SERVER,PORT))
    # 【新增】連線成功時的顯示
    print(f"[DB] connect server success at {SERVER}:{PORT}")
    
    send_text(DB, "DB")    
    init_db()
    db_loop(DB)  

except ConnectionRefusedError:
    print(f"[ERROR] Failed to connect to server at {SERVER}:{PORT}. Connection refused.")
except socket.gaierror:
    print(f"[ERROR] Address resolution failed for {SERVER}:{PORT}. Check the server IP.")
except Exception as e:
    print(f"[ERROR] An unexpected error occurred during connection: {e}")
