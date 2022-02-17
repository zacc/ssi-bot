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
