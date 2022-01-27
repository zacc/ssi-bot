import pytest


from logic_mixin import LogicMixin


class TestTitleParsing():

	@pytest.mark.parametrize("test_input, expected",
		[('<|sols|><|sot|>The title text<|eot|><|sol|>', "The title text"),
		('<|soss|><|sot|>More title text<|eot|><|sost|>The selftext text<|', "More title text"),
		('<|sot|>This one will work<|', "This one will work"),
		('<|sot|>Return first title only<|eot|><|sot|>Second title<|eot|>', "Return first title only"),
		('<|sot|>This one should not work', None),
		('<|soss|><|sost|>The selftext<|', None)])
	def test_title_parsing(self, test_input, expected):

		logic = LogicMixin()
		returned_text = logic.extract_title_from_generated_text(test_input)
		assert returned_text == expected
