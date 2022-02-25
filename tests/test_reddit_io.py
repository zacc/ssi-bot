import itertools
import pickle
import pytest

from reddit_io.reddit_io import *


class TestCanReplyToPrawThing():

	@pytest.mark.parametrize("pickle_path, expected",
		[('tests/pickles/comment_mod_removed.pkl', True),
		('tests/pickles/comment_user_deleted.pkl', True),
		('tests/pickles/submission_mod_removed.pkl', True),
		('tests/pickles/submission_spam_removed.pkl', True),
		('tests/pickles/submission_user_deleted.pkl', True),
		('tests/pickles/submission_locked.pkl', True),
		('tests/pickles/comment_submission_locked.pkl', True),
		('tests/pickles/submission_selftext.pkl', False),
		('tests/pickles/comment.pkl', False),
		])
	def test_can_reply_to_praw_thing(self, pickle_path, expected):

		fh = open(pickle_path, 'rb')
		thing = pickle.load(fh)

		result = RedditIO._is_praw_thing_removed_or_deleted(RedditIO, thing)
		assert result == expected


class TestReplyMatchesHisory():

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

	def test_reply_matches_history_positive(self, submission):

		comment = self._get_comment_by_id(submission.comments, 'hvl56vi')
		reply_body = "You are not allowed to post here."

		result = RedditIO._check_reply_matches_history(RedditIO, comment, reply_body)
		assert result == True

	def test_reply_matches_history_negative(self, submission):

		comment = self._get_comment_by_id(submission.comments, 'hvl56vi')
		reply_body = "Thank you lord Gutenman."

		result = RedditIO._check_reply_matches_history(RedditIO, comment, reply_body)
		assert result == False
