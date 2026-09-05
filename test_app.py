import unittest
from app import app
from database import init_db, get_rooms, get_bookings, add_room, delete_room

class ChurchBookingSystemTests(unittest.TestCase):
    def setUp(self):
        # 테스트 전용 데이터베이스 및 앱 테스트 클라이언트 설정
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        init_db(force_reinit=True) # 매번 테스트 실행 시 테스트 환경 초기화

        # Mock check_auth_session to return admin session by default in tests
        from unittest.mock import patch
        self.auth_patcher = patch('app.check_auth_session')
        self.mock_auth = self.auth_patcher.start()
        self.mock_auth.return_value = (True, True, {'id': 'admin-test-id', 'username': 'admin-test', 'name': 'Admin Test'})

    def tearDown(self):
        self.auth_patcher.stop()

    def test_root_redirect(self):
        """기본 경로 접속 시 /reserve/로 리다이렉션 되는지 검증"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/reserve/'))

    def test_reserve_index_loads(self):
        """메인 예약 달력 화면이 정상 로드되는지 검증"""
        response = self.client.get('/reserve/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('교회 강단 예약시스템', response.data.decode('utf-8'))
        self.assertIn('대강당(비젼홀)', response.data.decode('utf-8'))

    def test_reserve_book_loads_and_presets(self):
        """예약 신청서 로딩 및 쿼리 파라미터 프리셋 바인딩 검증"""
        import datetime
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        response = self.client.get(f'/reserve/book?room_id=1&date={today_str}&start_time=10:00')
        self.assertEqual(response.status_code, 200)
        content = response.data.decode('utf-8')
        self.assertIn('예약 신청서', content)
        self.assertIn(f'value="{today_str}"', content)

    def test_reserve_report_loads(self):
        """예약 리포트 페이지가 정상 로드되는지 검증"""
        response = self.client.get('/reserve/report')
        self.assertEqual(response.status_code, 200)
        self.assertIn('최근 3개월 예약 리포트', response.data.decode('utf-8'))

    def test_admin_rooms_crud(self):
        """강단 관리 CRUD 동작 여부 검증"""
        # 1. 초기 강단 목록 조회
        rooms = get_rooms()
        self.assertEqual(len(rooms), 3)

        # 2. 새로운 강단 등록 (POST /reserve/admin/rooms)
        response = self.client.post('/reserve/admin/rooms', data={
            'action': 'add',
            'name': '유아실 강단'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('유아실 강단', response.data.decode('utf-8'))

        # 3. 강단 이름 수정
        rooms = get_rooms()
        new_room_id = [r['id'] for r in rooms if r['name'] == '유아실 강단'][0]
        response = self.client.post('/reserve/admin/rooms', data={
            'action': 'update',
            'room_id': new_room_id,
            'name': '유치부실 강단'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('유치부실 강단', response.data.decode('utf-8'))

        # 4. 강단 삭제
        response = self.client.post('/reserve/admin/rooms', data={
            'action': 'delete',
            'room_id': new_room_id
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('유치부실 강단', response.data.decode('utf-8'))

    def test_room_booking_flow(self):
        """강단 예약 생성 및 확인, 취소 전 과정 테스트"""
        import datetime
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        # 1. 예약하기 시뮬레이션
        response = self.client.post('/reserve/book', data={
            'room_id': 1,
            'date': today_str,
            'start_time': '09:00',
            'end_time': '10:00',
            'user_name': '테스트 성도',
            'password': 'testpassword',
            'purpose': '성가대 연습'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('예약이 완료되었습니다!', response.data.decode('utf-8'))

        # 2. 리포트에 반영되었는지 확인
        response = self.client.get('/reserve/report')
        self.assertIn('테스트 성도', response.data.decode('utf-8'))
        self.assertIn('성가대 연습', response.data.decode('utf-8'))

    def test_health_check(self):
        """도커 헬스체크 API 엔드포인트가 정상 작동하는지 검증"""
        response = self.client.get('/planning/api/status')
        self.assertEqual(response.status_code, 200)
        self.assertIn('healthy', response.data.decode('utf-8'))

    def test_kakao_icalendar_settings_and_fallback(self):
        """카카오톡 캘린더 URL 설정 및 환경변수 Fallback 동작 검증"""
        import os
        from app import get_kakao_icalendar_url
        from database import set_setting

        # 1. 환경변수만 설정되어 있을 때 환경변수 값을 리턴하는지 검증
        os.environ['KAKAO_ICALENDAR'] = 'https://example.com/env_fallback.ics'
        set_setting('kakao_icalendar', '') # DB 초기화
        self.assertEqual(get_kakao_icalendar_url(), 'https://example.com/env_fallback.ics')

        # 2. DB에 값이 저장되었을 때 환경변수를 덮어쓰고 DB 값을 우선 반환하는지 검증
        set_setting('kakao_icalendar', 'https://example.com/db_override.ics')
        self.assertEqual(get_kakao_icalendar_url(), 'https://example.com/db_override.ics')

        # Clean up
        set_setting('kakao_icalendar', '')

    def test_ics_parser_and_mapping(self):
        """ICS 달력 파싱, 접두사 기반 강단 매핑 및 30분 슬롯 분할 검증"""
        from app import parse_ics, get_room_id_by_prefix, get_event_slots
        from database import get_rooms
        import datetime

        rooms = get_rooms()

        # Mock ICS 데이터
        mock_ics = (
            "BEGIN:VCALENDAR\n"
            "BEGIN:VEVENT\n"
            "SUMMARY:비젼홀) 성가대 연습\n"
            "DTSTART;TZID=Asia/Seoul:20260905T090000\n"
            "DTEND;TZID=Asia/Seoul:20260905T100000\n"
            "END:VEVENT\n"
            "BEGIN:VEVENT\n"
            "SUMMARY:드림홀) 금요기도회\n"
            "DTSTART;VALUE=DATE:20260905\n"
            "DTEND;VALUE=DATE:20260906\n"
            "END:VEVENT\n"
            "END:VCALENDAR"
        )

        # 1. ICS 파싱 검증
        events = parse_ics(mock_ics)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]['SUMMARY'], '비젼홀) 성가대 연습')
        self.assertEqual(events[1]['SUMMARY'], '드림홀) 금요기도회')

        # 2. 접두사 기반 강단 ID 조회 검증
        room_id_1 = get_room_id_by_prefix('비젼홀) 성가대 연습', rooms)
        room_id_2 = get_room_id_by_prefix('드림홀) 금요기도회', rooms)
        room_id_3 = get_room_id_by_prefix('별관5층) 청년부 예배', rooms)
        room_id_none = get_room_id_by_prefix('일반회의', rooms)

        self.assertIsNotNone(room_id_1)
        self.assertIsNotNone(room_id_2)
        self.assertIsNotNone(room_id_3)
        self.assertIsNone(room_id_none)

        # 3. 슬롯 생성 검증 (09:00 ~ 10:00 이벤트는 09:00, 09:30, 10:00 포함)
        start_dt = datetime.datetime(2026, 9, 5, 9, 0)
        end_dt = datetime.datetime(2026, 9, 5, 10, 0)
        slots = get_event_slots(start_dt, end_dt)
        expected_slots = [('2026-09-05', '09:00'), ('2026-09-05', '09:30'), ('2026-09-05', '10:00')]
        self.assertEqual(slots, expected_slots)

    def test_ics_caching_and_rate_limiting(self):
        """ICS 페칭 1분 레이트 리미트 및 캐시 보존 검증"""
        from unittest.mock import patch, MagicMock
        from app import get_overlay_bookings, set_setting

        # 기존 설정 및 캐시 초기화
        set_setting('last_ics_fetch_time', '')
        set_setting('ics_cache_data', '[]')
        set_setting('kakao_icalendar', 'https://example.com/test.ics')

        # Mocking requests.get
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = (
            "BEGIN:VCALENDAR\n"
            "BEGIN:VEVENT\n"
            "SUMMARY:비젼홀) 주일오전예배\n"
            "DTSTART;TZID=Asia/Seoul:20260905T090000\n"
            "DTEND;TZID=Asia/Seoul:20260905T100000\n"
            "END:VEVENT\n"
            "END:VCALENDAR"
        )

        with patch('requests.get', return_value=mock_response) as mock_get:
            # 1. 첫 페치 시 requests.get 이 정상 실행되는지 확인
            bookings = get_overlay_bookings()
            self.assertTrue(mock_get.called)
            self.assertEqual(len(bookings), 3) # 09:00, 09:30, 10:00 세 슬롯

            # Mock 실행 횟수 초기화
            mock_get.reset_mock()

            # 2. 1분 이내 두 번째 호출 시 requests.get 을 중복 호출하지 않고 캐시 반환 검증 (Rate-limited)
            bookings_2 = get_overlay_bookings()
            mock_get.assert_not_called()
            self.assertEqual(len(bookings_2), 3)

        # Clean up
        set_setting('kakao_icalendar', '')
        set_setting('last_ics_fetch_time', '')
        set_setting('ics_cache_data', '[]')

    def test_report_includes_overlay_bookings(self):
        """예약 리포트에 카카오톡 연동 예약이 오늘 날짜 이후 기준으로 포함되어 출력되는지 검증"""
        from unittest.mock import patch, MagicMock
        from app import set_setting
        import datetime

        # 오늘 날짜와 내일 날짜, 어제 날짜 계산
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        tomorrow_str = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        yesterday_str = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')

        # Mock ICS 데이터 설정 (과거, 미래의 이벤트 구성)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = f"""BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:비젼홀) 내일 연습
