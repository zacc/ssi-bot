#!/usr/bin/env python3
import json
import logging
import random
import re
import requests
import urllib.parse

from datetime import datetime

from bs4 import BeautifulSoup

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

	def _get_random_new_submission_tag(self):
		random.seed()
		random_value = random.random()

		if random_value < self._image_post_frequency:
			# Make a link (image) post
			return '<|sols|><|sot|>'
		else:
			# Make a text post
			return '<|soss|><|sot|>'

	def _collate_tagged_comment_history(self, praw_thing, to_level=6):
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

				if len(tagged_text + prefix) > 1500:
					# If the prefix becomes too long, the model text generation will break
					# Break the while loop here and just return whatever prefix we have
					break

				prefix = tagged_text + prefix

				# can't go any higher than a submission, so break the loop
				break

			elif isinstance(loop_thing, praw_Comment):
				# just a normal <|sor|>
				tagged_text = f'<|sor|>{loop_thing.body}<|eor|>'

				if len(tagged_text + prefix) > 1500:
					# If the prefix becomes too long, the model text generation will break
					# Break the while loop here and just return whatever prefix we have
					break

				prefix = tagged_text + prefix

			loop_thing = loop_thing.parent()
			counter += 1

		if prefix:
			# Compile a regex that will match the bot username,
			# then remove all instances from the text.
			# This will stop GPT-2 using the bot's name in generated text which looks wrong in a real context.
			regex = re.compile(re.escape(f"u/{self._praw.user.me().name}"), re.IGNORECASE)
			prefix = regex.sub('', prefix)

		if len(prefix) > 1500:
			# The model can handle 1024 tokens, but a token is not just one character.
			# Just truncate the long string to be safe and hope for the best :)
			return prefix[-1450:]

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
		elif praw_thing.author.name == 'AutoModerator':
			# It's the AutoModerator, just ignore this.
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

		# if the bot is mentioned, or its username is in the thing_text_content, reply 100%
		# Only an inbox message will have a type
		if getattr(praw_thing, 'type', '') == 'username_mention' or self._praw.user.me().name.lower() in thing_text_content.lower():
			return 1

		if isinstance(praw_thing, praw_Comment):
			# Find the depth of the comment
			if self._find_depth_of_comment(praw_thing) > 9:
				# don't reply to comments at > 9, to stop bots replying forever
				# and also to keep the bot's comments high up and visible
				return 0

		# From here we will start to calculate the probability cumulatively
		# Adjusting the weights here will change how frequently the bot will post
		# Try not to spam the sub too much and let other bots and humans have space to post
		base_probability = -0.2

		# Check the flair and username to see if the author might be a bot
		# 'Verified GPT-2 Bot' is only valid on r/subsimgpt2interactive
		# Sometimes author_flair_text will be present but None
		if 'verified gpt-2' in (getattr(praw_thing, 'author_flair_text', '') or '').lower()\
			or any(praw_thing.author.name.lower().endswith(i) for i in ['ssi', 'bot', 'gpt2']):
			# Reduce the reply probability by 10% to prioritise replying to humans
			base_probability += -0.1
		else:
			# assume humanoid if author metadata doesn't meet the criteria for a bot
			base_probability += 0.3

		if len(self._keyword_helper.positive_keyword_matches(thing_text_content)) > 0:
			# A positive keyword was found, increase probability of replying
			base_probability += 0.3

		if isinstance(praw_thing, praw_Submission):
			# it's a brand new submission and the bot can
			# comment at the top level and get some exposure..
			base_probability += 0.4

		if isinstance(praw_thing, praw_Comment):
			if praw_thing.parent().author == self._praw.user.me().name:
				# the post prior to this is by the bot
				base_probability += 0.1

			if any(kw.lower() in praw_thing.body.lower() for kw in ['?', ' you']):
				# any interrogative terms in the comment,
				# an increased reply probability
				base_probability += 0.3

			if praw_thing.submission.author == self._praw.user.me().name:
				# the submission is by the author, and favor that
				base_probability += 0.3

		# if the bot is mentioned, or its username is in the thing_text_content, reply 100%
		if getattr(praw_thing, 'type', '') == 'username_mention' or self._praw.user.me().name.lower() in thing_text_content.lower():
			base_probability = 1

		reply_probability = min(base_probability, 1)

		# work out the age of submission in hours
		age_of_submission = (datetime.utcnow() - submission_created_utc).total_seconds() / 3600
		# calculate rate of decay over 48 hours
		rate_of_decay = max(0, 1 - (age_of_submission / 48))
		# multiply the rate of decay by the reply probability
		return reply_probability * rate_of_decay

	def extract_reply_from_generated_text(self, prompt, generated_text, truncate):

		# remove any cruft
		generated_text = generated_text.replace('&amp;#x200B;\n', '')

		# find the first instance of the end-of-comment tag, starting from the end of the prompt
		index_of_truncate = generated_text.find(truncate, len(prompt))

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

	def extract_submission_text_from_generated_text(self, prompt, generated_text):

		return_dict = {}

		# remove any cruft
		generated_text = generated_text.replace('&amp;#x200B;\n', '')

		title_start_tag = '<|sot|>'
		title_end_tag = '<|eot|>'

		idx_title_start = generated_text.find(title_start_tag)
		idx_title_end = generated_text.find(title_end_tag)

		if idx_title_start == -1 or idx_title_end == -1:
			# There must be at least a complete title to make a submission
			return {}

		title = generated_text[idx_title_start + len(title_start_tag):idx_title_end]

		if not (0 < len(title) < 300):
			# Validate the title length is within reddit's range
			return {}

		# The title is ok, add it to the dict to return
		return_dict['title'] = title

		if generated_text.startswith('<|soss|>'):
			selftext_start_tag = '<|sost|>'
			selftext_end_tag = '<|eost|>'

			# Find the start and end tags of the main text, starting from the end of the title
			idx_selftext_start = generated_text.find(selftext_start_tag, idx_title_end)
			idx_selftext_end = generated_text.find(selftext_end_tag, idx_title_end)

			if idx_selftext_start == -1 or idx_selftext_end == -1:
				# Both tags should be found
				return {}

			print(idx_selftext_start, (idx_title_end + len(title_end_tag)))
			if idx_selftext_start != (idx_title_end + len(title_end_tag)):
				# check that the main text immediately follows the title end
				return {}

			return_dict['selftext'] = generated_text[idx_selftext_start + len(selftext_start_tag):idx_selftext_end]

		return return_dict

	def find_image_urls_for_search_string(self, search_string, limit=3):

		logging.info(f"Searching on Bing for an image for: \"{search_string}\"")

		return_list = []

		# Truncate to the first 10 words to improve effectiveness of the search
		search_terms = ' '.join(search_string.split()[:10])

		# If it exists, add the prefix to improve results
		if self._image_post_search_prefix:
			search_terms = self._image_post_search_prefix + ' ' + search_terms

		# Collect and encode all search url parameters
		search_parameters = {'q': search_terms,
							'FORM': 'HDRSC2',
							'safeSearch': 'strict'}

		encoded_search_parameters = urllib.parse.urlencode(search_parameters)
		search_url = "https://www.bing.com/images/search?" + encoded_search_parameters

		# Use Win10 Edge User Agent
		header = {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36 Edg/92.0.902.78"}

		r = requests.get(search_url, headers=header)

		if r.ok:
			soup = BeautifulSoup(r.text, 'html.parser')
			link_results = soup.find_all("a", {"class": "iusc"})

			for link in link_results:
				if link.has_attr('m'):
					# convert json in the link's attributes into a python dict
					m = json.loads(link["m"])
					if 'murl' in m:
						return_list.append(m['murl'])

		logging.info(f"Found {len(return_list)} images, returning top {limit}")
		return return_list[:limit]
