import logging
import unittest

from apartment_agents.logging import get_logger, log_kv


class LoggingTest(unittest.TestCase):
    def test_log_kv_renders_sorted_key_value_fields(self) -> None:
        logger = get_logger("test")

        with self.assertLogs(logger, level=logging.INFO) as captured:
            log_kv(logger, logging.INFO, "event_name", buyer_id="b1", listing_id="l1")

        message = captured.output[0]
        self.assertIn("event_name", message)
        self.assertIn("buyer_id='b1'", message)
        self.assertIn("listing_id='l1'", message)


if __name__ == "__main__":
    unittest.main()
