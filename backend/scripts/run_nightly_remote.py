"""Runs the nightly scan against the live PythonAnywhere-hosted database by
downloading it, running the scan locally, then uploading the result back.

Why this exists: PythonAnywhere's free tier can't reliably run a 500+
ticker scan within its web-request timeout (confirmed: a synchronous
request against the full S&P 500 universe got killed by their load
balancer with a 504 before finishing), and its Scheduled/Always-on Tasks
are paid-only. GitHub Actions has no such single-request timeout for a
scheduled job, so it does the actual compute; this script is what bridges
that compute to PythonAnywhere's storage via their Files API (confirmed
working on the free tier: GET/POST/DELETE all tested successfully).

Intended to be run by .github/workflows/nightly-scan.yml on a schedule.

Required env vars:
  PA_USERNAME   -- PythonAnywhere username
  PA_API_TOKEN  -- PythonAnywhere API token (Account -> API Token tab)
  PA_DB_PATH    -- absolute path to scanner.db on PythonAnywhere,
                   e.g. /home/USERNAME/minervini-scanner/backend/scanner.db
"""
import os
from pathlib import Path

import requests

from app.config import seed_defaults
from app.db import get_engine
from pipeline.run_nightly import run

LOCAL_DB_PATH = Path("scanner_remote.db")


def _pa_url(username: str, remote_path: str) -> str:
    return f"https://www.pythonanywhere.com/api/v0/user/{username}/files/path{remote_path}"


def download(username: str, token: str, remote_path: str, local_path: Path) -> None:
    resp = requests.get(_pa_url(username, remote_path), headers={"Authorization": f"Token {token}"})
    resp.raise_for_status()
    local_path.write_bytes(resp.content)


def upload(username: str, token: str, remote_path: str, local_path: Path) -> None:
    with open(local_path, "rb") as f:
        resp = requests.post(
            _pa_url(username, remote_path),
            headers={"Authorization": f"Token {token}"},
            files={"content": f},
        )
    resp.raise_for_status()


def main() -> None:
    username = os.environ["PA_USERNAME"]
    token = os.environ["PA_API_TOKEN"]
    remote_db_path = os.environ["PA_DB_PATH"]

    print(f"Downloading {remote_db_path} from PythonAnywhere...")
    download(username, token, remote_db_path, LOCAL_DB_PATH)

    engine = get_engine(db_path=LOCAL_DB_PATH)
    seed_defaults(engine)
    print("Running nightly scan locally (this runner, not PythonAnywhere)...")
    run(engine)
    engine.dispose()  # release the file handle before re-reading it for upload

    print(f"Uploading updated database back to {remote_db_path}...")
    upload(username, token, remote_db_path, LOCAL_DB_PATH)
    print("Done.")


if __name__ == "__main__":
    main()
