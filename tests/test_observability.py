from __future__ import annotations

import io
import logging
import re
import sys
import unittest
from unittest.mock import patch

from stockagent.observability import get_logger, setup_logging


class ObservabilityTest(unittest.TestCase):
    def tearDown(self) -> None:
        logging.getLogger().handlers.clear()
        logging.getLogger("httpx").setLevel(logging.NOTSET)
        logging.getLogger("edgar").setLevel(logging.NOTSET)

    def test_setup_logging_includes_second_precision_timestamp(self) -> None:
        stderr = io.StringIO()

        with patch.object(sys, "stderr", stderr):
            setup_logging("info")
            get_logger("stockagent.test").info("测试日志")

        self.assertRegex(
            stderr.getvalue(),
            re.compile(r"^\[INFO\] \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} 测试日志\n$"),
        )

    def test_info_logging_hides_third_party_info(self) -> None:
        stderr = io.StringIO()

        with patch.object(sys, "stderr", stderr):
            setup_logging("info")
            get_logger("stockagent.test").info("业务进度")
            get_logger("httpx").info("HTTP Request")
            get_logger("edgar.core").info("Identity configured")
            get_logger("edgar.core").warning("EDGAR warning")

        output = stderr.getvalue()
        self.assertIn("业务进度", output)
        self.assertNotIn("HTTP Request", output)
        self.assertNotIn("Identity configured", output)
        self.assertIn("EDGAR warning", output)

    def test_debug_logging_shows_httpx_info_but_hides_edgar_info(self) -> None:
        stderr = io.StringIO()

        with patch.object(sys, "stderr", stderr):
            setup_logging("debug")
            get_logger("httpx").info("HTTP Request")
            get_logger("edgar.entity.mappings_loader").info("Loaded mappings")

        output = stderr.getvalue()
        self.assertIn("[INFO]", output)
        self.assertIn("HTTP Request", output)
        self.assertNotIn("Loaded mappings", output)


if __name__ == "__main__":
    unittest.main()
