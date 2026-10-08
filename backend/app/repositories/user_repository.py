from sqlalchemy.orm import Session

from app.models.user import User
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

        db.add(user)
        db.commit()
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