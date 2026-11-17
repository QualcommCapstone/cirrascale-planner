"""Export the backend's OpenAPI schema with every contract model included.

FastAPI only lists models referenced by routes; the planning route streams NDJSON,
so we inject each contract model's JSON Schema into components.schemas. The result
feeds openapi-typescript in packages/contracts. Reproducible — never hand-edited.

Usage:
    uv run python scripts/export_openapi.py > ../../packages/contracts/openapi.json
"""

from __future__ import annotations

import json
import pathlib
import sys

# Make `app` importable no matter how the script is invoked.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402
from app.schemas import CONTRACT_MODELS  # noqa: E402


def build() -> dict:
    schema = app.openapi()
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    for model in CONTRACT_MODELS:
        js = model.model_json_schema(ref_template="#/components/schemas/{model}")
        # Nested models come back under $defs; hoist them to components.
        for name, definition in js.pop("$defs", {}).items():
            components.setdefault(name, definition)
        components[model.__name__] = js
    return schema


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
