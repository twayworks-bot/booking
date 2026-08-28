from flask import Flask, render_template, request, redirect, url_for, flash, Blueprint
from flask_bcrypt import Bcrypt
from database import init_db, get_rooms, get_bookings, book_room, cancel_booking, get_recent_bookings, add_room, update_room, delete_room
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key'
bcrypt = Bcrypt(app)

# 데이터베이스 초기화
init_db()

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
    
    # 선택된 강단의 캘린더 채우기
    calendar = {}
    calendar[active_room_id] = {}
    for date in week_dates:
        date_str = date.strftime("%Y-%m-%d")
        calendar[active_room_id][date_str] = {}
        for slot in time_slots:
            calendar[active_room_id][date_str][slot] = None
            for booking in bookings:
                booking_date = datetime.strptime(booking['date'], "%Y-%m-%d").date()
                if (booking['room_id'] == active_room_id and 
                    booking_date == date.date() and 
                    booking['time_slot'] == slot):
                    calendar[active_room_id][date_str][slot] = booking
    
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
    return render_template('report.html', bookings=bookings, rooms=rooms)

@reserve_bp.route('/admin/rooms', methods=['GET', 'POST'])
def admin_rooms():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name')
            if name:
                add_room(name)
                flash(f'새로운 강단 "{name}"이(가) 추가되었습니다.', 'success')
            else:
                flash('강단 이름을 입력해주세요.', 'danger')
        elif action == 'update':
            room_id = int(request.form.get('room_id'))
            name = request.form.get('name')
            if name:
                update_room(room_id, name)
                flash(f'강단 이름이 "{name}"(으)로 수정되었습니다.', 'success')
            else:
                flash('강단 이름을 입력해주세요.', 'danger')
        elif action == 'delete':
            room_id = int(request.form.get('room_id'))
            delete_room(room_id)
            flash('강단 및 해당 강단의 모든 예약 정보가 삭제되었습니다.', 'success')
        return redirect(url_for('reserve.admin_rooms'))
    
    rooms = get_rooms()
    return render_template('admin_rooms.html', rooms=rooms)

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
