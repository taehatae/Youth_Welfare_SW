from sqlalchemy.orm import Session

from app.models.user import User, UserEligibilityConditions
from app.schemas.user import UserProfileCreate


class UserRepository:

    def create(
        self,
        db: Session,
        profile: UserProfileCreate,
    ) -> User:

        user = User(
            age=profile.age,
            region=profile.region,
            income_level=profile.income_level,
            employment_status=profile.employment_status.value,
        )

        try:
            db.add(user)
            db.flush()

            db.add(
                UserEligibilityConditions(
                    user_id=user.user_id,
                    conditions=profile.eligibility_conditions,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

        db.refresh(user)

        return user

    def get_by_id(
        self,
        db: Session,
        user_id: str,
    ) -> User | None:

        return (
            db.query(User)
            .filter(User.user_id == user_id)
            .first()
        )

    def get_eligibility_conditions(
        self,
        db: Session,
        user_id: str,
    ) -> UserEligibilityConditions | None:
        return db.get(UserEligibilityConditions, user_id)
