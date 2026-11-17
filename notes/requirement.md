# 누적 요구사항 기록 (Cumulative Requirements)

## [2026-11-17 23:30] 환경변수 `DEFAULT_PREFIX` 동적 Subpath 지원, Dockerfile 개선 및 문서화 규칙 적용

### 원본 요구사항
- 현 프로젝트는 강단의 사용에 대한 booking-예약시간을 등록하고 관리하는 웹앱이며, 기본 subpath `"/reserve"`를 기본값 prefix로 지정하여 개발되어 있음.
- Docker에서 환경변수 `DEFAULT_PREFIX`를 지정할 때 이 환경변수 값을 subpath로 지정하여 사용자의 요청에 따라 변경이 되도록 수정.
- `Dockerfile` 생성 시 다음 내용을 반영:
  - Docker 컨테이너의 `DEFAULT_PREFIX` 환경세팅 값을 두어 앱의 기본 PREFIX값을 지정하고, 웹앱의 prefix 값은 `DEFAULT_PREFIX`를 참조하여 기본 base URL로 작동.
  - 컨테이너 헬스체크 정의 (Prefix 경로 연동):
    ```dockerfile
    HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=5s \
        CMD python -c "import os, requests; prefix = os.getenv('DEFAULT_PREFIX', ''); requests.get(f'http://localhost:5000{prefix}/api/status')"
    ```
  - 시작 CMD 반영 (Gunicorn 운영서버 기동):
    ```dockerfile
    CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--log-level", "debug", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "main:app"]
    ```
- 기록 관리 규칙:
  - 요구사항 지시 시 첫째 계획을 수립하여 `notes/plan_YYYYMMDDHHmm.md`에 기록
  - 매번 개발 요구사항과 요약은 `notes/history.md`에 기록
  - 사용자 원본 요구사항과 계획 기록은 `notes/req_YYYYMMDDHHmm.md`에 기록
  - 산출물 생성 기록은 `notes/result_YYYYMMDDHHmm.md`에 기록
  - 모든 요구 사항은 누적하여 `notes/requirement.md`에 기록
- `README.md` 업데이트:
  - 프로젝트의 목적과 사용법, 기능설명을 `README.md`에 수정하여 기록
  - 웹앱의 배포방법과 구현 내용과 실행방법도 동일하게 `README.md`에 기록 유지 및 업데이트
