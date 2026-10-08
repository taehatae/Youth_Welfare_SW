import httpx

from app.core.config import settings


class WelfareApiClient:
    LIST_ENDPOINT = "NationalWelfarelistV001"
    DETAIL_ENDPOINT = "NationalWelfaredetailedV001"

    def __init__(self):
        self.base_url = settings.welfare_api_base_url.rstrip("/")
        self.service_key = settings.welfare_api_service_key

    def _validate_settings(self):
        if not self.base_url:
            raise ValueError("WELFARE_API_BASE_URL이 설정되지 않았습니다.")

        if not self.service_key:
            raise ValueError("WELFARE_API_SERVICE_KEY가 설정되지 않았습니다.")

    async def get_welfare_services(
        self,
        page_no: int = 1,
        num_of_rows: int = 10,
    ) -> str:
        """
        중앙부처복지서비스 목록조회

        callTp=L : 목록조회
        """
        self._validate_settings()

        url = f"{self.base_url}/{self.LIST_ENDPOINT}"

        params = {
            "serviceKey": self.service_key,
            "callTp": "L",
            "pageNo": page_no,
            "numOfRows": num_of_rows,
            "srchKeyCode": "001",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.text

    async def get_welfare_service_detail(
        self,
        serv_id: str,
    ) -> str:
        """
        중앙부처복지서비스 상세조회

        callTp=D : 상세조회
        servId    : 복지서비스 ID
        """
        self._validate_settings()

        url = f"{self.base_url}/{self.DETAIL_ENDPOINT}"

        params = {
            "serviceKey": self.service_key,
            "callTp": "D",
            "servId": serv_id,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.text