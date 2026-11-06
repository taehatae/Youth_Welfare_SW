"""자격 경로 시드(data/eligibility_paths.json)를 DB에 넣는다. 시드를 고친 뒤 실행한다.

DB가 비어 있으면 진단할 때 자동으로 넣지만, 이미 들어 있으면 이 스크립트로 다시 넣어야 바뀐 내용이 반영된다.

    python scripts/build_eligibility_paths.py && python scripts/load_eligibility_paths.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main  # noqa: E402,F401  테이블 생성
from app.database.connection import SessionLocal  # noqa: E402
from app.services.eligibility_path_service import SEED_PATH, seed_from_file  # noqa: E402


def main() -> int:
    db = SessionLocal()
    try:
        count = seed_from_file(db, SEED_PATH)
    finally:
        db.close()
    print(f"{count}개 정책의 자격 경로를 DB에 넣었어요 ← {SEED_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
