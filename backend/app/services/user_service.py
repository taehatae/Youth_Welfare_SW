from sqlalchemy.orm import Session

from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    SaveProfileResponse,
    UserProfileCreate,
)


class UserService:

    def __init__(self):
        self.repository = UserRepository()

    def create_profile(
        self,
        db: Session,
        profile: UserProfileCreate,
    ) -> SaveProfileResponse:

        user = self.repository.create(
            db=db,
            profile=profile,
        )

        return SaveProfileResponse(
            user_id=user.user_id,
            status="success",
            message="사용자 프로필이 저장되었습니다.",
        )