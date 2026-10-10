from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.user import (
    SaveProfileResponse,
    UserProfileCreate,
)
from app.services.user_service import UserService


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


user_service = UserService()


@router.post(
    "/profile",
    response_model=SaveProfileResponse,
)
def create_profile(
    profile: UserProfileCreate,
    db: Session = Depends(get_db),
) -> SaveProfileResponse:

    return user_service.create_profile(
        db=db,
        profile=profile,
    )