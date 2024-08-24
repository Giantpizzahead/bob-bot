"""Example tests."""

import pytest


@pytest.mark.parametrize("a, b, expected", [(1, 2, 3), (-1, 1, 0), (-5, -2, -7)])
def test_addition(a: int, b: int, expected: int) -> None:
    """Test the addition operation.

    Args:
        a (int): The first operand.
        b (int): The second operand.
        expected (int): The expected result.

    Returns:
        None
    """
    assert a + b == expected
