
import html
import re
import xml.etree.ElementTree as ET

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

    @staticmethod
    def clean_text(text: str) -> str:
        """XML 텍스트의 문자 참조, 줄바꿈 및 붙어 있는 항목을 정리한다."""
        if not text:
            return ""

        cleaned = text

        # 이중 인코딩된 문자 참조까지 처리한다.
        for _ in range(2):
            decoded = html.unescape(cleaned)
            if decoded == cleaned:
                break
            cleaned = decoded

        # 줄바꿈 형식을 통일한다.
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

        # 붙어 있는 양육공백 항목 사이의 누락된 줄바꿈을 보정한다.
        cleaned = re.sub(
            r"(경우)[ \t]*(?=- 아동학대 피해)",
            r"\1\n",
            cleaned,
        )

        # 중위소득 기준 항목 사이에 누락된 줄바꿈을 보정한다.
        cleaned = re.sub(
            r"(원)[ \t]*(?=- 기준 중위소득)",
            r"\1\n",
            cleaned,
        )

        # 줄바꿈 주변의 불필요한 공백을 정리한다.
        cleaned = re.sub(r"[ \t]*\n[ \t]*", "\n", cleaned)

        # 한 줄 안의 연속된 공백을 정리한다.
        cleaned = re.sub(r"[ \t]+", " ", cleaned)

        return cleaned.strip()

    async def get_welfare_services(
        self,
        page_no: int = 1,
        num_of_rows: int = 10,
        life_array: str | None = None,
    ) -> str:

        """중앙부처복지서비스 목록조회. callTp=L."""
        self._validate_settings()

        url = f"{self.base_url}/{self.LIST_ENDPOINT}"

        
        params = {
            "serviceKey": self.service_key,
            "callTp": "L",
            "pageNo": page_no,
            "numOfRows": num_of_rows,
            "srchKeyCode": "001",
        }

        if life_array:
            params["lifeArray"] = life_array

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.text

    def parse_welfare_services(self, xml_text: str) -> list[dict]:
        """복지서비스 목록 XML을 파싱한다."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise ValueError(
                "복지서비스 API 응답이 올바른 XML 형식이 아닙니다."
            ) from exc

        result_code = root.findtext(".//resultCode")
        result_message = root.findtext(".//resultMessage", default="")

        if result_code not in (None, "0"):
            raise ValueError(
                f"복지서비스 API 오류: {result_code} - {result_message}"
            )

        services = []

        for item in root.findall(".//servList"):
            service = {
                "serv_id": self.clean_text(
                    item.findtext("servId", default="")
                ),
                "serv_name": self.clean_text(
                    item.findtext("servNm", default="")
                ),
                "department": self.clean_text(
                    item.findtext("jurMnofNm", default="")
                ),
                "organization": self.clean_text(
                    item.findtext("jurOrgNm", default="")
                ),
                "summary": self.clean_text(
                    item.findtext("servDgst", default="")
                ),
                "life_stages": self.clean_text(
                    item.findtext("lifeArray", default="")
                ),
                "detail_url": self.clean_text(
                    item.findtext("servDtlLink", default="")
                ),
                "support_cycle": self.clean_text(
                    item.findtext("sprtCycNm", default="")
                ),
                "support_type": self.clean_text(
                    item.findtext("srvPvsnNm", default="")
                ),
                "online_application": self.clean_text(
                    item.findtext("onapPsbltYn", default="")
                ),
            }
            services.append(service)

        return services

    def parse_welfare_service_detail(self, xml_text: str) -> dict:
        """복지서비스 상세 XML에서 자격 조건과 지원 정보를 추출한다."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise ValueError(
                "복지서비스 상세 응답이 올바른 XML 형식이 아닙니다."
            ) from exc

        result_code = root.findtext(".//resultCode")
        result_message = root.findtext(".//resultMessage", default="")

        if result_code not in (None, "0"):
            raise ValueError(
                f"복지서비스 API 오류: {result_code} - {result_message}"
            )

        service = {
            "serv_id": self.clean_text(
                root.findtext("servId", default="")
            ),
            "serv_name": self.clean_text(
                root.findtext("servNm", default="")
            ),
            "department": self.clean_text(
                root.findtext("jurMnofNm", default="")
            ),
            "target_details": self.clean_text(
                root.findtext("tgtrDtlCn", default="")
            ),
            "selection_criteria": self.clean_text(
                root.findtext("slctCritCn", default="")
            ),
            "support_content": self.clean_text(
                root.findtext("alwServCn", default="")
            ),
            "reference_year": self.clean_text(
                root.findtext("crtrYr", default="")
            ),
            "summary": self.clean_text(
                root.findtext("wlfareInfoOutlCn", default="")
            ),
            "support_cycle": self.clean_text(
                root.findtext("sprtCycNm", default="")
            ),
            "support_type": self.clean_text(
                root.findtext("srvPvsnNm", default="")
            ),
            "life_stages": self.clean_text(
                root.findtext("lifeArray", default="")
            ),
            "target_groups": self.clean_text(
                root.findtext("trgterIndvdlArray", default="")
            ),
            "interest_categories": self.clean_text(
                root.findtext("intrsThemaArray", default="")
            ),
        }

        list_fields = {
            "application_methods": "applmetList",
            "contact_numbers": "inqplCtadrList",
            "related_websites": "inqplHmpgReldList",
            "application_forms": "basfrmList",
            "related_laws": "baslawList",
        }

        for field_name, tag_name in list_fields.items():
            service[field_name] = []

            for item in root.findall(tag_name):
                service[field_name].append(
                    {
                        "name": self.clean_text(
                            item.findtext("servSeDetailNm", default="")
                        ),
                        "link_or_content": self.clean_text(
                            item.findtext("servSeDetailLink", default="")
                        ),
                    }
                )

        return service

    async def get_welfare_service_detail(self, serv_id: str) -> str:
        """중앙부처복지서비스 상세조회. callTp=D."""
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
