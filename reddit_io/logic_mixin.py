#!/usr/bin/env python3
import logging
import random
import re

from datetime import datetime

from praw.models import (Submission as praw_Submission, Comment as praw_Comment, Message as praw_Message)

from .tagging_mixin import TaggingMixin


class LogicMixin(TaggingMixin):
	"""
	This is not really a mixin..
	If just contains key functions that are paired with reddit_io.py
	It is abstracted so that users can customise their bot in this code
	while easily taking updates on reddit_io.py.
	"""

	_do_not_reply_bot_usernames = ['automoderator', 'reddit', 'profanitycounter']

	def _collate_tagged_comment_history(self, loop_thing, to_level=6, use_reply_sense=False):
		"""
		Loop backwards (upwards in reddit terms) from the praw_thing through the comment up x times,
		tagging the content text in the same way as the training data is
		The resulting string will be passed to the model to generate a reply to

		*This section is customisable for your own bot and how it has been finetuned*

		Each <|tag|> behaves as metadata so the model knows the general writing style of
		titles, replies and so forth.

		"""
		counter = 0
		prefix = ''

		while loop_thing and counter < to_level:

			if isinstance(loop_thing, praw_Submission):

				tagged_text = self.tag_submission(loop_thing, use_reply_sense)
				prefix = tagged_text + prefix

				# can't go any higher than a submission, so break the loop
				break

			elif isinstance(loop_thing, praw_Comment):
				# It's a comment
				tagged_text = self.tag_comment(loop_thing, use_reply_sense)
				prefix = tagged_text + prefix

				loop_thing = loop_thing.parent()

			elif isinstance(loop_thing, praw_Message):

				tagged_text = self.tag_message(loop_thing, use_reply_sense)
				prefix = tagged_text + prefix

				if loop_thing.parent_id:
					# Message's parent thing is read differently.
					loop_thing = self._praw.inbox.message(message_id=loop_thing.parent_id[3:])
				else:
					break

			counter += 1

		return prefix

	def remove_username_mentions_from_string(self, string, username):
		# Compile a regex that will match the bot username,
		# then remove all instances from the text.
		# This will stop GPT-2 using the bot's name in generated text which looks wrong in a real context.
		regex = re.compile(fr"u\/{username}(?!\|\>)", re.IGNORECASE)
		string = regex.sub('', string)
		return string

	def calculate_reply_probability(self, praw_thing):
		# Ths function contains all of the logic used for deciding whether to reply

		if not praw_thing.author:
			# If the praw_thing has been deleted the author will be None,
			# don't proceed to attempt a reply. Usually we will have downloaded
			# the praw_thing before it is deleted so this won't get hit often.
			return 0
		elif praw_thing.author.name.lower() == self._praw.user.me().name.lower():
			# The incoming praw object's author is the bot, so we won't reply
			return 0
		elif praw_thing.author.name.lower() in self._do_not_reply_bot_usernames:
			# Ignore comments/messages from Admins
			return 0

		# merge the text content into a single variable so it's easier to work with
		thing_text_content = ''
		submission_link_flair_text = ''
		submission_created_utc = None

		if isinstance(praw_thing, praw_Submission):
			# object is a submission that has title and selftext
			thing_text_content = f'{praw_thing.title} {praw_thing.selftext}'
			submission_link_flair_text = praw_thing.link_flair_text or ''
			submission_created_utc = datetime.utcfromtimestamp(praw_thing.created_utc)

		elif isinstance(praw_thing, praw_Comment):
			# otherwise it's a comment
			thing_text_content = praw_thing.body
			# navigate to the parent submission to get the link_flair_text
			submission_link_flair_text = praw_thing.submission.link_flair_text or ''
			submission_created_utc = datetime.utcfromtimestamp(praw_thing.submission.created_utc)

		elif isinstance(praw_thing, praw_Message):
			thing_text_content = praw_thing.body
			submission_created_utc = datetime.utcfromtimestamp(praw_thing.created_utc)

		# second most important thing is to check for a negative keyword
		# calculate whether negative keywords are in the text and return 0
		if len(self._keyword_helper.negative_keyword_matches(thing_text_content)) > 0:
			# The title or selftext/body contains negative keyword matches
			# and we will avoid engaging with negative content
			return 0

		# if the submission is flaired as a subreddit announcement,
		# do not reply so as to not spam the sub
		if submission_link_flair_text.lower() in ['announcement']:
			return 0

		# From here we will start to calculate the probability cumulatively
		# Adjusting the weights here will change how frequently the bot will post
		# Try not to spam the sub too much and let other bots and humans have space to post
		base_probability = self._base_reply_probability

		if isinstance(praw_thing, praw_Comment):
			# Find the depth of the comment
			comment_depth = self._find_depth_of_comment(praw_thing)
			if comment_depth > 12:
				# don't reply to deep comments, to prevent bots replying in a loop
				return 0
			else:
				# Reduce the reply probability x% for each level of comment depth
				# to keep the replies higher up
				base_probability -= ((comment_depth - 1) * self._comment_depth_reply_penalty)

		# Check the flair and username to see if the author might be a bot
		# 'Verified GPT-2 Bot' is only valid on r/subsimgpt2interactive
		# Sometimes author_flair_text will be present but None
		if 'verified gpt-2' in (getattr(praw_thing, 'author_flair_text', '') or '').lower()\
			or any(praw_thing.author.name.lower().endswith(i) for i in ['ssi', 'bot', 'gpt2']):
			# Adjust for when the author is a bot
			base_probability += self._bot_author_reply_boost
		else:
			# assume humanoid if author metadata doesn't meet the criteria for a bot
			base_probability += self._human_author_reply_boost

		if len(self._keyword_helper.positive_keyword_matches(thing_text_content)) > 0:
			# A positive keyword was found, increase probability of replying
			base_probability += self._positive_keyword_reply_boost

		if isinstance(praw_thing, praw_Submission):
			# it's a brand new submission.
			# This is mostly obsoleted by the depth penalty
			base_probability += self._new_submission_reply_boost

		if isinstance(praw_thing, praw_Comment):
			if praw_thing.parent().author == self._praw.user.me().name:
				# the post prior to this is by the bot
				base_probability += self._own_comment_reply_boost

			if any(kw.lower() in praw_thing.body.lower() for kw in ['?', ' you', 'what', 'how', 'when', 'why']):
				# any interrogative terms in the comment,
				# an increased reply probability
				base_probability += self._interrogative_reply_boost

			if praw_thing.submission.author == self._praw.user.me().name:
				# the submission is by the author, and favor that strongly
				base_probability += self._own_submission_reply_boost

		# if the bot is mentioned, or its username is in the thing_text_content, reply 100%
		if getattr(praw_thing, 'type', '') == 'username_mention' or\
			self._praw.user.me().name.lower() in thing_text_content.lower() or\
			isinstance(praw_thing, praw_Message):
			base_probability = self._message_mention_reply_probability

		reply_probability = min(base_probability, 1)

		# work out the age of submission in hours
		age_of_submission = (datetime.utcnow() - submission_created_utc).total_seconds() / 3600
		# calculate rate of decay over x hours
		rate_of_decay = max(0, 1 - (age_of_submission / 24))
		# multiply the rate of decay by the reply probability
		return round(reply_probability * rate_of_decay, 2)
