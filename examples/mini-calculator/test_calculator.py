import unittest

from calculator import add, divide, multiply


class CalculatorTest(unittest.TestCase):
    def test_adds_two_numbers(self):
        self.assertEqual(add(2, 3), 5)

    def test_divides_with_fractional_result(self):
        self.assertEqual(divide(7, 2), 3.5)

    def test_multiplies_two_numbers(self):
        self.assertEqual(multiply(4, 5), 20)


if __name__ == "__main__":
    unittest.main()
