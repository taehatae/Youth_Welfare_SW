# 팀원 PC에서 자격 경로 진단과 역설계 실행하기

2026-11-16 기준: 정책 152개, 저장 조건 1,749개, 사람 검수 60개, 미검수 변환본 92개. 같은 코드·시드·입력값·기준 연도로 실행해야 결과를 비교할 수 있다. 검수 완료는 최종 행정 자격 승인을 뜻하지 않는다.

## 1. Git으로 전달되는 것

| 파일 | 용도 |
|---|---|
| `backend/data/welfare-policies.json` | 정책 원문과 기존 파싱 조건. 서비스 152개 / 조건 1,749개 |
| `backend/data/eligibility_paths.json` | DB 적재용 자격 경로 152개 |
| `backend/data/eligibility_paths_reviewed.json` | 사람 검수본 60개. 실행용 전체 시드는 위 파일 |
| `backend/data/structured_conditions.json` | 자격 경로가 적용되지 않는 경우의 구조화 조건 |
| `backend/scripts/policy_data.py` | 정책 원문·저장 조건 가져오기 |
| `backend/scripts/load_eligibility_paths.py` | 자격 경로 가져오기 |
| `backend/scripts/backup_database.py` | 기존 SQLite 백업·별도 복원 검증 |

SQLite DB, 백업, `.env`, `.tmp-*` 디렉터리는 공유하지 않는다. 팀원은 위 파일로 자신의 DB를 구성하며, 기존 `path_browser.db`를 전달받을 필요가 없다. 외부 복지 API·Ollama·API 키도 이 적재 과정에는 필요 없다.

**개인화 안내 코드는 별도 배포 조건이다.** 이 문서를 작성한 시점에는 `personalized_condition_guidance.py`, `PersonalizedGuideAccess.tsx` 등 최신 개인화 구현이 미추적이고, 관련 라우트·타입·클라이언트 수정도 미커밋이다. 현재 원격 Hwang의 `7d9afe9`만 머지하면 이 파일들은 전달되지 않는다. 후속 커밋과 dev 병합에 필요한 코드가 모두 포함됐는지 먼저 확인한다. 이 문서 작업에서는 커밋·푸시하지 않았다.

## 2. 기존 DB의 변경 범위와 주의사항

서버·동기화 작업을 중단하고 정확한 DB 경로를 확인한 뒤 적재한다. 기존 DB를 삭제하거나 다른 사람의 DB로 덮어쓰지 않는다.

| 작업 | 실제 동작 |
|---|---|
| `import app.main` | 설정된 DB가 없으면 생성하고, 없는 모델 테이블·인덱스를 `create_all()`로 생성. 기존 테이블을 ALTER하거나 초기화하지 않음 |
| 정책 import 미리보기 | 읽기 전용. DB 변경 없음 |
| 정책 import `--apply` | 백업 후 서비스 ID로 원문 갱신/추가, **입력 파일에 포함된 서비스의 저장 조건 교체**. 파일에 없는 서비스는 유지 |
| 자격 경로 적재 | 공유 시드 기준으로 경로 메타데이터·조건·checks·preferences 교체. **시드에 없는 기존 경로 정책은 삭제**, 경로/조건의 내부 숫자 ID는 바뀔 수 있음 |
| 기능 플래그 활성화 | DB 모델 변경 없음. 이후 진단에서 경로 판정 사용 |

정책 import와 경로 적재는 `users`, `user_eligibility_conditions`, `accounts`, `account_sessions`, `account_workspaces`, `auth_attempts`를 수정 대상으로 삼지 않는다. 기존 회원·프로필·진단 JSON은 유지된다. 로컬에서 별도로 작성한 경로는 공유 시드로 대체될 수 있으므로 백업이 필요하다.

`load_eligibility_paths.py`에는 미리보기·자동 백업 옵션이 없다. 정책 import와 경로 적재는 각각 별도 트랜잭션이며, 두 명령 전체가 하나의 트랜잭션은 아니다. 한 명령이라도 실패하면 서버를 시작하지 말고 원인을 확인한다. 오래된 DB의 컬럼 불일치는 `create_all()`이 고쳐 주지 않으므로 임의 초기화하지 않는다.

### 자동 적재에 의존하지 않는 이유

