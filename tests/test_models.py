import unittest

from apartment_agents.models import ConfidenceScore


class ConfidenceScoreTest(unittest.TestCase):
    def test_rejects_out_of_range_values(self) -> None:
        with self.assertRaises(ValueError):
            ConfidenceScore(score=1.2)


if __name__ == "__main__":
    unittest.main()
