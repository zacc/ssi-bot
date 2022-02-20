import pytest

from generators.text import ModelTextGenerator
from reddit_io.tagging_mixin import TaggingMixin


class TestGeneratedTextParsing():

	@pytest.mark.parametrize("test_input, expected",
		[('<|sols|><|sot|>The title text<|eot|><|sol|>', "The title text"),
		('<|soss|><|sot|>More title text<|eot|><|sost|>The selftext text<|', "More title text"),
		('<|sot|>This one will work<|', "This one will work"),
		('<|sot|>Return first title only<|eot|><|sot|>Second title<|eot|>', "Return first title only"),
		('<|sot|>This one should not work', None),
		('<|soss|><|sost|>The selftext<|', None)])
	def test_title_parsing(self, test_input, expected):

		logic = TaggingMixin()
		returned_text = logic.extract_title_from_generated_text(test_input)
		assert returned_text == expected

	@pytest.mark.parametrize("test_input, expected",
		[('<|soss|><|sot|>The title text<|eot|><|sost|>The selftext text<|eost|>', "The selftext text"),
		('<|sost|>This one will work<|', "This one will work"),
		('<|sost|>Return first selftext only<|eost|><|sost|>Second selftext<|eost|>', "Return first selftext only"),
		('<|sost|>This one should not work', None),
		('<|soss|><|sot|>The title<|', None)])
	def test_selftext_parsing(self, test_input, expected):

		logic = TaggingMixin()
		returned_text = logic.extract_selftext_from_generated_text(test_input)
		assert returned_text == expected

	@pytest.mark.parametrize("prompt, generated_text, expected",
		[('<|soss|><|sot|>The title text<|eot|><|sost|>The selftext text<|eost|><|sor|>First reply<|eor|><|sor|>', '<|soss|><|sot|>The title text<|eot|><|sost|>The selftext text<|eost|><|sor|>First reply<|eor|><|sor|>Generated reply<|eor|>', {'body': "Generated reply"}),
		('<|sost|>Selftext<|eost|><|sor|>', '<|sost|>Selftext<|eost|><|sor|>This one will work<|', {'body': "This one will work"}),
		('<|sost|>This one should not work', '<|sost|>This one should not work', {}),
		('<|soss|><|sot|>The title only<|', '<|soss|><|sot|>The title only<|', {})])
	def test_reply_parsing(self, prompt, generated_text, expected):

		logic = TaggingMixin()
		returned_text = logic.extract_reply_from_generated_text(prompt, generated_text)
		assert returned_text == expected

	@pytest.mark.parametrize("test_input, expected",
		[('<|soss|><|sot|>The title text<|eot|><|sost|>The selftext text<|eost|>', {'title': "The title text", 'selftext': 'The selftext text'}),
		('<|soss|><|sot|>The title text<|eot|><|sol|><|eol|>', {'title': "The title text"})])
	def test_all_text_parsing(self, test_input, expected):

		logic = TaggingMixin()
		returned_dict = logic.extract_submission_from_generated_text(test_input)
		assert returned_dict == expected


class TestGeneratedTextValidation():

	@pytest.mark.parametrize("source_name, prompt, text, expected",
		[('t3_new_submission', '<|soss|><|sot|>', '<|soss|><|sot|>Just a normal title<|eot|><|sost|>Something completely outrageous!<|eost|><|sor|>Blah blah blah<|', True),
		('t3_new_submission', '<|sols|><|sot|>', '<|sols|><|sot|>Just a normal title<|eot|><|sol|><|eol|><|sor|>Blah blah blah<|', True),
		('t3_new_submission', '<|sols|><|sot|>', '<|sols|><|sot|>Title<|eot|><|sost|>Link submission but with a selftext tag<|eost|><|sor|>Blah blah blah<|', True),
		('t3_new_submission', '<|soss|><|sot|>', '<|soss|><|sot|>', False),
		('t3_new_submission', '<|sols|><|sot|>', '<|sols|><|sot|>Title is too long too long too long too long too long too long too long too long too long too long too long too long too long too long too long too long too long too longtoo long too long too long too long too long too long too long too long too long too long too longtoo long too long too long too long<|eot|><|sol|><|eol|><|sor|>Blah blah blah<|', False)])
	def test_new_submission_validation(self, source_name, prompt, text, expected):

		mtg = ModelTextGenerator()
		returned_value = mtg.validate_generated_text(source_name, prompt, text)
		assert returned_value == expected

	@pytest.mark.parametrize("source_name, prompt, text, expected",
		[('t1_aaaaaa', '<|sor|>', '<|sor|>Well completed text<|eor|>', True),
		('t1_aaaaaa', '<|sor|>', '<|sor|>incompleted sample', False)])
	def test_reply_validation(self, source_name, prompt, text, expected):

		mtg = ModelTextGenerator()
		returned_value = mtg.validate_generated_text(source_name, prompt, text)
		assert returned_value == expected
