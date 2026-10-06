import unittest

from linked_stock_analysis import _futu_code, _yahoo_ticker, allowed_option_types


class LinkedStockAnalysisTests(unittest.TestCase):
    def test_hong_kong_ticker_mapping_matches_futu_and_yahoo(self):
        self.assertEqual(_futu_code("700"), "HK.00700")
        self.assertEqual(_yahoo_ticker("HK.00700"), "0700.HK")

    def test_bullish_and_bearish_ratings_select_one_short_side(self):
        self.assertEqual(allowed_option_types("Buy"), ["PUT"])
        self.assertEqual(allowed_option_types("Overweight"), ["PUT"])
        self.assertEqual(allowed_option_types("Underweight"), ["CALL"])
        self.assertEqual(allowed_option_types("Sell"), ["CALL"])

    def test_neutral_review_or_incomplete_analysts_fail_closed(self):
        self.assertEqual(allowed_option_types("Hold"), [])
        self.assertEqual(allowed_option_types("REVIEW"), [])
        self.assertEqual(allowed_option_types("Buy", reports_complete=False), [])


if __name__ == "__main__":
    unittest.main()
