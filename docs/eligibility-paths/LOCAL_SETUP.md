# 팀원 PC에서 자격 경로 진단과 역설계 실행하기

2026-11-20 기준으로 원문 정책 152개, 기존 파싱 조건 1,749개, 사람 검수 152개, 자동 변환본 0개다. 신청 경로는 420개이며, 공유 SQLite에는 공통 경로를 포함해 572행과 비교 조건 533개가 있다. 같은 코드·시드·입력값·기준 연도로 실행해야 결과를 비교할 수 있다. 실제 신청 자격은 공식 공고와 담당 기관에서 확인한다.

## 1. Git으로 전달되는 것

| 파일 | 용도 |
|---|---|
| `backend/youth_welfare.db` | Git LFS로 공유하는 정책 적재 초기본. 원문·기존 파싱 조건·자격 경로가 적재되어 있으며 회원·프로필·진단 기록은 비어 있음 |
| `backend/data/welfare-policies.json` | 정책 원문과 기존 파싱 조건. 서비스 152개 / 조건 1,749개 |
| `backend/data/eligibility_paths.json` | DB 적재용 자격 경로 152개 |
| `backend/data/eligibility_paths_reviewed.json` | 사람 검수본 152개. 실행용 전체 시드는 위 파일 |
| `backend/data/structured_conditions.json` | 자격 경로가 적용되지 않는 경우의 구조화 조건 |
| `backend/scripts/policy_data.py` | 정책 원문·저장 조건 가져오기 |
| `backend/scripts/load_eligibility_paths.py` | 자격 경로 가져오기 |
| `backend/scripts/backup_database.py` | 기존 SQLite 백업·별도 복원 검증 |

Git LFS가 내려받은 실제 SQLite 파일을 사용한다. 공유 초기본에는 테스트 계정이나 진단을 저장하지 않는다. 팀원별 실행 DB, 백업, `.env`, `.tmp-*` 디렉터리는 공유하지 않는다. 공유 초기본 또는 JSON 시드를 사용해 각자 실행용 DB를 준비할 수 있다.

PR #23이 반영된 코드는 로그인 전용 맞춤 안내·난이도 API를 제공한다. `evaluation_context`로 진단 당시와 현재 정책 조건의 동일성을 확인할 수 없는 경우 개인화 값은 생략한다.

## 2. 일반 개발 실행 준비

Windows PowerShell에서 저장소 루트를 기준으로 시작한다.

```powershell
cd backend
if (-not (Test-Path .\.venv\Scripts\python.exe)) { py -3 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
```

