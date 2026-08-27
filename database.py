import os
import sqlite3
from datetime import datetime, timedelta
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

# 데이터베이스 영속성 폴더 및 경로 동적 생성
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, 'room_bookings.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(force_reinit=False):
    conn = get_db_connection()
    c = conn.cursor()
    
    # 강제 초기화 혹은 재개발 시 기존 테이블 초기화
    if force_reinit:
        c.execute('DROP TABLE IF EXISTS bookings')
        c.execute('DROP TABLE IF EXISTS rooms')
        
    c.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''');
    c.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            date TEXT,
            time_slot TEXT,
            user_name TEXT,
            password_hash TEXT,
            group_id TEXT,
            purpose TEXT,
            FOREIGN KEY (room_id) REFERENCES rooms (id)
        )
    ''')
    
    # 만약 기존 DB에 purpose 컬럼이 없으면 추가하는 마이그레이션 (안전을 위함)
    try:
        c.execute('SELECT purpose FROM bookings LIMIT 1')
    except sqlite3.OperationalError:
        try:
            c.execute('ALTER TABLE bookings ADD COLUMN purpose TEXT')
        except sqlite3.OperationalError:
            pass
            
    c.execute('SELECT COUNT(*) FROM rooms')
    if c.fetchone()[0] == 0:
        c.executemany('INSERT INTO rooms (name) VALUES (?)',
                     [('대강당(비젼홀)',), ('지하강당(드림홀)',), ('별관(미션홀)',)])
    conn.commit()
    conn.close()

def get_rooms():
    conn = get_db_connection()
    rooms = [{'id': row['id'], 'name': row['name']} for row in conn.execute('SELECT * FROM rooms').fetchall()]
    conn.close()
    return rooms

def get_bookings():
    conn = get_db_connection()
    bookings = [{'id': row['id'], 'room_id': row['room_id'], 'date': row['date'],
                 'time_slot': row['time_slot'], 'user_name': row['user_name'],
                 'group_id': row['group_id'], 'purpose': row['purpose']}
                for row in conn.execute('SELECT * FROM bookings').fetchall()]
    conn.close()
    return bookings

def get_recent_bookings():
    conn = get_db_connection()
    one_month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    c = conn.cursor()
    c.execute('''
        SELECT room_id, date, MIN(time_slot) as start_time, MAX(time_slot) as end_time, 
               user_name, group_id, purpose
        FROM bookings 
        WHERE date >= ?
        GROUP BY group_id
        ORDER BY date, start_time
    ''', (one_month_ago,))
    bookings = [{'room_id': row['room_id'], 'date': row['date'], 
                 'start_time': row['start_time'], 'end_time': row['end_time'], 
                 'user_name': row['user_name'], 'group_id': row['group_id'],
                 'purpose': row['purpose']}
                for row in c.fetchall()]
    conn.close()
    return bookings

def book_room(room_id, date, time_slot, user_name, password, group_id, purpose):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM bookings WHERE room_id = ? AND date = ? AND time_slot = ?',
              (room_id, date, time_slot))
    if c.fetchone():
        conn.close()
        return False
    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    c.execute('''
        INSERT INTO bookings (room_id, date, time_slot, user_name, password_hash, group_id, purpose) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (room_id, date, time_slot, user_name, password_hash, group_id, purpose))
    conn.commit()
    conn.close()
    return True

def cancel_booking(booking_id, password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT password_hash, group_id FROM bookings WHERE id = ?', (booking_id,))
    booking = c.fetchone()
    if not booking:
        conn.close()
        return False, "예약을 찾을 수 없습니다."
    if not bcrypt.check_password_hash(booking['password_hash'], password):
        conn.close()
        return False, "비밀번호가 일치하지 않습니다."
    c.execute('DELETE FROM bookings WHERE group_id = ?', (booking['group_id'],))
    conn.commit()
    conn.close()
    return True, "예약이 취소되었습니다."

# --- 신규 강단 관리 함수 ---
def add_room(name):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO rooms (name) VALUES (?)', (name,))
    conn.commit()
    conn.close()

def update_room(room_id, name):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE rooms SET name = ? WHERE id = ?', (name, room_id))
    conn.commit()
    conn.close()

def delete_room(room_id):
    conn = get_db_connection()
    c = conn.cursor()
    # 강단 삭제 시 관련 예약도 연쇄 삭제
    c.execute('DELETE FROM bookings WHERE room_id = ?', (room_id,))
    c.execute('DELETE FROM rooms WHERE id = ?', (room_id,))
    conn.commit()
    conn.close()
