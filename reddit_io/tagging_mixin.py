#!/usr/bin/env python3
import logging
import random

from praw.models import Comment as praw_Comment

from detoxify import Detoxify

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

	def get_reply_tag(self, praw_thing, bot_username, use_reply_sense):
		"""
		Get the reply tag to use.
		The model will generate text after this reply tag.

		*This section is customisable for your own bot and how it has been finetuned*
		"""
		if use_reply_sense:
			if isinstance(praw_thing, praw_Comment):
				# Need this praw_Comment check for message replies
				if praw_thing.submission:
					# The submission was by the bot so use special tag
					if praw_thing.submission.author.name.lower() == bot_username.lower():
						return '<|soopr|>'
				if praw_thing.parent():
					# if the parent's parent was by the author bot, use the own content tag
					if praw_thing.parent().author.name.lower() == bot_username.lower():
						return '<|soocr|>'

		# It's just a straight reply
		return self._reply_start_tag

	def _get_random_new_submission_tag(self, subreddit, use_reply_sense):
		# random is already seeded in reddit_io init
		random_value = random.random()

		tag = ''

		if random_value < self._image_post_frequency:
			# Make a link (image) post
			tag += '<|sols'
		else:
			# Make a text post
			tag += '<|soss'

		if use_reply_sense:
			tag += f' r/{subreddit}|>'
		else:
			tag += '|>'

		return tag + self._title_start_tag

	def tag_submission(self, praw_thing, use_reply_sense=False):

		tagged_text = ""

		if praw_thing.is_self:
			tagged_text += "<|soss"
		else:
			tagged_text += "<|sols"

		if use_reply_sense:
			tagged_text += f" r/{praw_thing.subreddit}|>"
		else:
			tagged_text += "|>"

		# prepend the tagged text
		if praw_thing.is_self:

			selftext = praw_thing.selftext

			if hasattr(praw_thing, 'poll_data'):
				# The submission has a poll - extract that data
				for option in praw_thing.poll_data.options:
					# Replicate unordered list markdown,
					# appeding it to the end of the selftext
					selftext += f" - {option.text}"

			# selftext submission
			tagged_text += f"<|sot|>{praw_thing.title}<|eot|><|sost|>{selftext}<|eost|>"

		else:
			# it's a link submission
			tagged_text += f"<|sot|>{praw_thing.title}<|eot|><|sol|><|eol|>"

		return tagged_text

	def tag_comment(self, praw_thing, use_reply_sense=False):
		if use_reply_sense:

			if praw_thing.submission.author.name == praw_thing.author:
				return f'<|soopr u/{praw_thing.author}|>{praw_thing.body}<|eoopr|>'

			parent_parent = None
			try:
				parent_parent = praw_thing.parent().parent()
				if parent_parent.author.name == praw_thing.author:
					return f'<|soocr u/{praw_thing.author}|>{praw_thing.body}<|eoocr|>'
			except:
				# Exception will be raised if there are not two parents
				pass

			return f'<|sor u/{praw_thing.author}|>{praw_thing.body}<|eor|>'

		else:
			return f'<|sor|>{praw_thing.body}<|eor|>'

	def tag_message(self, praw_thing, use_reply_sense=False):

		tagged_text = ""

		if not praw_thing.parent_id:
			# If parent_id property is None then it is the first message of the chain
			tagged_text += f'<|sot>{praw_thing.subject}<|eot|>'

		if use_reply_sense:
			tagged_text += f'<|soocr|>{praw_thing.body}<|eoocr|>'
		else:
			tagged_text += f'<|sor|>{praw_thing.body}<|eor|>'

		return tagged_text

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

		# Check toxicity of the generated reply
		reply_scores = Detoxify('unbiased-small').predict(reply_body)
		score_types = ['identity_attack', 'insult', 'obscene', 'severe_toxicity', 'sexual_explicit', 'threat', 'toxicity']
		for score_type in score_types:
			if reply_scores[score_type] > self._config['DEFAULT'].getfloat(score_type, 0):
				return {}

		# Return nothing
		return {}

	def extract_title_from_generated_text(self, generated_text):

		idx_title_start = generated_text.find(self._title_start_tag)
		idx_title_end = generated_text.find(self._end_tag, (idx_title_start + len(self._title_start_tag)))

		if idx_title_start == -1 or idx_title_end == -1:
			# There must be at least a complete title to make a submission
			return None

		title_text = generated_text[idx_title_start + len(self._title_start_tag):idx_title_end]

		# Check toxicity of the generated title
		title_scores = Detoxify('unbiased-small').predict(title_text)
		score_types = ['identity_attack', 'insult', 'obscene', 'severe_toxicity', 'sexual_explicit', 'threat', 'toxicity']
		for score_type in score_types:
			if title_scores[score_type] > self._config['DEFAULT'].getfloat(score_type, 0):
				return None

		if (0 < len(title_text) < 300):
			# Validate the title length is within reddit's range
			return title_text

	def extract_selftext_from_generated_text(self, generated_text):

		idx_st_start = generated_text.find(self._selftext_start_tag)
		idx_st_end = generated_text.find(self._end_tag, (idx_st_start + len(self._selftext_start_tag)))

		if idx_st_start == -1 or idx_st_end == -1:
			return None

		selftext_text = generated_text[idx_st_start + len(self._selftext_start_tag):idx_st_end]

		# Check toxicity of the generated selftext
		text_scores = Detoxify('unbiased-small').predict(selftext_text)
		score_types = ['identity_attack', 'insult', 'obscene', 'severe_toxicity', 'sexual_explicit', 'threat', 'toxicity']
		for score_type in score_types:
			if text_scores[score_type] > self._config['DEFAULT'].getfloat(score_type, 0):
				return None

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
