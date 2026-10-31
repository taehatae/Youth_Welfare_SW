"""Keep application imports during pytest away from the configured local DB."""

import os


os.environ["DATABASE_URL"] = "sqlite://"
# 로컬 .env에서 LLM 조건을 켜 두어도 테스트 결과가 캐시 파일에 따라 바뀌지 않게 한다.
os.environ["USE_LLM_JUDGE"] = "false"
os.environ["USE_STRUCTURED_CONDITIONS"] = "false"
