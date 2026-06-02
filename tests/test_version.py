import tomllib
from pathlib import Path

import api2agent


def test_package_version_matches_project_metadata() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert api2agent.__version__ == pyproject["project"]["version"]
