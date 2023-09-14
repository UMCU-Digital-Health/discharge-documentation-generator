"""Code for unit testing your functions"""
import pytest


@pytest.fixture
def sample_fixture():
    return 1


def test_sample(sample_fixture):
    assert sample_fixture == 1
