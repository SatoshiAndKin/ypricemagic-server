"""Export the FastAPI OpenAPI schema to openapi.json."""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os

os.environ.setdefault("CHAIN_NAME", "ethereum")

from src.server import app  # noqa: E402

schema = app.openapi()
output = Path(__file__).parent.parent / "openapi.json"
output.write_text(json.dumps(schema, indent=2))
print(f"Written to {output}")
