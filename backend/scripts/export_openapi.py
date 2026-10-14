"""Write the OpenAPI schema to backend/openapi.json (used to generate frontend types)."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("ENABLE_SCHEDULER", "false")

from app.main import create_app


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "openapi.json"
    out.write_text(json.dumps(create_app().openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
