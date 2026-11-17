# 개발 이력 및 요구사항 요약 (Development History)

## [2026-11-17 23:30] `DEFAULT_PREFIX` 동적 Subpath 지원 및 Dockerfile 개선
- **요구사항 요약:**
  - 기존 `/reserve`로 고정되어 있던 기본 subpath(prefix)를 환경변수 `DEFAULT_PREFIX`를 통해 동적으로 지정 및 변경할 수 있도록 웹앱 코드 수정
  - `Dockerfile`에 `DEFAULT_PREFIX` 환경변수 설정, `DEFAULT_PREFIX` 연동 `HEALTHCHECK` 정의, Gunicorn 운영서버 기동 `CMD` (`main:app`) 반영
  - `notes/` 폴더 하위에 계획(`plan_YYYYMMDDHHmm.md`), 요구사항(`req_YYYYMMDDHHmm.md`, `requirement.md`), 이력(`history.md`), 결과(`result_YYYYMMDDHHmm.md`) 기록 체계 수립
  - `README.md`에 프로젝트 목적, 사용법, 기능 설명, 배포 방법, 구현 내용 및 실행 방법 업데이트
- **관련 문서:**
  - 계획서: `notes/plan_202611172330.md`
  - 요구사항 및 계획: `notes/req_202611172330.md`
  - 산출물 결과: `notes/result_202611172330.md`