DTSTART;TZID=Asia/Seoul:{tomorrow_str.replace('-', '')}T100000
DTEND;TZID=Asia/Seoul:{tomorrow_str.replace('-', '')}T110000
END:VEVENT
BEGIN:VEVENT
SUMMARY:드림홀) 과거 연습
DTSTART;TZID=Asia/Seoul:{yesterday_str.replace('-', '')}T100000
DTEND;TZID=Asia/Seoul:{yesterday_str.replace('-', '')}T110000
END:VEVENT
END:VCALENDAR"""

        set_setting('last_ics_fetch_time', '')
        set_setting('ics_cache_data', '[]')
        set_setting('kakao_icalendar', 'https://example.com/report_test.ics')

        with patch('requests.get', return_value=mock_response):
            response = self.client.get('/reserve/report')
            self.assertEqual(response.status_code, 200)
            content = response.data.decode('utf-8')
            
            # 1. 오늘 이후 일정("내일 연습")은 리포트에 나타나야 함
            self.assertIn('내일 연습', content)
            self.assertIn('카카오톡', content)
            self.assertIn('연동 예약', content)
            
            # 2. 오늘 이전 일정("과거 연습")은 노출되지 않아야 함
            self.assertNotIn('과거 연습', content)

        # Clean up
        set_setting('kakao_icalendar', '')
        set_setting('last_ics_fetch_time', '')
        set_setting('ics_cache_data', '[]')

    def test_dynamic_ics_prefixes(self):
        """강단별 시작단어(ics_prefix) 동적 등록 및 기본값 결합 검증"""
        from database import add_room, get_rooms
        from app import get_room_prefixes, get_room_id_by_prefix

        # 1. 신규 강단 추가 (Prefix 없음)
        add_room('새로운 예배실', None)
        rooms = get_rooms()
        new_room = [r for r in rooms if r['name'] == '새로운 예배실'][0]

        # 2. prefix 컬럼이 비어있으면 강단명(새로운 예배실)을 기본 단어로 리턴하는지 검증
        prefixes = get_room_prefixes(new_room)
        self.assertIn('새로운 예배실', prefixes)

        # 3. 사용자 정의 시작단어 등록 검사 (콤마 구분)
        new_room['ics_prefix'] = '자자, 우야'
        prefixes_custom = get_room_prefixes(new_room)
        self.assertEqual(prefixes_custom, ['자자', '우야'])

        # 4. 동적 시작단어 기반의 매핑 검증
        room_id = get_room_id_by_prefix('자자) 특별 집회', rooms=[new_room])
        self.assertEqual(room_id, new_room['id'])

        room_id_none = get_room_id_by_prefix('일반집회) 특별 집회', rooms=[new_room])
        self.assertIsNone(room_id_none)

    def test_report_filters_out_past_db_bookings(self):
        """예약 리포트 페이지에서 오늘 자정 이전의 과거 일반 예약 데이터가 제외되는지 검증"""
        import datetime
        from database import book_room
        
        # 오늘 날짜와 어제 날짜 계산
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        yesterday_str = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        
        # 1. 오늘 날짜로 예약 등록
        book_room(room_id=1, date=today_str, time_slot='09:00', user_name='오늘 예약자', password='pwd', group_id='grp1', purpose='오늘목적')
        # 2. 어제 날짜로 예약 등록
        book_room(room_id=1, date=yesterday_str, time_slot='10:00', user_name='과거 예약자', password='pwd', group_id='grp2', purpose='과거목적')
        
        response = self.client.get('/reserve/report')
        self.assertEqual(response.status_code, 200)
        content = response.data.decode('utf-8')
        
        # 오늘 예약자는 리포트에 출력되어야 함
        self.assertIn('오늘 예약자', content)
        # 과거 예약자는 리포트에서 필터링되어 출력되지 않아야 함
        self.assertNotIn('과거 예약자', content)

if __name__ == '__main__':
    unittest.main()
