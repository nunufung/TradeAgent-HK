import unittest

from telegram_stock_bot import parse_request


class TelegramStockBotTests(unittest.TestCase):
    def test_accepts_plain_hong_kong_stock_code(self):
        self.assertEqual(parse_request("700"), ("stock", "700"))
        self.assertEqual(parse_request("0005"), ("stock", "5"))

    def test_accepts_stock_command(self):
        self.assertEqual(parse_request("/stock 2800"), ("stock", "2800"))
        self.assertEqual(parse_request("/stock@TradeAgentBot 9988"), ("stock", "9988"))

    def test_help_and_invalid_inputs(self):
        self.assertEqual(parse_request("/help"), ("help", None))
        self.assertEqual(parse_request("/start"), ("help", None))
        self.assertEqual(parse_request("/stock"), ("invalid", None))
        self.assertEqual(parse_request("0"), ("invalid", None))
        self.assertEqual(parse_request("700 please"), ("invalid", None))
        self.assertEqual(parse_request("123456"), ("invalid", None))


if __name__ == "__main__":
    unittest.main()
