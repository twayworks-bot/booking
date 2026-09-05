from flask import Flask, render_template, request, redirect, url_for, flash, Blueprint
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import uuid
import os
import json
import requests

# .env 파일 수동 로드
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip()

from database import (
    init_db, get_rooms, get_bookings, book_room, cancel_booking, 
    get_recent_bookings, add_room, update_room, delete_room, 
    get_setting, set_setting
)

app = Flask(__name__)
app.secret_key = 'your-secret-key'
bcrypt = Bcrypt(app)

# 데이터베이스 초기화
init_db()

def get_kakao_icalendar_url():
    db_val = get_setting('kakao_icalendar')
    if db_val and db_val.strip():
        return db_val.strip()
    return os.environ.get('KAKAO_ICALENDAR', '')

def parse_ics_datetime(val, params=None):
    val = val.strip()
    if not val:
        return None
    
    # VALUE=DATE 형식 처리 (예: "20260905")
    if len(val) == 8 and val.isdigit():
        dt = datetime.strptime(val, "%Y%m%d")
        return dt
        
    if "T" in val:
        is_utc = val.endswith("Z")
        clean_val = val.replace("Z", "")
        try:
            dt = datetime.strptime(clean_val, "%Y%m%dT%H%M%S")
        except ValueError:
            try:
                dt = datetime.strptime(clean_val, "%Y%m%dT%H%M")
            except ValueError:
                return None
        
        if is_utc:
            # 한국 시간으로 보정 (+9시간)
            dt = dt + timedelta(hours=9)
        return dt
    return None

def parse_ics(ics_text):
    lines = []
    current_line = ""
    for line in ics_text.splitlines():
        if not line:
            continue
        if line.startswith(" ") or line.startswith("\t"):
            current_line += line[1:]
        else:
            if current_line:
                lines.append(current_line)
            current_line = line
    if current_line:
        lines.append(current_line)
        
    events = []
    current_event = None
    
    for line in lines:
        if not line.strip():
            continue
        parts = line.split(":", 1)
        if len(parts) != 2:
            continue
        name_params, val = parts
        name_parts = name_params.split(";")
        name = name_parts[0].upper().strip()
        
        params = {}
        for p in name_parts[1:]:
            if "=" in p:
                pk, pv = p.split("=", 1)
                params[pk.upper().strip()] = pv.strip()
                
        if name == "BEGIN" and val.upper().strip() == "VEVENT":
            current_event = {}
        elif name == "END" and val.upper().strip() == "VEVENT":
            if current_event and "SUMMARY" in current_event and "DTSTART" in current_event and "DTEND" in current_event:
                events.append(current_event)
            current_event = None
        elif current_event is not None:
            if name == "SUMMARY":
                summary = val.replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()
                current_event["SUMMARY"] = summary
            elif name == "DTSTART":
                dt = parse_ics_datetime(val, params)
                if dt:
                    current_event["DTSTART"] = dt
            elif name == "DTEND":
                dt = parse_ics_datetime(val, params)
                if dt:
                    current_event["DTEND"] = dt
                        
    return events

def get_event_slots(start_dt, end_dt):
    slots = []
    current_date = start_dt.date()
    while current_date <= end_dt.date():
        date_str = current_date.strftime("%Y-%m-%d")
        for slot in generate_time_slots():
            slot_time = datetime.strptime(f"{date_str} {slot}", "%Y-%m-%d %H:%M")
            if start_dt <= slot_time <= end_dt:
                slots.append((date_str, slot))
        current_date += timedelta(days=1)
    return slots