`USE_ELIGIBILITY_PATHS=true`이면 진단 시 경로 테이블 전체가 비어 있을 때 `load()`가 시드를 적재하고 커밋한다. 원문 서비스가 없는 DB라면 외래 키 오류가 날 수 있다. 일부 경로가 이미 있으면 자동 갱신하지도 않는다. 아래 순서로 명시적으로 준비한다.

```text
DB 경로·환경 설정 → 기존 DB 백업 → 테이블 생성
→ 정책 원문·저장 조건 적재 → 자격 경로 적재
→ 수량·원문 해시 확인 → 서버 실행 → 새 진단
```

## 3. dev 코드를 받은 뒤 백엔드 준비

Windows PowerShell, 저장소 루트에서 시작한다. 이미 dev 브랜치이며 작업 트리가 안전한 경우에만 `git pull --ff-only origin dev`로 갱신한다. 다른 브랜치의 작업은 기존 팀 통합 절차로 보존한다.

### 3.1 가상환경과 명시적 설정

```powershell
cd backend
if (-not (Test-Path .\.venv\Scripts\python.exe)) { py -3 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# 팀원 자신의 DB. 운영·개발 DB가 따로 있으면 먼저 의도한 경로로 바꾼다.
$policyDb = Join-Path (Get-Location).Path 'youth_welfare.db'
$env:DATABASE_URL = 'sqlite:///' + $policyDb.Replace('\', '/')
$env:USE_ELIGIBILITY_PATHS = 'true'
$env:USE_STRUCTURED_CONDITIONS = 'true'
$env:USE_LLM_JUDGE = 'false'
$env:FRONTEND_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173'

# 개인정보·API 키 대신 실제 SQLite 경로와 세 플래그만 확인한다.
.\.venv\Scripts\python.exe -B -c "from pathlib import Path; from sqlalchemy.engine import make_url; from app.core.config import settings as s; u=make_url(s.database_url); assert u.drivername.startswith('sqlite'); print('SQLite:', Path(u.database).resolve()); print('paths:',s.use_eligibility_paths,'structured:',s.use_structured_conditions,'llm:',s.use_llm_judge)"
if ($LASTEXITCODE -ne 0) { throw 'Configuration check failed.' }
```

위 `$env:` 값은 **현재 PowerShell과 그 자식 프로세스에만** 적용된다. 새 터미널에서는 다시 설정하거나 자신의 `backend/.env`에 같은 값을 기록한다. 프로세스 환경변수가 `.env`보다 우선하며, `.env`는 실행 작업 디렉터리에서 찾으므로 `backend/`에서 실행한다. 이미 실행 중인 서버는 설정 변경 후 재시작해야 한다.

- `USE_ELIGIBILITY_PATHS=true`: 경로 판정 활성화. 구조화 조건보다 우선한다.
- `USE_STRUCTURED_CONDITIONS=true`: 경로가 없거나 원문 해시가 다른 경우 구조화 조건으로 분석하는 설정. 경로 판정 자체의 필수 플래그는 아니지만 동일 환경 재현을 위해 함께 켠다.
- `USE_LLM_JUDGE=false`: LLM 경로는 먼저 실행되어 자격 경로 처리를 건너뛰므로 꺼 둔다.

### 3.2 기존 DB 백업과 테이블 생성

```powershell
New-Item -ItemType Directory -Force .\backups | Out-Null
$setupStamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
if (Test-Path -LiteralPath $policyDb) {
    .\.venv\Scripts\python.exe -B -m scripts.backup_database backup --source "$policyDb" --destination ".\backups\before-path-setup-$setupStamp.db"
    if ($LASTEXITCODE -ne 0) { throw 'Initial backup failed.' }
}

# 새 DB와 기존 DB 모두 현재 앱 모델에 필요한 없는 테이블만 준비한다.
.\.venv\Scripts\python.exe -B -c "import app.main"
if ($LASTEXITCODE -ne 0) { throw 'Table initialization failed.' }
```

백업은 새 대상 파일만 생성하며 기존 파일을 덮어쓰지 않는다. 백업에는 개인정보가 포함될 수 있으므로 Git에 추가하지 않는다. 별도 파일로 복원 검증하려면 다음 명령을 사용한다. **실제 DB에 복원하지 않는다.**

