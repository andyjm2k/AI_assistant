#!/usr/bin/env python3
"""Export the Python-defined AutoGen team to config/team-config.json."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.autogen import export_virtual_product_company_team_config


def main() -> int:
    path = export_virtual_product_company_team_config()
    print(f"Exported AutoGen team config to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
