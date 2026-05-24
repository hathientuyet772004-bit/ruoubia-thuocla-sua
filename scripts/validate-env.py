from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ["ADMIN_CENTER_SKIP_AUTO_VALIDATE"] = "1"

from apps.admin_center.backend.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Admin Center environment configuration.")
    parser.add_argument("--env-file", default=".env", help="Environment file to validate.")
    args = parser.parse_args()

    env_file = ROOT / args.env_file
    if not env_file.exists():
        print(f"Missing env file: {env_file}", file=sys.stderr)
        return 2

    try:
        config = Settings(_env_file=str(env_file))
        config.validate_production_config()
    except Exception as exc:
        print(f"Invalid environment config: {exc}", file=sys.stderr)
        return 1

    print(f"Environment config OK: {env_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
