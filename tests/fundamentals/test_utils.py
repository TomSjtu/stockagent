from __future__ import annotations

import unittest

from stockagent.fundamentals._utils import safe_divide


class SafeDivideTest(unittest.TestCase):
    def test_returns_quotient_for_two_values(self) -> None:
        self.assertEqual(safe_divide(12.0, 3.0), 4.0)

    def test_returns_none_when_numerator_is_missing(self) -> None:
        self.assertIsNone(safe_divide(None, 3.0))

    def test_returns_none_when_denominator_is_missing(self) -> None:
        self.assertIsNone(safe_divide(12.0, None))

    def test_returns_none_when_denominator_is_zero(self) -> None:
        self.assertIsNone(safe_divide(12.0, 0.0))


if __name__ == "__main__":
    unittest.main()
