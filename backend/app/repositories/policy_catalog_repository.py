from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session
from app.models.welfare_service import WelfareService


class PolicyCatalogRepository:
    def search(self, db: Session, query: str):
        statement = select(WelfareService)
        if query:
            statement = statement.where(or_(
                WelfareService.serv_name.contains(query, autoescape=True),
                WelfareService.summary.contains(query, autoescape=True),
                WelfareService.support_content.contains(query, autoescape=True),
            ))
        return db.scalars(statement.order_by(WelfareService.serv_name, WelfareService.serv_id)).all()

    def count(self, db: Session):
        return db.scalar(select(func.count()).select_from(WelfareService)) or 0

    def get(self, db: Session, policy_id: str):
        return db.get(WelfareService, policy_id)