def get_room_prefixes(room):
    # 1. 강단별 기본 등록 단어 정의 (유연한 포함관계 검사 적용으로 명칭 변동 대비)
    defaults = []
    name = room['name']
    if "비젼홀" in name or "비전홀" in name or "비전횰" in name:
        defaults = ["비젼홀", "비전홀", "비전횰"]
    elif "드림홀" in name or "드림횰" in name:
        defaults = ["드림홀", "드림횰"]
    elif "별관" in name or "미션홀" in name or "별관5층" in name:
        defaults = ["별관5층", "별관오층", "별관5", "별관"]
    else:
        # 새로 추가된 신규 예배실의 경우 강단 이름 자체를 기본 단어로 삼습니다.
        name_clean = name.split('(')[0].strip()
        defaults = [name_clean] if name_clean else []
        
    # 2. DB 테이블 컬럼에 저장된 시작단어 파싱
    custom = []
    db_val = room.get('ics_prefix')
    if db_val and db_val.strip():
        custom = [p.strip() for p in db_val.split(',') if p.strip()]
        
    # 3. 데이터가 비어있으면 항상 기본 등록 단어 포함
    if not custom:
        return defaults
    return custom

def get_room_id_by_prefix(summary, rooms):
    # 공백 제거 및 다양한 괄호 기호 속성을 표준 닫는 괄호 ')'로 단일화합니다.
    normalized = (summary.replace(" ", "")
                         .replace("\t", "")
                         .replace("\r", "")
                         .replace("\n", "")
                         .replace("）", ")")  # 전각 괄호
                         .replace("]", ")")
                         .replace("］", ")"))
    
    # 각 강단의 시작단어를 순회하며 동적 매핑 검사 수행
    for r in rooms:
        prefixes = get_room_prefixes(r)
        for p in prefixes:
            p_norm = (p.replace(" ", "")
                       .replace("\t", "")
                       .replace("）", ")")
                       .replace("]", ")")
                       .replace("］", ")"))
            
            # 접두사 + ')' 형태로 시작하거나, 접두사 단어 자체로 완벽하게 매칭될 때 매핑 처리
            if normalized.startswith(p_norm + ")") or normalized.startswith(p_norm):
                return r['id']
                
    return None

