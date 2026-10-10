
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.welfare import (
    MatchedPoliciesResponse,
    ReverseRecommendationsResponse,
)
from app.services.welfare_sync_service import WelfareSyncService


router = APIRouter(
    prefix="/welfare",
    tags=["Welfare"],
)

user_repository = UserRepository()
welfare_sync_service = WelfareSyncService()


@router.post("/sync")
async def sync_welfare_services(
    max_services: int | None = Query(
        default=None,
        ge=1,
        le=500,
        description="동기화할 최대 서비스 수. 테스트 시 5를 지정하고, 생략하면 전체 조회",
    ),
    db: Session = Depends(get_db),
):
    """
    청년 대상 복지서비스를 API에서 가져와 데이터베이스에 동기화한다.

    기본값은 5개로, 먼저 소규모로 동작을 검증한다.
    전체 동기화는 max_services=500으로 여러 번 실행하거나,
    다음 단계에서 전체 동기화 옵션을 별도로 제공할 수 있다.
    """
    try:
        return await welfare_sync_service.sync_welfare_services(
            db=db,
            max_services=max_services,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


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

    # 실제 자격 매칭 로직은 다음 단계에서 구현한다.
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

    # 실제 역설계 로직은 이후 조건 비교 기능과 연결한다.
    return ReverseRecommendationsResponse(
        recommendations=[],
    )
