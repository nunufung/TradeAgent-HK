"""Publish only dashboard/space (public sanitized static files) to Hugging Face.

No private report, holdings, API prompt, account, or Futu OpenD data is uploaded.
Requires HF_TOKEN with write permission configured as a GitHub Actions secret.
"""
from pathlib import Path
import os
from huggingface_hub import HfApi

SPACE = "lewisf/tradeagent-hk-dashboard"
ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "dashboard/space"
ALLOWED = {
    "README.md", "index.html", "assets/app.js", "assets/style.css",
    "data/dashboard.json",
}


def main():
    token = os.getenv("HF_TOKEN", "").strip()
    if not token:
        raise SystemExit("HF_TOKEN missing: deployment is not authenticated.")
    files = {x.relative_to(FOLDER).as_posix() for x in FOLDER.rglob("*") if x.is_file()}
    if files != ALLOWED:
        raise SystemExit("Unexpected Space files or missing allowlisted files: refusing upload.")
    api = HfApi(token=token)
    api.create_repo(repo_id=SPACE, repo_type="space", space_sdk="static",
                    private=False, exist_ok=True)
    api.upload_folder(repo_id=SPACE, repo_type="space", folder_path=str(FOLDER),
                      commit_message="Update public TradeAgent-HK research dashboard")
    details = api.repo_info(repo_id=SPACE, repo_type="space")
    if details.id != SPACE:
        raise RuntimeError("Hugging Face Space identity mismatch.")
    print("Published sanitized static dashboard: https://huggingface.co/spaces/" + SPACE)


if __name__ == "__main__":
    main()
