"""간편 정책 찾기 공개 API. 로그인 없이 쓰며 아무것도 저장하지 않는다(계정·프로필·진단 기록과 무관)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.quick_finder import (
    QuickCategoriesResponse, QuickCategoryDetail, QuickEvaluateRequest, QuickEvaluateResponse, QuickInterpretRequest,
    QuickInterpretResponse,
)
from app.services import quick_finder_service as service
from app.services import quick_intent_service

router = APIRouter(prefix="/quick-finder", tags=["Quick finder"])


@router.get("/categories", response_model=QuickCategoriesResponse)
def list_categories(db: Session = Depends(get_db)):
    return service.categories(db)


@router.get("/categories/{category}", response_model=QuickCategoryDetail)
def category_detail(category: str, db: Session = Depends(get_db)):
    return service.category_detail(db, category)


@router.post("/evaluate", response_model=QuickEvaluateResponse)
def evaluate(request: QuickEvaluateRequest, db: Session = Depends(get_db)):
    return service.evaluate(db, request.category, request.answers)


@router.post("/interpret", response_model=QuickInterpretResponse)
def interpret(request: QuickInterpretRequest):
    """문장 → 정책 분야(예: "자취 관련 정책 없어?" → 주거). DB를 쓰지 않고 문장을 저장하지 않는다."""
    return quick_intent_service.interpret(request.text)
