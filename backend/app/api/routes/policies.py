from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.policy_catalog import CatalogResponse, CatalogDetail
from app.services.policy_catalog_service import PolicyCatalogService

router = APIRouter(prefix="/policies", tags=["Policy catalog"])
service = PolicyCatalogService()


@router.get("", response_model=CatalogResponse)
def list_policies(q: str = Query("", max_length=100), category: str = "all",
                  page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=48),
                  db: Session = Depends(get_db)):
    return service.search(db, q, category, page, page_size)


@router.get("/{policy_id}", response_model=CatalogDetail)
def policy_detail(policy_id: str, db: Session = Depends(get_db)):
    return service.detail(db, policy_id)
