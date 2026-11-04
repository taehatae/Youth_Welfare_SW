"""자격 조건 초안을 원문과 나란히 보며 채점하는 로컬 화면.

판단(조건·확인 사항) 하나하나를 맞음/틀림으로 채점하고, 정책마다 놓친 조건을 적는다.
누를 때마다 채점 결과 파일(초안 옆 *_review.json)에 바로 저장한다.

    python scripts/review_server.py data/eligibility_paths_batch2_draft.json   # http://localhost:8765
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.make_review_sheet import SNAPSHOT, describe, problems  # noqa: E402

PORT = 8765
PAGE = Path(__file__).with_name("review_page.html")


def load(draft_path: Path) -> dict:
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    services = {s["serv_id"]: s for s in json.loads(SNAPSHOT.read_text(encoding="utf-8"))["data"]["welfare_services"]}
    policies = []
    for policy in draft["policies"]:
        service = services[policy["serv_id"]]
        source = "\n".join(t for t in (service["target_details"], service["selection_criteria"]) if t and t.strip())
        view = lambda c: {**c, "text": describe(c), "problems": problems(c, source)}
        paths = [{"id": "_common", "label": "모든 경로 공통", "kind": "공통",
                  "conditions": [view(c) for c in policy.get("common", [])], "checks": policy.get("common_checks", [])}]
        paths += [{**p, "conditions": [view(c) for c in p.get("conditions", [])], "checks": p.get("checks", [])}
                  for p in policy["paths"]]
        policies.append({"serv_id": policy["serv_id"], "name": policy["name"], "source": source,
                         "detail_url": service.get("detail_url") or "", "paths": paths,
                         "preferences": policy.get("preferences", [])})
    return {"batch": draft.get("batch"), "policies": policies}


def make_handler(draft_path: Path, result_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, content_type: str, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self._send(PAGE.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/data":
                saved = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
                data = {**load(draft_path), "review": saved, "result_file": result_path.name}
                self._send(json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            else:
                self._send(b"not found", "text/plain", 404)

        def do_POST(self):
            if self.path != "/api/save":
                return self._send(b"not found", "text/plain", 404)
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            result_path.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
            self._send(b'{"ok":true}', "application/json")

        def log_message(self, *args):
            pass

    return Handler


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 1
    draft_path = Path(argv[0]).resolve()
    result_path = draft_path.with_name(draft_path.stem.replace("_draft", "") + "_review.json")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), make_handler(draft_path, result_path))
    print(f"검수 화면: http://localhost:{PORT}  (결과 저장 → {result_path.name})")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
