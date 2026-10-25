from sqlalchemy.orm import Session

from app.models.welfare_sync import WelfareApiQuotaWindow
from app.repositories.welfare_sync_repository import (
    QuotaWindowUnavailable,
    WelfareSyncRepository,
)


def confirm_quota_window(
    db: Session,
    *,
    window_id: str,
    operation: str,
    verified_available_calls: int | None,
    operator_name: str,
    confirm_provider_quota: bool,
) -> WelfareApiQuotaWindow:
    if not confirm_provider_quota:
        raise QuotaWindowUnavailable(
            "Explicit confirmation of provider quota availability is required."
        )
    return WelfareSyncRepository.open_quota_window(
        db,
        window_id=window_id,
        operation=operation,
        verified_available_calls=verified_available_calls,
        operator_name=operator_name,
    )
