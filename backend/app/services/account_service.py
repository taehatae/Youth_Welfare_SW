from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.user import User
from app.repositories.account_repository import AccountRepository
from app.schemas.account import WorkspaceState
from app.schemas.user import UserProfileCreate
from app.services.eligibility_matching_service import EligibilityMatchingService


class AccountService:
    def __init__(self):
        self.repository = AccountRepository()
        self.matching = EligibilityMatchingService()

    def state(self, db: Session, account: Account) -> WorkspaceState:
        data = {**self.repository.state(db, account),
                "profile": self.repository.profile(db, account)}
        return WorkspaceState.model_validate(data)

    def analyze(self, db: Session, account: Account, profile: UserProfileCreate | None = None) -> WorkspaceState:
        is_diagnosis = profile is not None
        previous = self.repository.state(db, account)
        profile = profile or self.repository.profile(db, account)
        if profile is None:
            raise HTTPException(409, "먼저 내 정보를 저장해주세요.")
        profile = profile.model_copy(update={"eligibility_conditions": profile.eligibility_conditions or {}})
        try:
            user = self.repository.save_profile(db, account, profile) if is_diagnosis else db.get(User, account.profile_id)
            result = self.matching.analyze_user(db, user, profile.eligibility_conditions)
            # 상세 링크는 전체 분석 결과에 제공된다.
            urls = {row["policy_id"]: row["detail_url"] for row in result["analysis_results"]}
            for policy in result["policies"]:
                policy["detail_url"] = urls.get(policy["policy_id"], "")
            snapshot = {"profile": profile.model_dump(mode="json"),
                        "analysis": {"userId": user.user_id, "matched": result,
                                     "reverse": {"recommendations": []}},
                        "checkedAt": datetime.now(timezone.utc).isoformat()}
            known = {p["policy_id"]: p for p in previous.get("knownPolicies", [])}
            known.update({p["policy_id"]: p for p in result["policies"]})
            state = {"diagnosis": snapshot if is_diagnosis else previous.get("diagnosis"),
                     "savedPolicies": previous.get("savedPolicies", []),
                     "previousDiagnosis": previous.get("diagnosis") if is_diagnosis else previous.get("previousDiagnosis"),
                     "current": snapshot,
                     "previous": None if is_diagnosis else previous.get("current"),
                     "knownPolicies": result["policies"] if is_diagnosis else list(known.values())}
            # 스키마 확인 후 프로필과 분석 결과를 한 트랜잭션에 저장한다.
            response = WorkspaceState.model_validate({**state, "profile": profile})
            self.repository.save_state(db, account, response.model_dump(mode="json", exclude={"profile"}))
            db.commit()
            return response
        except Exception:
            db.rollback()
            raise
