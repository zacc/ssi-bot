#!/usr/bin/env python3
import logging
import random


class TaggingMixin():
	"""
	This mixin contains all the logic for tagging comments,
	It is abstracted so that users can update this code on their fork,
	while taking updates on the main classes.
	"""

	_link_submission_start_tag = '<|sols|>'
	_selftext_submission_start_tag = '<|soss|>'

	_title_start_tag = '<|sot|>'
	_selftext_start_tag = '<|sost|>'

	_reply_start_tag = '<|sor|>'
	_reply_end_tag = '<|eor|>'

	_end_tag = '<|'

	def _get_reply_tag(self, praw_thing):
		"""
		Get the reply tag to use.
		The model will generate text after this reply tag.

		*This section is customisable for your own bot and how it has been finetuned*
		"""

		# It's just a straight reply
		return self._reply_start_tag

	def _get_random_new_submission_tag(self):
		# random is already seeded in reddit_io init
		random_value = random.random()

		if random_value < self._image_post_frequency:
			# Make a link (image) post
			return self._link_submission_start_tag + self._title_start_tag
		else:
			# Make a text post
			return self._selftext_submission_start_tag + self._title_start_tag

	def extract_reply_from_generated_text(self, prompt, generated_text):

		# remove any cruft
		generated_text = generated_text.replace('&amp;#x200B;\n', '')

		# find the first instance of the end-of-comment tag, starting from the end of the prompt
		index_of_truncate = generated_text.find(self._end_tag, len(prompt))

		if index_of_truncate == -1:
			# the original truncate tag couldn't be found,
			# but we'll still try and truncate the string at the last line break (end of paragraph)
			# so that the text still looks clean.
			index_of_truncate = generated_text.rfind("\\n")

		if index_of_truncate == -1:
			# in case trained model do not output tags and put lot !!!!! at the end,
			# This change allows this messages without need of end tags
			index_of_truncate = generated_text.find("!!!!")

		if index_of_truncate == -1:
			# still nothing could be found so just skip this one
			# if this is hit often, increase the length of the generated text
			logging.info("Truncate string not found")
			return {}

		# extract the text from between the prompt and the truncate point
		reply_body = generated_text[len(prompt):index_of_truncate]
		if reply_body:
			return {'body': reply_body}

		# Return nothing
		return {}

	def extract_title_from_generated_text(self, generated_text):

		idx_title_start = generated_text.find(self._title_start_tag)
		idx_title_end = generated_text.find(self._end_tag, (idx_title_start + len(self._title_start_tag)))

		if idx_title_start == -1 or idx_title_end == -1:
			# There must be at least a complete title to make a submission
			return None

		title_text = generated_text[idx_title_start + len(self._title_start_tag):idx_title_end]

		if (0 < len(title_text) < 300):
			# Validate the title length is within reddit's range
			return title_text

	def extract_selftext_from_generated_text(self, generated_text):

		idx_st_start = generated_text.find(self._selftext_start_tag)
		idx_st_end = generated_text.find(self._end_tag, (idx_st_start + len(self._selftext_start_tag)))

		if idx_st_start == -1 or idx_st_end == -1:
			return None

		selftext_text = generated_text[idx_st_start + len(self._selftext_start_tag):idx_st_end]
		return selftext_text

	def extract_submission_from_generated_text(self, generated_text):

		return_dict = {}

		# remove any cruft
		generated_text = generated_text.replace('&amp;#x200B;\n', '')

		title = self.extract_title_from_generated_text(generated_text)

		if not title:
			return {}
		else:
			# The title is ok, add it to the dict to return
			return_dict['title'] = title

		selftext = self.extract_selftext_from_generated_text(generated_text)

		if selftext:
			return_dict['selftext'] = selftext

		return return_dict
