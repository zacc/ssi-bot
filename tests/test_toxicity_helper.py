
import pytest

from utils.toxicity_helper import ToxicityHelper


class TestToxicityHelper():

	def test_assert_threshold_map(self):
		th = ToxicityHelper()
		assert list(th._threshold_map.values())

	def test_toxic_text(self):
		th = ToxicityHelper()
		th.text_above_toxicity_threshold("You are a cunt!")

	def test_non_toxic_text(self):
		th = ToxicityHelper()
		th.text_above_toxicity_threshold("Hello, I love you.")
