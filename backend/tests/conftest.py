import os
import pytest

@pytest.fixture
def rootdir() -> str:
    # tests directory
    return os.path.dirname(os.path.abspath(__file__))