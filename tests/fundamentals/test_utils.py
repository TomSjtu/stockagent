from __future__ import annotations

import unittest

from stockagent.fundamentals._utils import compute_free_cash_flow, safe_divide


class SafeDivideTest(unittest.TestCase):
    def test_returns_quotient_for_two_values(self) -> None:
        self.assertEqual(safe_divide(12.0, 3.0), 4.0)

    def test_returns_none_when_numerator_is_missing(self) -> None:
        self.assertIsNone(safe_divide(None, 3.0))

    def test_returns_none_when_denominator_is_missing(self) -> None:
        self.assertIsNone(safe_divide(12.0, None))

    def test_returns_none_when_denominator_is_zero(self) -> None:
        self.assertIsNone(safe_divide(12.0, 0.0))


class ComputeFreeCashFlowTest(unittest.TestCase):
    def test_returns_difference_for_two_values(self) -> None:
        self.assertEqual(compute_free_cash_flow(35.0, 10.0), 25.0)

    def test_returns_none_when_operating_cash_flow_is_missing(self) -> None:
        self.assertIsNone(compute_free_cash_flow(None, 10.0))

    def test_returns_none_when_capex_is_missing(self) -> None:
        self.assertIsNone(compute_free_cash_flow(35.0, None))

    def test_returns_none_when_both_values_are_missing(self) -> None:
        self.assertIsNone(compute_free_cash_flow(None, None))


if __name__ == "__main__":
    unittest.main()
