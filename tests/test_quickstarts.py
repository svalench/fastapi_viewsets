"""Exercise the published examples without substituting test-only app code."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = [
    ("README.md", "Quickstart (SQLAlchemy, sync)"),
    ("README.md", "Async quickstart (SQLAlchemy 2.x + Pydantic v2)"),
    ("docs/quickstart-sync.md", "Full example"),
    ("docs/quickstart-async.md", "Full example"),
    ("docs/index.md", "30-second example"),
]

CHECK_ENDPOINTS = """
from fastapi.testclient import TestClient

with TestClient(app) as client:
    response = client.get("/items")
    assert response.status_code == 200, response.text
    assert response.json() == []

    response = client.post("/items", json={"name": "apple"})
    assert response.status_code == 200, response.text
    item = response.json()
    assert isinstance(item["id"], int)
    assert item["name"] == "apple"
    url = f'/items/{item["id"]}'

    response = client.get(url)
    assert response.status_code == 200, response.text
    assert response.json() == item

    response = client.get("/items?limit=10&offset=0")
    assert response.status_code == 200, response.text
    assert response.json() == [item]

    response = client.patch(url, json={"name": "banana"})
    assert response.status_code == 200, response.text
    assert response.json() == {"id": item["id"], "name": "banana"}

    response = client.delete(url)
    assert response.status_code == 200, response.text
    assert response.json() == {"status": True, "text": "successfully deleted"}
    assert client.get(url).status_code == 404
    assert client.get("/items").json() == []

    response = client.get("/openapi.json")
    assert response.status_code == 200, response.text
    paths = response.json()["paths"]
    assert {"get", "post"} <= paths["/items"].keys()
    assert {"get", "patch", "delete"} <= paths["/items/{id}"].keys()
"""


@pytest.mark.parametrize(
    "filename,heading",
    EXAMPLES,
    ids=["readme-sync", "readme-async", "docs-sync", "docs-async", "docs-index"],
)
def test_quickstart(filename, heading, tmp_path):
    text = (ROOT / filename).read_text(encoding="utf-8")
    section = text.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]
    snippet = re.search(r"^```python\n(.*?)^```", section, flags=re.M | re.S)
    assert snippet is not None, f"No Python example in {filename}: {heading}"

    # A fresh process and directory prevent db_conf/ORMFactory caches, an
    # existing database, or a developer's .env from masking startup failures.
    # -I also prevents the source checkout from hiding a broken installed wheel.
    env = os.environ.copy()
    for key in (
        "ORM_TYPE",
        "DATABASE_URL",
        "SQLALCHEMY_DATABASE_URL",
        "SQLALCHEMY_ASYNC_DATABASE_URL",
    ):
        env.pop(key, None)
    # Execute checks in the same namespace, without running the example's
    # __main__ block (which would start a long-lived Uvicorn server).
    program = (
        "namespace = {'__name__': 'quickstart'}\n"
        f"exec(compile({snippet.group(1)!r}, {filename!r}, 'exec'), namespace)\n"
        f"exec({CHECK_ENDPOINTS!r}, namespace)\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", program],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
