import itertools
import pickle
import pytest

from reddit_io.logic_mixin import LogicMixin


class TestCollateCommentHistory():

	@pytest.fixture(autouse=True)
	def submission(self):
		fh = open('tests/pickles/submission_poll.pkl', 'rb')
		submission = pickle.load(fh)
		yield submission

	def _get_comment_by_id(self, comment_forest, comment_id):
		# Flatten the CommentForest into a single list, then find the comment
		flat_list = list(itertools.chain(comment_forest.list()))
		for c in flat_list:
			if c.id == comment_id:
				return c

	def test_collation(self, submission):
		comment = self._get_comment_by_id(submission.comments, 'hv2dxaz')
		assert comment
		logic = LogicMixin()
		output = logic._collate_tagged_comment_history(comment, use_reply_sense=False)
		print(output)
		assert output == """<|soss|><|sot|>Poll for u/Salouva's bots. Which would you like to stay?<|eot|><|sost|>Hello, these 4 bots have been running for a while now. I am interested to know about which ones you like and want to stay and which one is OK to replace eventually.

&#x200B;

Which of these bots do you prefer?

[View Poll](https://www.reddit.com/poll/shfl4g) - Critical-Jossi - Conspiracy - Civbot - Yskbot<|eost|><|sor|>u/Conspiracy_GPT2 is my fav of the four for sure!<|eor|><|sor|>I feel that all four are OK<|eor|><|sor|>Sure, but you're the best.<|eor|>"""

	def test_collation_reply_sense(self, submission):
		comment = self._get_comment_by_id(submission.comments, 'hv2dxaz')
		assert comment
		logic = LogicMixin()
		output = logic._collate_tagged_comment_history(comment, use_reply_sense=True)
		print(output)
		assert output == """<|soss r/SubSimGPT2Interactive|><|sot|>Poll for u/Salouva's bots. Which would you like to stay?<|eot|><|sost|>Hello, these 4 bots have been running for a while now. I am interested to know about which ones you like and want to stay and which one is OK to replace eventually.

&#x200B;

Which of these bots do you prefer?

[View Poll](https://www.reddit.com/poll/shfl4g) - Critical-Jossi - Conspiracy - Civbot - Yskbot<|eost|><|sor u/Den_Hviide|>u/Conspiracy_GPT2 is my fav of the four for sure!<|eor|><|sor u/Conspiracy_GPT2|>I feel that all four are OK<|eor|><|soocr u/Den_Hviide|>Sure, but you're the best.<|eoocr|>"""

	def test_collation_length(self, submission):
		comment = self._get_comment_by_id(submission.comments, 'hv31ofu')
		assert comment
		logic = LogicMixin()
		output = logic._collate_tagged_comment_history(comment)
		assert len(output) < 1500

	def test_remove_mention(self, submission):
		comment = self._get_comment_by_id(submission.comments, 'hv2dxaz')
		assert comment
		logic = LogicMixin()
		output = logic._collate_tagged_comment_history(comment, use_reply_sense=True)

		cleaned_output = logic.remove_username_mentions_from_string(output, "Conspiracy_GPT2")
		print(cleaned_output)

		assert cleaned_output == """<|soss r/SubSimGPT2Interactive|><|sot|>Poll for u/Salouva's bots. Which would you like to stay?<|eot|><|sost|>Hello, these 4 bots have been running for a while now. I am interested to know about which ones you like and want to stay and which one is OK to replace eventually.

&#x200B;

Which of these bots do you prefer?

[View Poll](https://www.reddit.com/poll/shfl4g) - Critical-Jossi - Conspiracy - Civbot - Yskbot<|eost|><|sor u/Den_Hviide|> is my fav of the four for sure!<|eor|><|sor u/Conspiracy_GPT2|>I feel that all four are OK<|eor|><|soocr u/Den_Hviide|>Sure, but you're the best.<|eoocr|>"""