이미 준비한 로컬 DB가 있다면 아래 `$policyDb`에 그 경로를 지정하고 적용된 데이터를 [읽기 전용으로 확인](#4-읽기-전용-확인)한다. 공유 초기본에는 정책과 경로가 모두 적재되어 있으므로, 최초 로컬 실행용 파일이 필요할 때는 SQLite 백업 명령으로 별도 경로에 복사한다. 외부 복지 API·Ollama·API 키는 필요 없다.

```powershell
# 처음 실행용 복사본을 준비할 때만 실행한다.
New-Item -ItemType Directory -Force .\.tmp-local-paths | Out-Null
if (-not (Test-Path -LiteralPath .\.tmp-local-paths\youth_welfare.db)) {
    .\.venv\Scripts\python.exe -B -m scripts.backup_database backup --source .\youth_welfare.db --destination .\.tmp-local-paths\youth_welfare.db
    if ($LASTEXITCODE -ne 0) { throw 'Local database copy failed.' }
}
```

```powershell
$policyDb = (Resolve-Path -LiteralPath .\.tmp-local-paths\youth_welfare.db -ErrorAction Stop).Path
if ($policyDb -eq (Join-Path (Get-Location).Path 'youth_welfare.db')) { throw 'Use a separate local database.' }
$env:DATABASE_URL = 'sqlite:///' + $policyDb.Replace('\', '/')
$env:USE_ELIGIBILITY_PATHS = 'true'
$env:USE_STRUCTURED_CONDITIONS = 'true'
$env:USE_LLM_JUDGE = 'false'
$env:FRONTEND_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173'

# 실제 SQLite 경로와 세 플래그만 확인한다.
.\.venv\Scripts\python.exe -B -c "from pathlib import Path; from sqlalchemy.engine import make_url; from app.core.config import settings as s; u=make_url(s.database_url); assert u.drivername.startswith('sqlite'); print('SQLite:', Path(u.database).resolve()); print('paths:',s.use_eligibility_paths,'structured:',s.use_structured_conditions,'llm:',s.use_llm_judge)"
if ($LASTEXITCODE -ne 0) { throw 'Configuration check failed.' }
```

위 `$env:` 값은 **현재 PowerShell과 그 자식 프로세스에만** 적용된다. 새 터미널에서는 다시 설정하거나 자신의 `backend/.env`에 같은 값을 기록한다. 프로세스 환경변수가 `.env`보다 우선하며, `.env`는 실행 작업 디렉터리에서 찾으므로 `backend/`에서 실행한다. 이미 실행 중인 서버는 설정 변경 후 재시작해야 한다.

- `USE_ELIGIBILITY_PATHS=true`는 경로 판정을 켠다. 적용 가능한 정책은 구조화 조건보다 경로 판정이 우선한다.
- `USE_STRUCTURED_CONDITIONS=true`는 구조화 조건 판정을 켠다. 경로 판정이 적용되지 않는 정책은 적용 가능한 구조화 분석이나 기존 분석 결과를 유지한다.
- `USE_LLM_JUDGE=false`로 둔다. LLM 판정이 켜져 있으면 실험용 판정으로 먼저 반환한다.

[읽기 전용 확인](#4-읽기-전용-확인)을 통과하면 [서버 실행](#5-서버-실행과-브라우저-확인)으로 진행한다.

## 3. 별도 DB 재구성 및 명시적 시드 적재

빈 격리 DB를 구성하거나 특정 로컬 DB의 데이터를 의도적으로 갱신할 때만 실행한다. 공유 초기본과 평소 사용하는 계정 DB는 이 절차의 대상에서 제외한다. 대상 DB를 사용하는 서버·동기화 작업을 중단하고 경로와 변경 범위를 먼저 확인한다. 기존 DB를 삭제하거나 다른 사람의 DB로 덮어쓰지 않는다.

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

### 3.1 재구성 대상 지정

`backend/`에서 2장의 가상환경을 사용한다. 아래 경로는 초기화·적재용 별도 DB의 예시다. 공유 초기본을 복사하는 단계는 이 경우 생략한다.

```powershell
New-Item -ItemType Directory -Force .\.tmp-path-rebuild | Out-Null
$policyDb = Join-Path (Get-Location).Path '.tmp-path-rebuild\youth_welfare.db'
$env:DATABASE_URL = 'sqlite:///' + $policyDb.Replace('\', '/')
Write-Output $policyDb
```

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

## 4. 읽기 전용 확인

현재 수량은 다음과 같다. 향후 검수·정책 데이터가 갱신되면 같은 커밋의 시드와 비교한다.

| 항목 | 현재 기대값 |
|---|---:|
| `welfare_services` | 152 |
| `welfare_eligibility_conditions` | 1,749 |
| `policy_eligibility` | 152 |
| 사람 검수 (`drafted_by != converted`) | 152 |
| 미검수 변환본 (`drafted_by = converted`) | 0 |
| `eligibility_paths` (`_common` 152행 포함) | 572 |
| `eligibility_path_conditions` | 533 |
| 원문 해시 불일치·원문 누락 | 0 |

시드의 `status=reviewed`는 엔진에서 사용할 수 있는 상태다. 사람 검수 여부는 검수본과 `drafted_by`를 함께 확인한다. 엔진 응답의 `path_review`는 사람 검수본을 `reviewed`, 자동 변환본을 `converted`로 구분한다.

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

## 5. 서버 실행과 브라우저 확인

### 백엔드: 위와 같은 PowerShell

실행 전에 4장의 확인을 통과한 별도 로컬 DB를 선택하고 2장의 플래그와 `FRONTEND_ORIGINS`를 적용한다. 3장에서 재구성한 DB를 실행할 때는 2장의 설정 예시에서 `$policyDb`에 재구성한 파일을 지정한다. 기본 SQLite 경로는 `backend/`에서 실행할 때 공유 초기본을 가리킨다.

```powershell
if (-not $policyDb -or -not (Test-Path -LiteralPath $policyDb -PathType Leaf)) { throw 'Prepare a local database first.' }
$policyDb = (Resolve-Path -LiteralPath $policyDb -ErrorAction Stop).Path
if ($policyDb -eq (Join-Path (Get-Location).Path 'youth_welfare.db')) { throw 'Use a separate local database.' }
$env:DATABASE_URL = 'sqlite:///' + $policyDb.Replace('\', '/')
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
3. 최신 공유 시드와 일치하는 DB에서는 `path_review=reviewed` 152개, `converted` 0개인지 확인한다.
4. 미충족 탭의 개인화 안내를 확인한다. 가상 예: 만 25세·남성이면 여성청소년 생리용품 지원의 연령/성별 안내, 본인 월소득 3,000,000원이면 두루누리 기준 2,699,999원과의 차액 300,001원을 확인한다.
5. 로그아웃하면 개인화 안내가 사라지고 전용 API는 401을 반환해야 한다. 다른 계정의 진단 식별자로도 조회할 수 없어야 한다.

기존 진단 스냅샷은 플래그나 시드를 바꿔도 자동으로 갱신되지 않는다. 기존 기록은 보존되며, 레거시 결과에 경로가 나중에 붙는 것은 아니다. `refresh`는 최신 현황 `current`를 갱신하고, 결과 화면이 사용하는 `diagnosis`는 새 진단에서 갱신한다. 이전 결과·변환본·원문/조건 불일치·지원하지 않는 복합 조건에서는 일반 안내가 유지될 수 있다.

## 6. 2026-11-16 초기 적재 검증 기록

커밋된 HEAD의 `backend/`만 임시 디렉터리에 내보내고, 기존 DB·`.env`를 복사하지 않은 상태에서 위 초기화·원문 import·경로 load를 실행했다. 정책 152개 / 저장 조건 1,749개 / 사람 검수 60개 / 변환본 92개, 원문 해시 일치 152개, 무결성 `ok`, 외래 키 오류 0건을 확인했다. 합성 사용자 데이터 6개 테이블(회원·프로필·추가 정보·진단 스냅샷·세션·인증 시도)은 import와 경로 재적재 전후 동일했다.

위 수치는 당시 격리 환경의 데이터 배포·적용 기록이다. 전체 정책의 의미적 판정 정확도와 다른 PC의 의존성 설치는 이 검증 범위에 포함되지 않았다.
