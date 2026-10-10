import xml.etree.ElementTree as ET
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.eligibility_condition_service import (
    EligibilityConditionService,
)
from app.clients.welfare_api_client import WelfareApiClient
from app.models.welfare_service import WelfareService


class WelfareSyncService:
    """중앙부처 복지서비스 API 데이터를 데이터베이스에 동기화한다."""

    PAGE_SIZE = 100
    YOUTH_LIFE_ARRAY = "004"

    def __init__(self):
        self.client = WelfareApiClient()

    async def sync_welfare_services(
        self,
        db: Session,
        max_services: int | None = None,
    ) -> dict:
        """
        청년 대상 복지서비스 목록과 상세정보를 가져와 저장한다.

        max_services:
            테스트 시 처리할 최대 서비스 수.
            None이면 조회된 청년 대상 서비스를 모두 처리한다.
        """
        if max_services is not None and max_services < 1:
            raise ValueError("max_services는 1 이상이어야 합니다.")

        summaries = []
        page_no = 1
        total_count = None

        # 1. 청년 대상 복지서비스 목록 조회
        while True:
            xml_text = await self.client.get_welfare_services(
                page_no=page_no,
                num_of_rows=self.PAGE_SIZE,
                life_array=self.YOUTH_LIFE_ARRAY,
            )

            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError as exc:
                raise ValueError(
                    "복지서비스 목록 응답이 올바른 XML 형식이 아닙니다."
                ) from exc

            result_code = root.findtext(".//resultCode")
            result_message = root.findtext(
                ".//resultMessage",
                default="",
            )

            if result_code not in (None, "0"):
                raise ValueError(
                    f"복지서비스 목록 API 오류: "
                    f"{result_code} - {result_message}"
                )

            if total_count is None:
                count_text = root.findtext(".//totalCount")
                if count_text and count_text.isdigit():
                    total_count = int(count_text)

            page_services = self.client.parse_welfare_services(xml_text)

            if not page_services:
                break

            summaries.extend(page_services)

            if max_services is not None and len(summaries) >= max_services:
                summaries = summaries[:max_services]
                break

            if total_count is not None and len(summaries) >= total_count:
                break

            page_no += 1

        # 2. 각 서비스의 상세정보를 조회하고 DB에 저장
        synced_count = 0
        failed_services = []

        for summary in summaries:
            serv_id = summary.get("serv_id", "").strip()

            if not serv_id:
                failed_services.append({
                    "serv_id": "",
                    "reason": "서비스 ID가 없어 건너뛰었습니다.",
                })
                continue

            try:
                detail_xml = await self.client.get_welfare_service_detail(
                    serv_id
                )
                detail = self.client.parse_welfare_service_detail(
                    detail_xml
                )

                # 목록 정보와 상세 정보를 합친다.
                data = {**summary, **detail}

                service = db.get(WelfareService, serv_id)

                if service is None:
                    service = WelfareService(serv_id=serv_id)
                    db.add(service)

                # 모델에 정의된 필드만 업데이트한다.
                fields = [
                    "serv_name",
                    "department",
                    "organization",
                    "summary",
                    "detail_url",
                    "support_cycle",
                    "support_type",
                    "online_application",
                    "target_details",
                    "selection_criteria",
                    "support_content",
                    "reference_year",
                    "life_stages",
                    "target_groups",
                    "interest_categories",
                    "application_methods",
                    "contact_numbers",
                    "related_websites",
                    "application_forms",
                    "related_laws",
                ]

                for field in fields:
                    if field in data:
                        setattr(service, field, data[field])

                # 상세정보의 자격 요건을 구조화해 저장한다.
                EligibilityConditionService.replace_conditions(
                    db=db,
                    serv_id=serv_id,
                    target_details=service.target_details,
                    selection_criteria=service.selection_criteria,
                )

                service.synced_at = datetime.utcnow()

                # 서비스별로 저장해 중간 실패 시 앞선 저장 결과를 보존한다.
                db.commit()
                synced_count += 1

            except Exception as exc:
                db.rollback()

                failed_services.append({
                    "serv_id": serv_id,
                    "reason": str(exc)[:300],
                })

        return {
            "life_array": self.YOUTH_LIFE_ARRAY,
            "listed_count": len(summaries),
            "synced_count": synced_count,
            "failed_count": len(failed_services),
            "failed_services": failed_services,
        }
