"""共享 fixture：仓库根、schemas 目录、示例 case。"""

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def schemas_dir(repo_root: pathlib.Path) -> pathlib.Path:
    return repo_root / "schemas"


@pytest.fixture(scope="session")
def case_dir(repo_root: pathlib.Path) -> pathlib.Path:
    return repo_root / "examples" / "aapl-2026-04"
