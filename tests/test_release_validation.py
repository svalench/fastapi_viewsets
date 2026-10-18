"""Exercise the release version validator with literal, untrusted input."""
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.version_info < (3, 11), reason="Release workflow uses Python 3.11")
@pytest.mark.parametrize("requested,valid", [
    ("1.5.3", True), ("v1.5.3", True), ("1.5.2", False),
    ('$(touch injected)', False), ('1.5.3\nextra=value', False),
    ('"; touch injected; #', False),
])
def test_release_input_is_validated_as_data(tmp_path, requested, valid):
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/release.yml").read_text()
    script = workflow.split("python - <<'PYCODE'\n", 1)[1].split("          PYCODE", 1)[0]
    script = "\n".join(line[10:] for line in script.splitlines())
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.5.3"\n')
    output = tmp_path / "output"
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path,
                            env={**os.environ, "REQUESTED_VERSION": requested,
                                 "GITHUB_OUTPUT": str(output)}, capture_output=True, text=True)
    assert (result.returncode == 0) is valid
    assert not (tmp_path / "injected").exists()
    if valid:
        assert output.read_text() == "version=1.5.3\n"
    else:
        assert not output.exists()