```powershell
# 기존 DB 백업을 생성한 경우에만 실행
.\.venv\Scripts\python.exe -B -m scripts.backup_database restore --source ".\backups\before-path-setup-$setupStamp.db" --destination ".\backups\restore-check-$setupStamp.db"
if ($LASTEXITCODE -ne 0) { throw 'Backup restore check failed.' }
```

### 3.3 정책 원문·기존 조건 적재

새 DB에서는 이 단계를 실행한다. 기존 DB의 서비스 ID 목록과 정책 원문이 현재 공유 시드와 같다고 이미 검증했다면, 불필요한 저장 조건 교체를 피하도록 이 단계를 생략하고 백업 후 3.4로 진행할 수 있다. **수량만 같다는 이유로 원문이 같다고 판단하지 않는다.** 원문 해시가 다르면 경로가 기존 분석으로 대체되므로 먼저 원문·시드 버전을 맞춘다.

```powershell
.\.venv\Scripts\python.exe -B -m scripts.policy_data inspect --source .\data\welfare-policies.json
if ($LASTEXITCODE -ne 0) { throw 'Policy snapshot validation failed.' }

# 미리보기: service_count=152, condition_count=1749 및 신규/갱신 수 확인
.\.venv\Scripts\python.exe -B -m scripts.policy_data import --database "$policyDb" --source .\data\welfare-policies.json
if ($LASTEXITCODE -ne 0) { throw 'Policy import preview failed.' }

# 실제 반영. 도구가 요구하는 별도 백업은 테이블 생성 이후·원문 갱신 이전 상태다.
.\.venv\Scripts\python.exe -B -m scripts.policy_data import --database "$policyDb" --source .\data\welfare-policies.json --apply --backup ".\backups\before-policy-import-$setupStamp.db"
if ($LASTEXITCODE -ne 0) { throw 'Policy import failed.' }
```

### 3.4 자격 경로 적재

```powershell
.\.venv\Scripts\python.exe -B -m scripts.load_eligibility_paths
if ($LASTEXITCODE -ne 0) { throw 'Eligibility path load failed.' }
```

`--database` 인자를 받는 정책 import와 달리, 경로 적재는 **`DATABASE_URL` 설정을 사용한다.** 위 명령들을 같은 PowerShell에서 실행해야 같은 DB를 사용한다. 정책 검수 담당자가 만든 시드를 그대로 적재하며, 실행 준비를 위해 `merge_reviewed.py`나 `build_eligibility_paths.py`를 다시 실행할 필요는 없다.

### 3.5 읽기 전용 확인

현재 수량은 다음과 같다. 향후 검수·정책 데이터가 갱신되면 같은 커밋의 시드와 비교한다.

| 항목 | 현재 기대값 |
|---|---:|
| `welfare_services` | 152 |
| `welfare_eligibility_conditions` | 1,749 |
| `policy_eligibility` | 152 |
| 사람 검수 (`drafted_by != converted`) | 60 |
| 미검수 변환본 (`drafted_by = converted`) | 92 |
| `eligibility_paths` (`_common` 포함) | 484 |
| `eligibility_path_conditions` | 407 |
| 원문 해시 불일치·원문 누락 | 0 |

시드의 `status=reviewed`는 **152개 모두**에 설정되어 있다. 이것만 세어 사람 검수 152개라고 판단하면 안 된다. 엔진은 152개를 읽고 응답의 `path_review`에서 `reviewed` 60개 / `converted` 92개로 구분한다. 결과 화면의 사람 검수 필터와 개인화 전용 API는 이 구분을 사용한다.

```powershell
@'
from contextlib import closing
from pathlib import Path
import hashlib
import sqlite3
from sqlalchemy.engine import make_url
from app.core.config import settings

url = make_url(settings.database_url)
assert url.drivername.startswith('sqlite')
database = Path(url.database).resolve(strict=True)
print('SQLite:', database)
with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
    for table in ('welfare_services', 'welfare_eligibility_conditions', 'policy_eligibility',
                  'eligibility_paths', 'eligibility_path_conditions'):
        print(table, db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0])
    for group, expression in (('human_reviewed', "drafted_by <> 'converted'"),
                              ('converted', "drafted_by = 'converted'")):
        print(group, db.execute("SELECT COUNT(*) FROM policy_eligibility WHERE status='reviewed' AND " + expression).fetchone()[0])
    mismatch = 0
    for expected, sid, target, selection in db.execute('SELECT p.source_sha256,s.serv_id,s.target_details,s.selection_criteria FROM policy_eligibility p LEFT JOIN welfare_services s USING(serv_id)'):
        source = '\n'.join(t for t in (target, selection) if t and t.strip())
        mismatch += sid is None or hashlib.sha256(source.encode()).hexdigest() != expected
    print('source_hash_mismatch_or_missing', mismatch)
    print('integrity_check', db.execute('PRAGMA integrity_check').fetchall())
    print('foreign_key_error_count', len(db.execute('PRAGMA foreign_key_check').fetchall()))
'@ | .\.venv\Scripts\python.exe -B -
if ($LASTEXITCODE -ne 0) { throw 'Read-only verification failed.' }
```

