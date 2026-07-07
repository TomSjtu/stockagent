from __future__ import annotations

import io
import logging
import re
import sys
import unittest
from unittest.mock import patch

from stockagent.observability import get_logger, setup_logging


class ObservabilityTest(unittest.TestCase):
    def test_setup_logging_includes_second_precision_timestamp(self) -> None:
        stderr = io.StringIO()

        with patch.object(sys, "stderr", stderr):
            setup_logging("info")
            get_logger("stockagent.test").info("测试日志")

        self.assertRegex(
            stderr.getvalue(),
            re.compile(r"^\[INFO\] \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} 测试日志\n$"),
        )
        logging.getLogger().handlers.clear()


if __name__ == "__main__":
    unittest.main()
