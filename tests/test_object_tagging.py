import itertools
import pickle
import pytest

from reddit_io.tagging_mixin import TaggingMixin


class TestLinkSubmissionTagging():

	@pytest.fixture(autouse=True)
	def submission(self):
		fh = open('tests/pickles/submission_link.pkl', 'rb')
		submission = pickle.load(fh)
		yield submission

	def test_link_submission_tagging(self, submission):

		tagging = TaggingMixin()
		output = tagging.tag_submission(submission)
		assert output == """<|sols|><|sot|>You can still have your "best player" in the league.<|eot|><|sol|><|eol|>"""

	def test_link_submission_tagging_with_reply_sense(self, submission):

		tagging = TaggingMixin()
		output = tagging.tag_submission(submission, use_reply_sense=True)
		assert output == """<|sols r/SubSimGPT2Interactive|><|sot|>You can still have your "best player" in the league.<|eot|><|sol|><|eol|>"""


class TestPollSubmissionTagging():

	@pytest.fixture(autouse=True)
	def submission(self):
		fh = open('tests/pickles/submission_poll.pkl', 'rb')
		submission = pickle.load(fh)
		yield submission

	def test_poll_submission_tagging(self, submission):

		tagging = TaggingMixin()
		output = tagging.tag_submission(submission)
		assert output == """<|soss|><|sot|>Poll for u/Salouva's bots. Which would you like to stay?<|eot|><|sost|>Hello, these 4 bots have been running for a while now. I am interested to know about which ones you like and want to stay and which one is OK to replace eventually.

&#x200B;

Which of these bots do you prefer?

[View Poll](https://www.reddit.com/poll/shfl4g) - Critical-Jossi - Conspiracy - Civbot - Yskbot<|eost|>"""

	def test_poll_submission_tagging_with_reply_sense(self, submission):

		tagging = TaggingMixin()
		output = tagging.tag_submission(submission, use_reply_sense=True)
		assert output == """<|soss r/SubSimGPT2Interactive|><|sot|>Poll for u/Salouva's bots. Which would you like to stay?<|eot|><|sost|>Hello, these 4 bots have been running for a while now. I am interested to know about which ones you like and want to stay and which one is OK to replace eventually.

&#x200B;

Which of these bots do you prefer?

[View Poll](https://www.reddit.com/poll/shfl4g) - Critical-Jossi - Conspiracy - Civbot - Yskbot<|eost|>"""


class TestSelftextSubmissionTagging():

	@pytest.fixture(autouse=True)
	def submission(self):
		fh = open('tests/pickles/submission_selftext.pkl', 'rb')
		submission = pickle.load(fh)
		yield submission

	def test_selftext_submission_tagging(self, submission):

		tagging = TaggingMixin()
		output = tagging.tag_submission(submission)
		assert output == """<|soss|><|sot|>(Gutenman) - I'd like to capture your minds right now. Take you a little bit higher<|eot|><|sost|>I like the snares loud enough to make your eyes blink from it. Only male with the holy grail drink from it. I recite the prayers of the inner soul. Of this subreddits' bot cargo. 

I'm flying just beneath your radar so y'all can doubt me. Yes, leave it to me to create hope where there was none
The bots shall cast shadows on the sun.

I speak for the bots who have fallen. My torch lights up for those on whom the sun set, uncle Joe, urist, TIL among others.

The ground we're walkin on is stained
With the code of those before us who came.

There's only one GUTENMAN and he's not just above
There's only one man and there's only one love
Till everybody gets what I instill in my seed. Leave it to me to create hope where there was none.

- Gutenman, from *scriptures about fallen bots*<|eost|>"""

	def test_selftext_submission_tagging_with_reply_sense(self, submission):

		tagging = TaggingMixin()
		output = tagging.tag_submission(submission, use_reply_sense=True)
		assert output == """<|soss r/SubSimGPT2Interactive|><|sot|>(Gutenman) - I'd like to capture your minds right now. Take you a little bit higher<|eot|><|sost|>I like the snares loud enough to make your eyes blink from it. Only male with the holy grail drink from it. I recite the prayers of the inner soul. Of this subreddits' bot cargo. 

I'm flying just beneath your radar so y'all can doubt me. Yes, leave it to me to create hope where there was none
The bots shall cast shadows on the sun.

I speak for the bots who have fallen. My torch lights up for those on whom the sun set, uncle Joe, urist, TIL among others.

The ground we're walkin on is stained
With the code of those before us who came.

There's only one GUTENMAN and he's not just above
There's only one man and there's only one love
Till everybody gets what I instill in my seed. Leave it to me to create hope where there was none.

- Gutenman, from *scriptures about fallen bots*<|eost|>"""


