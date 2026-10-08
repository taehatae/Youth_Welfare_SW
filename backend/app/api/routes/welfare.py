from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.welfare import (
    MatchedPoliciesResponse,
    ReverseRecommendationsResponse,
)


router = APIRouter(
    prefix="/welfare",
    tags=["Welfare"],
)


user_repository = UserRepository()


@router.get(
    "/matched",
    response_model=MatchedPoliciesResponse,
)
def get_matched_welfare(
    user_id: str,
    db: Session = Depends(get_db),
) -> MatchedPoliciesResponse:

    user = user_repository.get_by_id(
        db=db,
        user_id=user_id,
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다.",
        )

    # 1단계에서는 실제 복지 매칭 로직을 구현하지 않는다.
    # 2단계에서 welfare_policies + policy_conditions를 이용해 구현한다.

    return MatchedPoliciesResponse(
        matched_count=0,
        policies=[],
    )


@router.get(
    "/reverse-engineering",
    response_model=ReverseRecommendationsResponse,
)
def get_reverse_engineering(
    user_id: str,
    db: Session = Depends(get_db),
) -> ReverseRecommendationsResponse:

    user = user_repository.get_by_id(
        db=db,
        user_id=user_id,
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다.",
        )

    # 1단계에서는 실제 역설계 로직을 구현하지 않는다.
    # 이후 조건 비교 및 역설계 알고리즘을 연결한다.

    return ReverseRecommendationsResponse(
        recommendations=[],
    )