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
        response = self.client.get('/reserve/book?room_id=1&date=2026-08-27&start_time=10:00')
        self.assertEqual(response.status_code, 200)
        content = response.data.decode('utf-8')
        self.assertIn('예약 신청서', content)
        self.assertIn('value="2026-08-27"', content)

    def test_reserve_report_loads(self):
        """예약 리포트 페이지가 정상 로드되는지 검증"""
        response = self.client.get('/reserve/report')
        self.assertEqual(response.status_code, 200)
        self.assertIn('최근 1개월 예약 리포트', response.data.decode('utf-8'))

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
        # 1. 예약하기 시뮬레이션
        response = self.client.post('/reserve/book', data={
            'room_id': 1,
            'date': '2026-08-27',
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

if __name__ == '__main__':
    unittest.main()