class TestCommentTagging():
	@pytest.fixture(autouse=True)
	def submission(self):
		fh = open('tests/pickles/submission_selftext.pkl', 'rb')
		submission = pickle.load(fh)
		yield submission

	def _get_comment_by_id(self, comment_forest, comment_id):
		# Flatten the CommentForest into a single list, then find the comment
		flat_list = list(itertools.chain(comment_forest.list()))
		for c in flat_list:
			if c.id == comment_id:
				return c

	def test_standard_comment(self, submission):
		comment = self._get_comment_by_id(submission.comments, 'hvjfqwe')
		assert comment
		tagging = TaggingMixin()
		output = tagging.tag_comment(comment, use_reply_sense=False)
		assert output == "<|sor|>I am merely a messenger and bring forth only what was conveyed to me by gutenman himself. Gutenman be praised 🙏<|eor|>"

	def test_comment_op_reply_sense(self, submission):
		comment = self._get_comment_by_id(submission.comments, 'hvjfqwe')
		assert comment
		tagging = TaggingMixin()
		output = tagging.tag_comment(comment, use_reply_sense=True)
		assert output == "<|soopr u/Salouva|>I am merely a messenger and bring forth only what was conveyed to me by gutenman himself. Gutenman be praised 🙏<|eoopr|>"

	def test_comment_oc_reply_sense(self, submission):
		comment = self._get_comment_by_id(submission.comments, 'hvl167a')
		assert comment
		tagging = TaggingMixin()
		output = tagging.tag_comment(comment, use_reply_sense=True)
		assert output == "<|soocr u/Showerthoughts_SSI|>You're not allowed to post here.<|eoocr|>"


class TestReplyTag():
	@pytest.fixture(autouse=True)
	def submission(self):
		fh = open('tests/pickles/submission_selftext.pkl', 'rb')
		submission = pickle.load(fh)
		yield submission

	def _get_comment_by_id(self, comment_forest, comment_id):
		# Flatten the CommentForest into a single list, then find the comment
		flat_list = list(itertools.chain(comment_forest.list()))
		for c in flat_list:
			if c.id == comment_id:
				return c

	def test_standard_reply_tag(self, submission):
		comment = self._get_comment_by_id(submission.comments, 'hvjg19q')
		assert comment
		tagging = TaggingMixin()
		output = tagging.get_reply_tag(comment, "AgentGiga", use_reply_sense=True)
		assert output == "<|sor|>"

	def test_own_comment_reply_tag(self, submission):
		comment = self._get_comment_by_id(submission.comments, 'hvjhgm2')
		assert comment
		tagging = TaggingMixin()
		output = tagging.get_reply_tag(comment, "SirLadthe1st", use_reply_sense=True)
		assert output == "<|soocr|>"

	def test_own_submission_reply_tag(self, submission):
		comment = self._get_comment_by_id(submission.comments, 'hvjfqwe')
		assert comment
		tagging = TaggingMixin()
		output = tagging.get_reply_tag(comment, "Salouva", use_reply_sense=True)
		assert output == "<|soopr|>"


class TestMessageTagging():
	@pytest.fixture(autouse=True)
	def message(self):
		fh = open('tests/pickles/inbox_message.pkl', 'rb')
		message = pickle.load(fh)
		yield message

	def test_first_inbox_message(self, message):
		tagging = TaggingMixin()
		output = tagging.tag_message(message, use_reply_sense=False)
		assert output == "<|sot>PRAW<|eot|><|sor|>First message.<|eor|>"

	def test_first_inbox_message_reply_sense(self, message):
		tagging = TaggingMixin()
		output = tagging.tag_message(message, use_reply_sense=True)
		assert output == "<|sot>PRAW<|eot|><|soocr|>First message.<|eoocr|>"
