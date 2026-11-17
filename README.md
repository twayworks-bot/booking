# ⛪ 교회 강단 예약시스템 (Church Pulpit Booking System)

교회의 예배실 강단과 주요 성소를 투명하고 편리하게 예약하고 관리할 수 있도록 설계된 **Flask 기반의 예약 관리 웹 애플리케이션**입니다. 기존의 단순 회의실 예약 시스템에서 벗어나, 교회의 실무 환경과 성도들의 사용 흐름에 최적화된 구조로 전면 개발되었습니다.

---

## 📌 1. 서비스 목적 및 개요 (Overview)
본 시스템은 교회의 주일 예배 준비, 찬양팀/찬양대 연습, 구역 모임, 부서 수련회, 그리고 성도님들의 개인 기도를 조화롭게 연결하기 위해 제작되었습니다. 
* **동적 Subpath(Base URL) 지원 (`DEFAULT_PREFIX`):** 기본 경로 `/reserve`를 기본값(Default Prefix)으로 작동하며, 환경변수 `DEFAULT_PREFIX` 설정을 통해 배포 환경(리버스 프록시, 컨테이너 서브패스 등)의 요구에 따라 베이스 URL 경로를 자유롭게 변경할 수 있습니다. (루트 `/` 접속 시에도 설정된 `{DEFAULT_PREFIX}/` 경로로 자동 안전 리다이렉트 됩니다)
* **목표:** 복잡하고 헷갈리는 날짜 및 시간 선택 과정을 개선하여, 달력에서 원하는 시간 빈 칸을 **단 한 번 클릭하는 것만으로 모든 필수 정보가 연동되는 간편 예약(Click-to-Book)** 체계를 지원합니다.

---

## 🚀 2. 핵심 기능 및 구현 내용 (Core Features & Implementation)

### A. 🌐 환경변수 `DEFAULT_PREFIX` 기반 동적 Subpath 라우팅
* **기본 Subpath 설정:** 환경변수 `DEFAULT_PREFIX`가 지정되지 않은 경우 기본값 `/reserve`를 사용하여 기존의 모든 URL 체계를 그대로 유지합니다.
* **사용자 정의 Prefix 연동:** Docker 컨테이너 실행 시 `-e DEFAULT_PREFIX=/custom-path` 또는 `.env` 파일을 통해 값을 변경하면, Flask `Blueprint`(`reserve_bp`)의 `url_prefix`와 정적 파일 경로(`static_url_path`), 그리고 모든 내부 `url_for()` 링크가 해당 서브패스를 기준으로 자동 전환됩니다.
* **컨테이너 헬스체크 연동:** `{DEFAULT_PREFIX}/api/status` 엔드포인트를 통해 현재 설정된 Prefix 경로 하에서 컨테이너의 정상 작동 상태(`{"status": "healthy"}`)를 검증합니다.

### B. 📅 탭(Tab) 기반 주간 예약 달력 (UX 혁신)
* **예배실별 달력 탭 분리:** 기존에 한 화면에 여러 테이블이 수직으로 길게 나열되어 스크롤이 무한히 길어지던 현상을 해소했습니다. 강단별 상단 탭을 배치하여 성도들이 각 예배실 일정을 한눈에 비교하고 쉽게 찾아볼 수 있습니다.
* **원클릭 간편 예약 (Click-to-Book):** 달력의 빈 시간대에 표시되는 `[+ 예약 가능]` 버튼을 클릭하면, 해당 **강단명, 날짜, 시작 시간**이 입력 폼에 미리 채워진 상태로 연결됩니다.
* **상세 사용 목적(Purpose) 노출:** 예약 신청 시 단순 인적사항 외에도 구체적인 목적(예: *성가대 찬양 연습, 부서 여름 수련회 등*)을 기입하게 강제하여 공간 사용의 정당성과 배려 문화를 정착시킵니다.

### C. ⚙️ 동적 강단 관리 기능 (Admin Room CRUD)
* **강단 동적 관리:** 관리 콘솔(`{DEFAULT_PREFIX}/admin/rooms`)을 제공하여 새로운 공간(예: 세미나실, 유아실 등)을 유연하게 추가, 이름 변경, 안전 삭제할 수 있습니다.
* **기본 지정 강단:** 최초 데이터베이스 셋업 시 교회의 핵심 성소 세 곳이 기본 생성됩니다.
  1. `대강당(비젼홀)`
  2. `지하강당(드림홀)`
  3. `별관(미션홀)`
