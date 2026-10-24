from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.user import (
    SaveProfileResponse,
    UserProfileCreate,
)
from app.models.account import Account
from app.services.auth_service import current_account, throttle, verify_password
from app.services.account_service import AccountService
from app.schemas.account import WorkspaceState, SavedPoliciesInput, ProfileViewInput, SavedPolicyToggle, SavedPolicyUpdate
from app.services.saved_policy_service import SavedPolicyService
from app.services.profile_privacy import public_state, profile_key


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.post(
    "/profile",
    response_model=SaveProfileResponse,
)
def create_profile(
    profile: UserProfileCreate,
    db: Session = Depends(get_db),
    account: Account = Depends(current_account),
) -> SaveProfileResponse:
    try:
        user = AccountService().repository.save_profile(db, account, profile)
        db.commit()
        return SaveProfileResponse(user_id=user.user_id, status="success", message="계정에 프로필을 저장했습니다.")
    except Exception:
        db.rollback()
        raise


@router.get("/profile", response_model=UserProfileCreate | None)
def get_profile(db: Session = Depends(get_db), account: Account = Depends(current_account)):
    raise HTTPException(403, "프로필을 조회하려면 아이디와 비밀번호를 다시 입력해주세요.")


@router.post("/profile/view", response_model=UserProfileCreate | None)
def view_profile(data: ProfileViewInput, request: Request, db: Session = Depends(get_db), account: Account = Depends(current_account)):
    # 조회할 때마다 검증한다. 로그인 쿠키만으로 재사용할 수 있는 조회 권한을 발급하지 않는다.
    throttle(request, db)
    valid = verify_password(data.password, account.password_hash)
    if data.username != account.username or not valid:
        raise HTTPException(403, "현재 로그인한 계정의 아이디와 비밀번호를 확인해주세요.")
    repository = AccountService().repository
    snapshot = repository.state(db, account).get(data.snapshot)
    return snapshot["profile"] if snapshot else repository.profile(db, account)


@router.get("/state", response_model=WorkspaceState)
def get_state(db: Session = Depends(get_db), account: Account = Depends(current_account)):
    return public_state(AccountService().state(db, account), account)


@router.put("/saved", response_model=SavedPoliciesInput)
def save_policies(data: SavedPoliciesInput, db: Session = Depends(get_db), account: Account = Depends(current_account)):
    raise HTTPException(410, "관심 정책 저장은 /users/saved/toggle을 사용해주세요.")


@router.post("/saved/toggle", response_model=SavedPoliciesInput)
def toggle_policy(data: SavedPolicyToggle, db: Session = Depends(get_db), account: Account = Depends(current_account)):
    repository = AccountService().repository
    try:
        state = dict(repository.state(db, account))
        saved = list(state.get("savedPolicies", []))
        existing = next((item for item in saved if profile_key(account, item["profile"]) == data.profileKey and item["policy"]["id"] == data.policyId), None)
        if existing:
            saved.remove(existing)
        else:
            if len(saved) >= 200:
                raise HTTPException(409, "관심 정책은 최대 200개까지 저장할 수 있어요.")
            snapshots = [state.get(name) for name in ("current", "diagnosis", "previous", "previousDiagnosis")]
            snapshot = next((item for item in snapshots if item and profile_key(account, item["profile"]) == data.profileKey), None)
            row = next((row for row in snapshot["analysis"]["matched"]["analysis_results"] if row["policy_id"] == data.policyId), None) if snapshot else None
            if not row:
                raise HTTPException(404, "내 진단 결과에서 정책을 찾지 못했어요.")
            conditions = [{"field": c["condition_type"], "current": c["current_value"], "required": c["required_value"], "status": label, "guide": c["action_guide"] or c["message"]}
                          for key, label in (("gap_conditions", "미충족"), ("review_conditions", "추가 확인")) for c in row[key]]
            saved.append({"profileKey": data.profileKey, "profile": snapshot["profile"], "savedAt": datetime.now(timezone.utc).isoformat(),
                          "policy": {"id": row["policy_id"], "title": row["title"], "status": row["status"], "url": row["detail_url"], "description": " ".join(row.get("notes", [])),
                                     "counts": {"evaluated": row["evaluated_conditions"], "passed": row["passed_conditions"], "failed": len(row["gap_conditions"]), "review": len(row["review_conditions"])}, "conditions": conditions}})
        state["savedPolicies"] = saved
        result = public_state(WorkspaceState.model_validate(state), account)
        repository.save_state(db, account, state)
        db.commit()
        return SavedPoliciesInput(items=result.savedPolicies)
    except Exception:
        db.rollback()
        raise


@router.patch("/saved", response_model=SavedPoliciesInput)
def update_saved_policy(data: SavedPolicyUpdate, db: Session = Depends(get_db), account: Account = Depends(current_account)):
    return SavedPolicyService().update(db, account, data)