def fetch_and_cache_ics():
    url = get_kakao_icalendar_url()
    app.logger.info(f"[ICS Sync] 카카오톡 캘린더 연동 시작 - 대상 URL: '{url}'")
    if not url:
        app.logger.warning("[ICS Sync] 연동 종료 - 설정된 카카오톡 ICS URL이 데이터베이스 및 .env에 존재하지 않습니다.")
        set_setting('ics_cache_data', '[]')
        set_setting('last_ics_fetch_time', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return []
        
    try:
        app.logger.info(f"[ICS Sync] URL HTTP GET 요청 수행 중... (Timeout: 5s)")
        response = requests.get(url, timeout=5)
        # iCalendar(ICS) 표준(RFC 5545) 및 한글 처리를 위해 UTF-8 인코딩을 강제 지정합니다.
        response.encoding = 'utf-8'
        app.logger.info(f"[ICS Sync] HTTP 응답 상태 코드 수신: {response.status_code}")
        if response.status_code == 200:
            app.logger.info(f"[ICS Sync] 데이터 수신 완료 (크기: {len(response.text)} 자)")
            events = parse_ics(response.text)
            app.logger.info(f"[ICS Sync] 커스텀 ICS 파서 실행 완료 - 총 {len(events)}개의 이벤트 후보 추출")
            rooms = get_rooms()
            overlay_bookings = []
            
            for idx, event in enumerate(events):
                summary = event["SUMMARY"]
                start_dt = event["DTSTART"]
                end_dt = event["DTEND"]
                
                room_id = get_room_id_by_prefix(summary, rooms)
                app.logger.info(f"[ICS Sync] 이벤트 [{idx}] 상세 검사 - 제목: '{summary}', 기간: {start_dt} ~ {end_dt}")
                if not room_id:
                    app.logger.info(f"[ICS Sync] 이벤트 [{idx}] 스킵 - 일치하는 강단 접두사 없음")
                    continue
                    
                room_name = next((r['name'] for r in rooms if r['id'] == room_id), "알 수 없음")
                slots = get_event_slots(start_dt, end_dt)
                app.logger.info(f"[ICS Sync] 이벤트 [{idx}] 매핑 성공! 강단명: '{room_name}'(ID: {room_id}), 매핑된 30분 슬롯 수: {len(slots)}개")
                
                for date_str, slot in slots:
                    app.logger.info(f"  -> 슬롯 등록: 날짜={date_str}, 시간={slot}")
                    overlay_bookings.append({
                        "id": f"ics-{idx}-{date_str}-{slot}",
                        "room_id": room_id,
                        "date": date_str,
                        "time_slot": slot,
                        "user_name": "카카오톡 연동",
                        "purpose": summary,
                        "is_overlay": True
                    })
            
            set_setting('ics_cache_data', json.dumps(overlay_bookings, ensure_ascii=False))
            set_setting('last_ics_fetch_time', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            app.logger.info(f"[ICS Sync] 동기화 정상 완결 - 총 {len(overlay_bookings)}개의 오버레이 슬롯 캐시 갱신 완료")
            return overlay_bookings
        else:
            app.logger.error(f"[ICS Sync] HTTP 상태 코드 에러 - 연동을 건너뜁니다. 코드: {response.status_code}")
    except Exception as e:
        app.logger.error(f"[ICS Sync] 연동 작업 중 예외(Exception) 발생: {e}", exc_info=True)
        
    cached = get_setting('ics_cache_data')
    if cached:
        try:
            app.logger.info("[ICS Sync] 오류 발생에 따라 이전 로컬 캐시 데이터를 복구하여 반환합니다.")
            return json.loads(cached)
        except Exception:
            pass
    return []

def get_overlay_bookings():
    last_fetch_str = get_setting('last_ics_fetch_time')
    now = datetime.now()
    should_fetch = True
    
    if last_fetch_str:
        try:
            last_fetch = datetime.strptime(last_fetch_str, "%Y-%m-%d %H:%M:%S")
            if (now - last_fetch).total_seconds() < 60:
                should_fetch = False
        except Exception:
            pass
            
    if should_fetch:
        app.logger.info("[ICS Sync] 캐시 쿨다운(1분)이 경과하였으므로 실제 동기화를 진행합니다.")
        return fetch_and_cache_ics()
    else:
        app.logger.info("[ICS Sync] 캐시 유지 시간(1분 이내)이므로 로컬 캐시 데이터를 반환합니다.")
        cached = get_setting('ics_cache_data')
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass
        return []

def get_grouped_overlay_bookings():
    # 오늘 자정(00:00:00) 기준 일자를 구해 오늘 일자 이후 내용만 필터링합니다.
    today_str = datetime.now().strftime("%Y-%m-%d")
    overlay_slots = get_overlay_bookings()
    
    # 오늘을 포함하여 오늘 이후 날짜만 걸러냅니다. (ob['date'] >= today_str)
    filtered_slots = [ob for ob in overlay_slots if ob['date'] >= today_str]
    app.logger.info(f"[ICS Report] 오늘 일자({today_str}) 이후 오버레이 슬롯 수 필터링: 총 {len(overlay_slots)}개 중 {len(filtered_slots)}개 대상")
    
    # (room_id, date, purpose)를 기준으로 슬롯 그룹화
    groups = {}
    for ob in filtered_slots:
        key = (ob['room_id'], ob['date'], ob['purpose'])
        if key not in groups:
            groups[key] = []
        groups[key].append(ob['time_slot'])
        
    grouped_reports = []
    for key, slots in groups.items():
        room_id, date, purpose = key
        # 슬롯을 정렬하여 가장 빠른 시간(시작 시간)과 가장 늦은 시간(종료 시간)을 얻음
        slots.sort()
        start_time = slots[0]
        end_time = slots[-1]
        
        grouped_reports.append({
            'room_id': room_id,
            'date': date,
            'start_time': start_time,
            'end_time': end_time,
            'user_name': '카카오톡 연동',
            'group_id': f'ics-group-{room_id}-{date}-{purpose.replace(" ", "")}',
            'purpose': purpose,
            'is_overlay': True
        })
        
    # 날짜와 시작 시간 기준으로 오름차순 정렬
    grouped_reports.sort(key=lambda x: (x['date'], x['start_time']))
    app.logger.info(f"[ICS Report] 리포트용 그룹화 완료: 총 {len(grouped_reports)}개의 연동 예약 생성")
    return grouped_reports

# 블루프린트 설정 (prefix: /reserve)
reserve_bp = Blueprint('reserve', __name__, url_prefix='/reserve')

# 주간 캘린더 날짜 생성 (페이지네이션 지원)
def generate_week_dates(week_offset=0):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = today + timedelta(weeks=week_offset)
    return [start_date + timedelta(days=i) for i in range(7)]

def generate_time_slots():
    start_time = datetime.strptime("08:00", "%H:%M").time()
    end_time = datetime.strptime("22:00", "%H:%M").time()
    slots = []
    current = start_time
    while current <= end_time:
        slots.append(current.strftime("%H:%M"))
        current = (datetime.combine(datetime.today(), current) + timedelta(minutes=30)).time()
    return slots

@reserve_bp.route('/')
def index():
    week_offset = int(request.args.get('week_offset', 0))
    if week_offset < 0 or week_offset > 16:
        flash('캘린더 범위를 벗어났습니다.', 'danger')
        week_offset = 0
    
    rooms = get_rooms()
    if not rooms:
        return render_template('index.html', rooms=[], week_dates=[], 
                             time_slots=[], calendar={}, week_offset=week_offset, active_room_id=None)
    
    # 활성화된 강단 ID (기본값은 첫 번째 강단)
    active_room_id = request.args.get('room_id')
    if active_room_id:
        try:
            active_room_id = int(active_room_id)
        except ValueError:
            active_room_id = rooms[0]['id']
    else:
        active_room_id = rooms[0]['id']
        
    room_ids = [r['id'] for r in rooms]
    if active_room_id not in room_ids:
        active_room_id = rooms[0]['id']
        
    week_dates = generate_week_dates(week_offset)
    time_slots = generate_time_slots()
    bookings = get_bookings()
    overlay_bookings = get_overlay_bookings()
    
    # 선택된 강단의 캘린더 채우기
    calendar = {}
    calendar[active_room_id] = {}
    for date in week_dates:
        date_str = date.strftime("%Y-%m-%d")
        calendar[active_room_id][date_str] = {}
        for slot in time_slots:
            calendar[active_room_id][date_str][slot] = None
            
            # 1. 일반 예약 확인
            found_booking = None
            for booking in bookings:
                booking_date = datetime.strptime(booking['date'], "%Y-%m-%d").date()
                if (booking['room_id'] == active_room_id and 
                    booking_date == date.date() and 
                    booking['time_slot'] == slot):
                    found_booking = booking
                    break
            
            if found_booking:
                calendar[active_room_id][date_str][slot] = found_booking
            else:
                # 2. 일반 예약이 없으면 카카오톡 연동(오버레이) 예약 확인
                for ob in overlay_bookings:
                    ob_date = datetime.strptime(ob['date'], "%Y-%m-%d").date()
                    if (ob['room_id'] == active_room_id and 
                        ob_date == date.date() and 
                        ob['time_slot'] == slot):
                        calendar[active_room_id][date_str][slot] = ob
                        break
    
    return render_template('index.html', rooms=rooms, week_dates=week_dates, 
                         time_slots=time_slots, calendar=calendar, week_offset=week_offset, 
                         active_room_id=active_room_id)

@reserve_bp.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        room_id = int(request.form['room_id'])
        date = request.form['date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        user_name = request.form['user_name']
        password = request.form['password']
        purpose = request.form.get('purpose', '')
        
        time_slots = generate_time_slots()
        if start_time not in time_slots or end_time not in time_slots:
            flash('유효하지 않은 시간 슬롯입니다.', 'danger')
            return redirect(url_for('reserve.book'))
        
        start_dt = datetime.strptime(start_time, "%H:%M")
        end_dt = datetime.strptime(end_time, "%H:%M")
        if start_dt >= end_dt:
            flash('종료 시간은 시작 시간보다 늦어야 합니다.', 'danger')
            return redirect(url_for('reserve.book'))
        
        group_id = str(uuid.uuid4())
        slots_to_book = []
        current = start_dt
        while current <= end_dt:
            slots_to_book.append(current.strftime("%H:%M"))
            current = current + timedelta(minutes=30)
        
        success = True
        for slot in slots_to_book:
            if not book_room(room_id, date, slot, user_name, password, group_id, purpose):
                success = False
                break
        
        if success:
            flash('예약이 완료되었습니다!', 'success')
        else:
            flash('선택한 시간대 중 일부가 이미 예약되어 있습니다.', 'danger')
        return redirect(url_for('reserve.index', room_id=room_id))
    
    # GET 요청: 예약 프리셋 지원
    preset_room_id = request.args.get('room_id')
    preset_date = request.args.get('date')
    preset_start_time = request.args.get('start_time')
    
    rooms = get_rooms()
    week_dates = []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for i in range(16 * 7):
        week_dates.append(today + timedelta(days=i))
    time_slots = generate_time_slots()
    return render_template('book.html', rooms=rooms, week_dates=week_dates, time_slots=time_slots,
                           preset_room_id=preset_room_id, preset_date=preset_date, preset_start_time=preset_start_time)

@reserve_bp.route('/cancel/<int:booking_id>', methods=['GET', 'POST'])
def cancel(booking_id):
    if request.method == 'POST':
        password = request.form['password']
        success, message = cancel_booking(booking_id, password)
        flash(message, 'success' if success else 'danger')
        return redirect(url_for('reserve.index'))
    
    return render_template('cancel.html', booking_id=booking_id)

@reserve_bp.route('/report')
def report():
    rooms = get_rooms()
    bookings = get_recent_bookings()
    overlay_bookings = get_grouped_overlay_bookings()
    
    # 일반 예약과 카카오톡 연동 예약을 병합합니다.
    combined_bookings = list(bookings) + overlay_bookings
    # 날짜와 시작시간 오름차순으로 정렬합니다.
    combined_bookings.sort(key=lambda x: (x['date'], x['start_time']))
    
    return render_template('report.html', bookings=combined_bookings, rooms=rooms)

@reserve_bp.route('/admin/rooms', methods=['GET', 'POST'])
def admin_rooms():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name')
            ics_prefix = request.form.get('ics_prefix', '').strip()
            if name:
                add_room(name, ics_prefix)
                flash(f'새로운 강단 "{name}"이(가) 추가되었습니다.', 'success')
            else:
                flash('강단 이름을 입력해주세요.', 'danger')
        elif action == 'update':
            room_id = int(request.form.get('room_id'))
            name = request.form.get('name')
            ics_prefix = request.form.get('ics_prefix', '').strip()
            if name:
                update_room(room_id, name, ics_prefix)
                # 강단 매핑명이 바뀔 수 있으므로 즉시 캐시를 만료시켜 새로 고침을 유도합니다.
                set_setting('last_ics_fetch_time', '')
                flash(f'강단 정보가 수정되었습니다.', 'success')
            else:
                flash('강단 이름을 입력해주세요.', 'danger')
        elif action == 'delete':
            room_id = int(request.form.get('room_id'))
            delete_room(room_id)
            flash('강단 및 해당 강단의 모든 예약 정보가 삭제되었습니다.', 'success')
        elif action == 'update_ics':
            url = request.form.get('kakao_icalendar', '').strip()
            set_setting('kakao_icalendar', url)
            # URL이 변경되면 즉시 캐시를 초기화하여 다음 조회 때 즉각 페치하도록 유도
            set_setting('last_ics_fetch_time', '')
            flash('카카오톡 캘린더 연동 URL 설정이 저장되었습니다.', 'success')
        return redirect(url_for('reserve.admin_rooms'))
    
    rooms = get_rooms()
    kakao_icalendar = get_setting('kakao_icalendar', '')
    default_ics = os.environ.get('KAKAO_ICALENDAR', '')
    return render_template('admin_rooms.html', rooms=rooms, 
                           kakao_icalendar=kakao_icalendar, 
                           default_ics=default_ics)

# 헬스체크 API 엔드포인트 추가 (도커 컨테이너 검사용)
@app.route('/planning/api/status')
def health_check():
    return {'status': 'healthy'}, 200

# 블루프린트 등록
app.register_blueprint(reserve_bp)

# 기본 주소 진입 시 예약 메인 화면으로 리다이렉트
@app.route('/')
def home():
    return redirect(url_for('reserve.index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