* **연쇄 데이터 보호 (Cascade Delete):** 강단이 삭제되는 경우 데이터 무결성을 위해 관련된 모든 기존 예약 데이터 역시 데이터베이스에서 동시 파기되도록 안전하게 보호 장치를 설계하였습니다.

### D. 📊 최근 예약 리포트 및 보안 취소 기능
* **최근 3개월 리포트 (`{DEFAULT_PREFIX}/report`):** 오늘 자정 이후의 유효한 예약 일정을 통합하여 데스크톱 테이블 뷰 및 모바일 반응형 카드 뷰로 보기 쉽게 정리합니다.
* **비밀번호 기반 취소 처리:** 본인의 예약에 직접 부여한 비밀번호를 Bcrypt 해시로 검증하여 타인의 실수나 임의 변경으로 인한 혼선을 완벽하게 예방합니다.

### E. 💬 카카오톡 캘린더 연동 및 실시간 스마트 캐싱 (External Sync)
* **환경변수 및 DB 유기적 연동**: `.env`에 등록된 `KAKAO_ICALENDAR`를 기본값으로 삼되, 관리자가 직접 콘솔에서 지정한 URL이 있을 경우 데이터베이스에 저장해 우선순위로 작동합니다.
* **1분 쿨타임 스마트 캐싱**: 무분별한 외부 API 호출을 억제하기 위해 최소 1분 간격의 타임아웃 캐싱 규칙을 가동하여 로컬 캐시 데이터(`ics_cache_data`)를 스마트하게 제어합니다.
* **반복 일정(RRULE/EXDATE) 및 동적 접두사(Prefix) 정규화 매핑**:
  - 카카오톡 ICS의 반복 일정(`RRULE`, `EXDATE`)을 한국 표준시(KST) 기준으로 전개하여 누락 없이 반영합니다.
  - 일정 제목의 시작 단어(예: `"비젼홀)"`, `"드림홀)"`, `"별관5층)"` 등)를 포착해 정확한 예약 슬롯으로 자동 오버레이(Overlay) 렌더링합니다.
  - 전각 괄호(`）`), 대괄호(`]`), 공백 유무에 상관없이 매핑을 유연하게 매칭시키는 정규화 처리가 기본 탑재되어 있습니다.
  - **시작단어 동적 콘솔 관리**: 관리자 화면에서 강단별로 `ics_prefix` 컬럼을 통해 시작 단어들을 실시간 추가/수정(콤마 `,` 구분)할 수 있으며, 비어있을 때는 상시 기본값으로 자동 보완됩니다.
* **예약 리포트 연동 (오늘 자정 이후 기준)**: 통합 예약 리포트에 오늘을 포함한 미래의 카카오톡 연동 예약 일정이 오름차순으로 병합 및 노출되며, 시각적 구분을 돕는 전용 배지가 부착됩니다.

### F. 🔐 공통 인증 서비스 연동 및 관리자 권한 제어 (Auth Integration & Access Control)
* **공통 로그인 세션 검증:** 동일한 도메인(`holyseeds.thewayworks.net`)을 공유하는 공통 인증 서비스(`/auth`)의 로그인 세션 쿠키(`auth_session`)를 실시간 분석 및 검증합니다.
* **통합 관리자 권한 제어 (Role-Based Access Control):** 
  - 세션 쿠키를 기반으로 백엔드에서 원격 인증 연동 API(`/auth/api/verify-session`)를 호출하여 해당 유저의 관리자 권한(`is_manager` 속성)을 검증합니다.
  - 비인가 사용자가 관리자 전용 페이지(`{DEFAULT_PREFIX}/admin/rooms`)에 접근할 경우, 차단 후 로그인 화면으로 리다이렉션하며 로그인 완료 시 원래 요청한 경로로 자동 복귀합니다.

---

