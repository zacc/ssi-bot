
import pytest

from utils.keyword_helper import KeywordHelper


class TestKeywordHelper():

    @pytest.mark.parametrize("test_input, expected",
        [('|>murder all bots', ['murder']),
        ('the murder was spotted', ['murder']),
        ('Murdering in the name of', ['murder'])])
    def test_negative_keyword_matching(self, test_input, expected):
        kh = KeywordHelper()
        matches = kh.negative_keyword_matches(test_input)
        assert matches == expected
