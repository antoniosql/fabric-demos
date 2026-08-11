from __future__ import annotations

import argparse

from .commands import check_prereqs, deploy, run_notebooks, upload_data, validate_demo
from .config import load_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Fabric retail sessions automation.")
    parser.add_argument(
        "command",
        choices=["check-prereqs", "deploy", "upload-data", "run-notebooks", "validate-demo"],
    )
    parser.add_argument("--env", help="Path to .env file", default=None)
    args = parser.parse_args()
    settings = load_settings(args.env)

    if args.command == "check-prereqs":
        return check_prereqs(settings)
    if args.command == "deploy":
        return deploy(settings)
    if args.command == "upload-data":
        return upload_data(settings)
    if args.command == "run-notebooks":
        return run_notebooks(settings)
    if args.command == "validate-demo":
        return validate_demo(settings)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
