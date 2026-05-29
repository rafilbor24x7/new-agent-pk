from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx


UPLOAD_URL = "https://new-agent-pk.onrender.com/admin/upload_esklp"
TIMEOUT_SECONDS = 120.0


def main() -> int:
    esklp_dir = os.getenv("ESKLP_DIR")
    admin_token = os.getenv("ADMIN_TOKEN")

    if not esklp_dir:
        print("ERROR: ESKLP_DIR is not set", file=sys.stderr)
        return 2
    if not admin_token:
        print("ERROR: ADMIN_TOKEN is not set", file=sys.stderr)
        return 2

    source_dir = Path(esklp_dir)
    if not source_dir.exists() or not source_dir.is_dir():
        print(f"ERROR: ESKLP_DIR is not a directory: {source_dir}", file=sys.stderr)
        return 2

    files = sorted(path for path in source_dir.glob("*.xlsx") if path.is_file())
    if not files:
        print(f"No .xlsx files found in {source_dir}")
        return 0

    print(f"Uploading {len(files)} .xlsx file(s) from {source_dir} to {UPLOAD_URL}")
    failures = 0

    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        for index, path in enumerate(files, start=1):
            print(f"[{index}/{len(files)}] {path.name} ... ", end="", flush=True)
            try:
                with path.open("rb") as file:
                    response = client.post(
                        UPLOAD_URL,
                        headers={"X-Admin-Token": admin_token},
                        files={
                            "file": (
                                path.name,
                                file,
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            )
                        },
                    )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                failures += 1
                print(f"FAILED HTTP {exc.response.status_code}: {exc.response.text}")
                continue
            except httpx.HTTPError as exc:
                failures += 1
                print(f"FAILED {exc}")
                continue
            except OSError as exc:
                failures += 1
                print(f"FAILED {exc}")
                continue

            try:
                payload = response.json()
            except ValueError:
                failures += 1
                print(f"FAILED invalid JSON response: {response.text}")
                continue

            saved = payload.get("saved", path.name)
            remote_path = payload.get("path", "")
            print(f"OK saved={saved} path={remote_path}")

    if failures:
        print(f"Done with {failures} failure(s).", file=sys.stderr)
        return 1

    print("Done. All files uploaded successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())