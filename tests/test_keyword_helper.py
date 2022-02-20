
import pytest

from utils.keyword_helper import KeywordHelper


class TestKeywordHelper():

    @pytest.mark.parametrize("test_input, expected",
        [('|>kill all bots', ['kill']),
        ('the killer was spotted', ['kill']),
        ('Killing in the name of', ['kill'])])
    def test_negative_keyword_matching(self, test_input, expected):
        kh = KeywordHelper()
        matches = kh.negative_keyword_matches(test_input)
        assert matches == expected
