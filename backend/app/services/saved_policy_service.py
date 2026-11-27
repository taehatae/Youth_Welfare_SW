from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.account import Account
from app.repositories.account_repository import AccountRepository
from app.schemas.account import SavedPoliciesInput, SavedPolicyUpdate, WorkspaceState
from app.services.profile_privacy import profile_key, public_state


class SavedPolicyService:
    def update(self, db: Session, account: Account, data: SavedPolicyUpdate) -> SavedPoliciesInput:
        repository = AccountRepository()
        try:
            state = dict(repository.state(db, account))
            saved = [dict(item) for item in state.get("savedPolicies", [])]
            item = next((item for item in saved
                         if item["policy"]["id"] == data.policyId
                         and profile_key(account, item["profile"]) == data.profileKey), None)
            if item is None:
                raise HTTPException(404, "저장한 관심 정책을 찾지 못했어요. 목록을 다시 불러와주세요.")
            # 사용자가 기록한 관리 정보만 갱신한다. 진단 결과와 프로필 원문은 유지한다.
            item["trackingStatus"] = data.trackingStatus
            item["note"] = data.note.strip()
            state["savedPolicies"] = saved
            result = public_state(WorkspaceState.model_validate(state), account)
            repository.save_state(db, account, state)
            db.commit()
            return SavedPoliciesInput(items=result.savedPolicies)
        except Exception:
            db.rollback()
            raise
