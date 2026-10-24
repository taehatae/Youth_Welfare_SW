"""프로필 원문은 재인증 요청에만 반환하고 결과에는 불투명한 식별자를 사용한다."""
from copy import deepcopy
import hashlib
import hmac
import json

from app.models.account import Account
from app.schemas.account import WorkspaceState


def profile_key(account: Account, profile: dict) -> str:
    payload = json.dumps(profile, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hmac.new(account.password_hash.encode(), payload.encode(), hashlib.sha256).hexdigest()


def hide_input_values(value):
    if isinstance(value, dict):
        return {key: "프로필 보호 중" if key in {"current_value", "current"} and isinstance(item, str)
                else hide_input_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [hide_input_values(item) for item in value]
    return value


def public_state(state: WorkspaceState, account: Account) -> WorkspaceState:
    data = deepcopy(state.model_dump(mode="json"))
    data["profile"] = None
    for name in ("diagnosis", "previousDiagnosis", "current", "previous"):
        snapshot = data.get(name)
        if snapshot:
            snapshot["profileKey"] = profile_key(account, snapshot["profile"])
            snapshot["profile"] = None
    for saved in data["savedPolicies"]:
        saved["profileKey"] = profile_key(account, saved["profile"])
        saved["profile"] = None
    return WorkspaceState.model_validate(hide_input_values(data))