## 🛠️ 3. 기술 스택 및 아키텍처 (Tech Stack)
* **Backend:** Python 3.10+, Flask (`Blueprint` 동적 `url_prefix` 라우팅), Gunicorn (WSGI 운영 서버, `main:app` 진입점)
* **Database:** SQLite3 (`/app/data/room_bookings.db` 영속성 볼륨 저장)
* **Security:** Flask-Bcrypt (비밀번호 단방향 암호화 해싱), 외부 SSO 세션 검증 연동
* **Frontend:** HTML5, CSS3 (Custom `style.css`), Bootstrap 5, Bootstrap Icons (CDN)
* **Testing:** Python `unittest` (`test_app.py`)

---

## 🗃️ 4. 데이터베이스 테이블 구조 (Database Schema)

### `rooms` 테이블 (예배실/강단 정보)
| 컬럼명 | 데이터 타입 | 제약 조건 | 설명 |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | 강단 고유 식별 번호 |
| `name` | TEXT | NOT NULL | 예배실 및 강단 명칭 |
| `ics_prefix` | TEXT | NULL | 해당 강단의 카카오톡 일정 매칭용 시작단어 목록 (콤마 `,` 구분) |

### `bookings` 테이블 (예약 내역 정보)
| 컬럼명 | 데이터 타입 | 제약 조건 | 설명 |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | 예약 고유 식별 번호 |
| `room_id` | INTEGER | FOREIGN KEY REFERENCES rooms(id) | 예약된 강단 ID |
| `date` | TEXT | NOT NULL (YYYY-MM-DD) | 사용 일자 |
| `time_slot` | TEXT | NOT NULL (HH:MM) | 30분 단위 시간 슬롯 |
| `user_name` | TEXT | NOT NULL | 예약자 이름 혹은 단체명 |
| `password_hash`| TEXT | NOT NULL | 취소용 단방향 암호화 비밀번호 해시 |
| `group_id` | TEXT | NOT NULL (UUIDv4) | 연속 예약 묶음을 나타내는 그룹 ID |
| `purpose` | TEXT | DEFAULT '연습 및 사용' | 구체적인 예약 목적/용도 |

### `settings` 테이블 (환경설정 및 동기화 캐시)
| 컬럼명 | 데이터 타입 | 제약 조건 | 설명 |
|---|---|---|---|
| `key` | TEXT | PRIMARY KEY | 설정 고유 키 (예: `kakao_icalendar`, `ics_cache_data`, `last_ics_fetch_time`) |
| `value` | TEXT | NULL | 해당 키의 설정값 혹은 직렬화된 JSON 캐시 데이터 |

---

## 🏃 5. 설치, 실행 및 배포 방법 (How to Run & Deploy)

### 1) 로컬 환경 실행 방법

#### 필수 요구사항 및 패키지 설치
Python 3.8 이상이 설치되어 있어야 하며, `requirements.txt`를 통해 의존성 패키지를 설치합니다.
```bash
pip install -r requirements.txt
```

#### 환경변수 설정 (`.env` 또는 시스템 환경변수)
프로젝트 루트의 `.env` 파일에 기본 환경변수를 설정할 수 있습니다.
```env
DEFAULT_PREFIX=/reserve
KAKAO_ICALENDAR=https://calendar-ics.kakao.com/.../talk.ics
```

#### 애플리케이션 기동
* **개발 서버 실행:**
  ```bash
  python app.py
  # 또는
  python main.py
  ```
* **Gunicorn 운영 서버 실행 (Linux/Container 환경):**
  ```bash
  gunicorn --bind 0.0.0.0:5000 --workers 2 --log-level debug --access-logfile - --error-logfile - --capture-output main:app
  ```
서버가 실행되면 웹 브라우저에서 `http://127.0.0.1:5000/` 접속 시 자동으로 `http://127.0.0.1:5000/reserve/` (또는 지정한 `DEFAULT_PREFIX`)로 리다이렉트되어 메인 화면이 표시됩니다.

---

### 2) 🐳 Docker 컨테이너 빌드 및 배포 방법

