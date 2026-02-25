"""Export the FastAPI OpenAPI schema to openapi.json."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("CHAIN_NAME", "ethereum")

from src.server import app

schema = app.openapi()
output = Path(__file__).parent.parent / "openapi.json"
output.write_text(json.dumps(schema, indent=2))
sys.stdout.write(f"Written to {output}\n")
