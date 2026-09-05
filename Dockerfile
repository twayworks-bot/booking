# 1. Base Image 선택 (경량화된 Python 공식 이미지 사용)
FROM python:3.10-slim

# 2. 시스템 의존성 패키지 업데이트 및 환경변수 설정
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# 카카오톡 캘린더 연동을 위한 기본 ics calendar 엔드포인트 환경설정값 정의 (.env 대용 및 컨테이너 기동 시 오버라이드 가능)
ENV KAKAO_ICALENDAR=https://raw.githubusercontent.com/example/mock/main/calendar.ics

# 3. 컨테이너 내부 작업 디렉토리 설정
WORKDIR /app

# 4. 의존성 파일 복사 및 설치 (캐시 최적화)
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 5. 어플리케이션 소스 코드 전체 복사
COPY . /app/

# 6. 데이터베이스 영속성 저장을 위한 볼륨 정의
VOLUME ["/app/data"]

# 7. Gunicorn 실행을 위한 수신 포트 지정 (5000번)
EXPOSE 5000

# 7. 헬스체크 루틴 추가 (요청하신 조건 준수)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=5s \
    CMD python -c "import requests; requests.get('http://localhost:5000/reserve/api/status')"

# 8. 컨테이너 기동 시 실 구동 커맨드 설정 (요청하신 Gunicorn 커맨드 준수)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--log-level", "debug", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "app:app"]