이 확인 코드는 기존 사용자 입력값을 조회하지 않는다. `integrity_check`는 `ok`, 외래 키 오류는 0인지 확인한다.

## 4. 서버 실행과 브라우저 확인

### 백엔드: 위와 같은 PowerShell

```powershell
.\.venv\Scripts\python.exe -B -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

`http://127.0.0.1:8000/docs` 또는 `/openapi.json`에서 `POST /api/v1/welfare/diagnose`와 `POST /api/v1/users/condition-guides/view`가 존재하는지 확인한다. 후자의 요청에 `username`·`password`가 필수라면 로그인 기반 최신 개인화 코드가 반영되지 않은 것이다.

### 프런트엔드: 별도 PowerShell, 저장소 루트에서 시작

```powershell
cd frontend
pnpm install
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000/api/v1'
pnpm dev
```

브라우저에서 `http://127.0.0.1:5173`을 연다. 프로세스 환경변수를 사용하지 않으면 `frontend/.env.example`을 참고해 `.env.local`의 API URL을 설정하고 Vite를 재시작한다. 다른 포트를 쓰면 API URL과 백엔드의 `FRONTEND_ORIGINS`도 맞춘다. 이전 `8001/5174`는 공유에 반드시 필요한 구성이 아니다.

1. 자신의 로컬 DB에 새 가상 계정을 만들고, 가상 프로필로 **새 진단**을 실행한다.
2. Network에서 진단과 개인화 안내가 모두 같은 `:8000/api/v1`을 사용하는지 확인한다.
3. 사람 검수 60개가 `path_review=reviewed`, 나머지 92개가 `converted`인지 확인한다.
4. 미충족 탭의 개인화 안내를 확인한다. 가상 예: 만 25세·남성이면 여성청소년 생리용품 지원의 연령/성별 안내, 본인 월소득 3,000,000원이면 두루누리 기준 2,699,999원과의 차액 300,001원을 확인한다.
5. 로그아웃하면 개인화 안내가 사라지고 전용 API는 401을 반환해야 한다. 다른 계정의 진단 식별자로도 조회할 수 없어야 한다.

기존 진단 스냅샷은 플래그나 시드를 바꿔도 자동으로 갱신되지 않는다. 기존 기록은 보존되며, 레거시 결과에 경로가 나중에 붙는 것은 아니다. `refresh`는 최신 현황 `current`를 갱신하고, 결과 화면이 사용하는 `diagnosis`는 새 진단에서 갱신한다. 이전 결과·변환본·원문/조건 불일치·지원하지 않는 복합 조건에서는 일반 안내가 유지될 수 있다.

## 5. 이 절차의 검증 범위

커밋된 HEAD의 `backend/`만 임시 디렉터리에 내보내고, 기존 DB·`.env`를 복사하지 않은 상태에서 위 초기화·원문 import·경로 load를 실행했다. 정책 152개 / 저장 조건 1,749개 / 사람 검수 60개 / 변환본 92개, 원문 해시 일치 152개, 무결성 `ok`, 외래 키 오류 0건을 확인했다. 합성 사용자 데이터 6개 테이블(회원·프로필·추가 정보·진단 스냅샷·세션·인증 시도)은 import와 경로 재적재 전후 동일했다.

이는 데이터 배포·적용 절차 검증이며, 전체 정책의 의미적 판정 정확도나 다른 PC의 의존성 설치까지 실기기로 검증한 것은 아니다. 개인화 기능을 사용하려면 해당 구현 코드도 dev에 포함되어야 한다.
