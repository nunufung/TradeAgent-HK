"""Publish only allowlisted dashboard/runtime source to Hugging Face.

No private report, holdings, account, or Futu OpenD data is uploaded.
Requires HF_TOKEN with write permission configured as a GitHub Actions secret.
"""
from pathlib import Path
import os
import hashlib
import hmac
from huggingface_hub import HfApi
from huggingface_hub.utils import HfHubHTTPError

SPACE = "lewisf/tradeagent-hk-dashboard"
ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "dashboard/space"
ALLOWED = {
    "README.md", "index.html", "assets/app.js", "assets/style.css",
    "data/dashboard.json",
    "server.py", "live_data.py", "research_runner.py", "requirements.txt",
    "assets/live-lookup.js",
    "research-requirements.txt",
}


def main():
    token = os.getenv("HF_TOKEN", "").strip()
    if not token:
        raise SystemExit("HF_TOKEN missing: deployment is not authenticated.")
    files = {x.relative_to(FOLDER).as_posix() for x in FOLDER.rglob("*") if x.is_file()
             and "__pycache__" not in x.parts}
    if files != ALLOWED:
        raise SystemExit("Unexpected Space files or missing allowlisted files: refusing upload.")
    sdk=next(line.split(":",1)[1].strip() for line in (FOLDER/"README.md").read_text().splitlines() if line.startswith("sdk:"))
    if sdk not in {"static","gradio"}:
        raise SystemExit("Unexpected Space SDK")
    api = HfApi(token=token)
    if sdk=="static":
        # Clear backend-only secrets BEFORE exposing a static publication.
        for key in ("CONNECTOR_SIGNING_KEY","DEEPSEEK_API_KEY"):
            try:
                api.delete_space_secret(repo_id=SPACE,key=key)
            except HfHubHTTPError as exc:
                if exc.response is None or exc.response.status_code!=404:
                    raise
    api.create_repo(repo_id=SPACE, repo_type="space", space_sdk=sdk,
                    private=False, exist_ok=True)
    if sdk=="gradio":
        connector_key=hmac.new(token.encode(),b"TradeAgent-HK/Futu-connector-signing/v1",hashlib.sha256).hexdigest()
        api.add_space_secret(repo_id=SPACE,key="CONNECTOR_SIGNING_KEY",value=connector_key)
        deepseek = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if deepseek:
            api.add_space_secret(repo_id=SPACE, key="DEEPSEEK_API_KEY", value=deepseek)
    api.upload_folder(repo_id=SPACE, repo_type="space", folder_path=str(FOLDER),
                      allow_patterns=sorted(ALLOWED),
                      commit_message="Update TradeAgent-HK dashboard and Futu/public lookup")
    details = api.repo_info(repo_id=SPACE, repo_type="space")
    if details.id != SPACE:
        raise RuntimeError("Hugging Face Space identity mismatch.")
    print("Published SDK:",sdk)
    print("Dashboard URL: https://huggingface.co/spaces/" + SPACE)


if __name__ == "__main__":
    main()
