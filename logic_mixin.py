#!/usr/bin/env python3

from datetime import datetime

from praw.models import (Submission as praw_Submission, Comment as praw_Comment)


class LogicMixin():
	"""
	This mixin contains all the logic for tagging comments,
	and replying to posts.
	It is abstracted so that users can update this code on their fork,
	while taking updates on the main classes.
	"""

	def _get_reply_tag(self, praw_thing):
		"""
		Get the reply tag to use.
		The model will generate text after this reply tag.

		*This section is customisable for your own bot and how it has been finetuned*
		"""

		# It's just a straight reply
		return '<|sor|>'

	def _collate_tagged_comment_history(self, praw_thing, to_level=3):
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
		loop_thing = praw_thing

		while loop_thing and counter < to_level:
			if isinstance(loop_thing, praw_Submission):

				# prepend the tagged text
				if loop_thing.is_self:
					# selftext submission
					tagged_text = f"<|soss|><|sot|>{loop_thing.title}<|eot|><|sost|>{loop_thing.selftext}<|eost|>"
				else:
					# it's a link submission
					tagged_text = f"<|sols|><|sot|>{loop_thing.title}<|eot|><|sol|>{loop_thing.selftext}<|eol|>"

				if len(tagged_text + prefix) > 3000:
					# If the prefix becomes too long, the model text generation will break
					# Break the while loop here and just return whatever prefix we have
					break

				prefix = tagged_text + prefix

				# can't go any higher than a submission, so break the loop
				break

			elif isinstance(loop_thing, praw_Comment):
				# just a normal <|sor|>
				tagged_text = f'<|sor|>{loop_thing.body}<|eor|>'

				if len(tagged_text + prefix) > 3000:
					# If the prefix becomes too long, the model text generation will break
					# Break the while loop here and just return whatever prefix we have
					break

				prefix = tagged_text + prefix

			loop_thing = loop_thing.parent()
			counter += 1

		return prefix

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

		# merge the text content into a single variable so it's easier to work with
		thing_text_content = ''
		submission_link_flair_text = ''
		submission_created_utc = None

		if praw_thing.type == 'submission':
			# object is a submission that has title and selftext
			thing_text_content = f'{praw_thing.title} {praw_thing.selftext}'
			submission_link_flair_text = praw_thing.link_flair_text or ''
			submission_created_utc = datetime.utcfromtimestamp(praw_thing.created_utc)

		elif praw_thing.type == 'comment':
			# otherwise it's a comment
			thing_text_content = praw_thing.body
			# navigate to the parent submission to get the link_flair_text
			submission_link_flair_text = praw_thing.submission.link_flair_text or ''
			submission_created_utc = datetime.utcfromtimestamp(praw_thing.submission.created_utc)

		# second most important thing is to check for a negative keyword
		# calculate whether negative keywords are in the text and return 0
		if len(self._negative_keyword_matches(thing_text_content)) > 0:
			# The title or selftext/body contains negative keyword matches
			# and we will avoid engaging with negative content
			return 0

		# if the submission is flaired as a subreddit announcement,
		# do not reply so as to not spam the sub
		if submission_link_flair_text.lower() in ['announcement']:
			return 0

		# if the bot is mentioned, or its username is in the thing_text_content, reply 100%
		if praw_thing.type == 'username_mention' or self._praw.user.me().name.lower() in thing_text_content:
			return 1

		if praw_thing.type == 'comment':
			# Find the depth of the comment
			if self._find_depth_of_comment(praw_thing) > 9:
				# don't reply to comments at > 9, to stop bots replying forever
				# and also to keep the bot's comments high up and visible
				return 0

		# From here we will start to calculate the probability cumulatively
		# Adjusting the weights here will change how frequently the bot will post
		# Try not to spam the sub too much and let other bots and humans have space to post
		base_probability = 0

		# cannot use ('bot' in flair) because of flairs that read 'bot operator' and so forth
		if (any(kw in (praw_thing.author_flair_text or '').lower() for kw in ['gpt-2'])
				or praw_thing.author.name.lower()[-3:] in ['ssi', 'bot']):
			# bot flair, or the last 3 characters of the author signify a bot
			base_probability += 0.01
		else:
			# assume humanoid if author metadata doesn't meet the criteria for a bot
			base_probability += 0.2

		if len(self._positive_keyword_matches(thing_text_content)) > 0:
			# A positive keyword was found, increase probability of replying
			base_probability += 0.3

		if praw_thing.type == 'submission':
			# it's a brand new submission and the bot can
			# comment at the top level and get some exposure..
			base_probability += 0.2

		if praw_thing.type == 'comment':
			if praw_thing.parent().author == self._praw.user.me().name:
				# the post prior to this is by the bot
				base_probability += 0.1

			if any(kw in praw_thing.body for kw in ['?', ' you']):
				# any interrogative terms in the comment,
				# an increased reply probability
				base_probability += 0.3

			if praw_thing.submission.author == self._praw.user.me().name:
				# the submission is by the author, and favor that
				base_probability += 0.1

		reply_probability = min(base_probability, 1)

		# work out the age of submission in hours
		age_of_submission = (datetime.utcnow() - submission_created_utc).total_seconds() / 3600
		# calculate rate of decay over 48 hours
		rate_of_decay = 1 - (age_of_submission / 48)
		# multiply the rate of decay by the reply probability
		return reply_probability * rate_of_decay