#### Dockerfile 주요 구성 사양
* **기본 환경변수:** `ENV DEFAULT_PREFIX=/reserve` (컨테이너 기동 시 `-e DEFAULT_PREFIX=...`로 변경 가능)
* **헬스체크 (Prefix 자동 연동):**
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=5s \
      CMD python -c "import os, requests; prefix = os.getenv('DEFAULT_PREFIX', ''); requests.get(f'http://localhost:5000{prefix}/api/status')"
  ```
* **운영 서버 기동 CMD:**
  ```dockerfile
  CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--log-level", "debug", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "main:app"]
  ```

#### ① 도커 이미지 빌드
```bash
docker build -t church-reserve .
```

#### ② 기본 Prefix(`/reserve`)로 컨테이너 실행 (데이터 볼륨 영속성 연결)
* **Linux / macOS:**
  ```bash
  docker run -d -p 5000:5000 \
    -v $(pwd)/data:/app/data \
    --name church-booking-app \
    church-reserve
  ```
* **Windows (PowerShell):**
  ```powershell
  docker run -d -p 5000:5000 `
    -v ${PWD}/data:/app/data `
    --name church-booking-app `
    church-reserve
  ```

#### ③ 사용자 정의 `DEFAULT_PREFIX`를 지정하여 컨테이너 실행
다른 서브패스(예: `/booking`)로 웹앱을 서비스하려는 경우 `-e DEFAULT_PREFIX=/booking` 옵션을 부여합니다. 웹앱의 모든 라우팅과 컨테이너 헬스체크가 자동으로 `/booking` 하위로 연동됩니다.
```bash
docker run -d -p 5000:5000 \
  -e DEFAULT_PREFIX=/booking \
  -v $(pwd)/data:/app/data \
  --name church-booking-app \
  church-reserve
```

---

## 📖 6. 사용자 설명서 (User Guide)

### 1) 강단 예약 현황 확인하기 (메인 화면)
* 메인 홈(`{DEFAULT_PREFIX}/`)에 접속하면 금주 주간 날짜에 따른 30분 단위 시간표가 표시됩니다.
* 상단 **강단별 탭(Tab)**(`대강당(비젼홀)`, `지하강당(드림홀)`, `별관(미션홀)`)을 클릭하여 원하는 예배실 강단으로 즉각 전환하여 예약표를 조회할 수 있습니다.
* 왼쪽의 `이전 주`, `오늘이 속한 주`, `다음 주` 버튼을 활용해 날짜 범위를 이동할 수 있습니다.

### 2) 간편 예약하기 (원클릭 예약)
* 달력에서 원하시는 요일과 시간대의 **`[+ 예약 가능]`** 버튼을 클릭합니다.
* 자동으로 예배실 정보, 일자, 시작 시간이 채워진 상태로 **예약 신청서**가 열립니다.
* 예약 성도명/단체명을 입력하고, **예약 목적**을 미리 정의된 셀렉트 박스(예: *찬양대 연습, 수요 기도회 등*)에서 고르거나 직접 기입합니다.
* 예약 취소 시에 필요한 본인인증용 **비밀번호**를 설정하고 신청하기를 누릅니다.

### 3) 예약 취소하기
* 달력에 등록된 본인의 예약 카드 우측 하단에 있는 **`[취소]`** 버튼을 누릅니다.
* 예약 시 직접 설정했던 **비밀번호**를 입력하고 확인을 누르면 해당 시간대에 묶여있는 연속 예약 전체가 일괄적으로 즉시 취소됩니다.

### 4) 신규 강단 추가 및 카카오톡 연동 관리 (관리자 기능)
* 상단 메뉴 우측 끝의 **`⚙️ 강단 관리`** 메뉴를 누릅니다.
* 왼쪽의 **새 강단 등록** 카드에 신규 추가를 원하는 예배실 이름과 카카오톡 연동 시작단어를 입력하고 등록하면 즉시 상단 탭에 동적으로 생성됩니다.
* 목록 우측의 **[수정]** 버튼을 통해 실시간으로 명칭과 연동 시작단어를 정정하거나, **[삭제]** 버튼을 눌러 해당 강단과 관련된 예약 전체를 일괄 삭제할 수 있습니다.

---

## 🧪 7. 통합 기능 테스트 방법 (Testing)
시스템 로직의 무결성을 검증하고 코드 변경 시 오류를 차단하기 위한 자동화 유닛 테스트 케이스(`test_app.py`)가 탑재되어 있습니다.

```bash
python -m unittest test_app.py -v
```
라우팅 리다이렉트, `DEFAULT_PREFIX` 동적 서브패스 변경, 탭 전환 연동성, 폼 프리셋 바인딩, 관리자 CRUD, 카카오톡 ICS 파싱/반복일정/캐싱, 헬스체크 API 등 전체 핵심 기능을 검증합니다.
