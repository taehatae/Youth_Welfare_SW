from sqlalchemy.orm import Session

from app.models.account import Account, AccountWorkspace
from app.models.user import User, UserEligibilityConditions
from app.schemas.user import UserProfileCreate


class AccountRepository:
    def save_profile(self, db: Session, account: Account, profile: UserProfileCreate) -> User:
        user = db.get(User, account.profile_id) if account.profile_id else None
        if user is None:
            user = User()
            db.add(user)
        user.age = profile.age
        user.region = profile.region
        user.income_level = profile.income_level
        user.employment_status = profile.employment_status.value
        db.flush()
        account.profile_id = user.user_id
        extra = db.get(UserEligibilityConditions, user.user_id)
        if extra is None:
            extra = UserEligibilityConditions(user_id=user.user_id)
            db.add(extra)
        extra.conditions = profile.eligibility_conditions
        db.flush()
        return user

    def profile(self, db: Session, account: Account) -> UserProfileCreate | None:
        user = db.get(User, account.profile_id) if account.profile_id else None
        if user is None:
            return None
        extra = db.get(UserEligibilityConditions, user.user_id)
        return UserProfileCreate(age=user.age, region=user.region, income_level=user.income_level,
                                 employment_status=user.employment_status,
                                 eligibility_conditions=(extra.conditions or {}) if extra else {})

    def state(self, db: Session, account: Account) -> dict:
        record = db.get(AccountWorkspace, account.account_id)
        return record.state if record else {}

    def save_state(self, db: Session, account: Account, state: dict) -> None:
        record = db.get(AccountWorkspace, account.account_id)
        if record is None:
            record = AccountWorkspace(account_id=account.account_id)
            db.add(record)
        record.state = state
