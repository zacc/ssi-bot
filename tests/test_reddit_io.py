import pickle
import pytest

from reddit_io.reddit_io import *


class TestCanReplyToPrawThing():

	@pytest.mark.parametrize("pickle_path, expected",
		[('tests/pickles/comment_mod_removed.pkl', False),
		('tests/pickles/comment_user_deleted.pkl', False),
		('tests/pickles/submission_mod_removed.pkl', False),
		('tests/pickles/submission_spam_removed.pkl', False),
		('tests/pickles/submission_user_deleted.pkl', False),
		('tests/pickles/submission_locked.pkl', False),
		('tests/pickles/comment_submission_locked.pkl', False),
		('tests/pickles/submission_selftext.pkl', True),
		('tests/pickles/comment.pkl', True),
		])
	def test_can_reply_to_praw_thing(self, pickle_path, expected):

		fh = open(pickle_path, 'rb')
		thing = pickle.load(fh)

		result = RedditIO._can_reply_to_praw_thing(RedditIO, thing)
		assert result == expected
