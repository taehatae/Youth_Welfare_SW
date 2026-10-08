import httpx

from app.core.config import settings


class WelfareApiClient:

    def __init__(self):
        self.base_url = settings.welfare_api_base_url
        self.service_key = settings.welfare_api_service_key

    async def get_welfare_services(
        self,
        page_no: int = 1,
        num_of_rows: int = 10,
    ) -> str:

        if not self.base_url:
            raise ValueError(
                "WELFARE_API_BASE_URL이 설정되지 않았습니다."
            )

        if not self.service_key:
            raise ValueError(
                "WELFARE_API_SERVICE_KEY가 설정되지 않았습니다."
            )

        params = {
            "ServiceKey": self.service_key,
            "pageNo": page_no,
            "numOfRows": num_of_rows,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                self.base_url,
                params=params,
            )

            response.raise_for_status()

            return response.text