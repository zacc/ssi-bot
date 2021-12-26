#!/usr/bin/env python3

import logging
import random
import threading
import time
import regex as re

from configparser import ConfigParser
from datetime import datetime, timedelta

import praw
from praw.models import (Submission as praw_Submission, Comment as praw_Comment)

from logic_mixin import LogicMixin

from db import Thing as db_Thing
from peewee import fn


class RedditIO(threading.Thread, LogicMixin):
	"""
	Advised that praw can have problems with threads,
	so decided to keep all praw tasks in one daemon
	"""
	daemon = True
	name = "RedditIOThread"

	_praw = None

	_default_text_generation_parameters = {
			'max_length': 260,
			'num_return_sequences': 1,
			'prompt': None,
			'temperature': 0.8,
			'top_k': 40,
			'truncate': '<|eo',
	}

	_subreddit = 'test'
	_new_submission_flair_id = None
	_new_submission_frequency = timedelta(hours=0)
	_image_post_frequency = 0
	_image_post_search_prefix = ''

	# These hard-coded negative keywords are used to prevent the bot posting distasteful stuff.
	# It's only inteded as a basic defence.
	# Operator should train their model to avoid falling back on this.
	_default_negative_keywords = [
		('ar', 'yan'), ('ausch, witz'),
		('black', ' people'),
		('child p', 'orn'), ('concentrati', 'on camp'),
		('fag', 'got'),
		('hit', 'ler'), ('holo', 'caust'),
		('inc', 'est'), ('israel'),
		('jew', 'ish'), ('je', 'w'), ('je', 'ws'),
		(' k', 'ill'), ('kk', 'k'),
		('lol', 'i'),
		('maste', 'r race'), ('mus', 'lim'),
		('nation', 'alist'), ('na', 'zi'), ('nig', 'ga'), ('nig', 'ger'),
		('pae', 'do'), ('pale', 'stin'), ('ped', 'o'),
		('rac' 'ist'), (' r', 'ape'), ('ra', 'ping'),
		('sl', 'ut'), ('swas', 'tika'),
	]

	_positive_keywords = []
	_negative_keywords = ["".join(s) for s in _default_negative_keywords]

	def __init__(self):
		threading.Thread.__init__(self)

		# seed the random generator
		random.seed()

		self._config = ConfigParser()
		self._config.read('ssi-bot.ini')

		if self._config['DEFAULT']['positive_keywords']:
			self._positive_keywords = self._config['DEFAULT']['positive_keywords'].lower().split(',')
		if self._config['DEFAULT']['negative_keywords']:
			# Append user's custom negative keywords
			self._negative_keywords += self._config['DEFAULT']['negative_keywords'].lower().split(',')

		if self._config['DEFAULT']['subreddit']:
			self._subreddit = self._config['DEFAULT']['subreddit'].strip()
		else:
			logging.warning(f"Missing value of 'subreddit' in ini! Subreddit has been set to the default of r/{self._subreddit}!")

		if self._config['DEFAULT']['submission_flair_id']:
			self._new_submission_flair_id = self._config['DEFAULT']['submission_flair_id']
		else:
			logging.warning(f"Missing value of 'submission_flair_id' in ini! The flair ID has been set to the default of {self._new_submission_flair_id}!")

		if self._config['DEFAULT']['post_frequency']:
			self._new_submission_frequency = timedelta(hours=int(self._config['DEFAULT']['post_frequency']))
		else:
			logging.warning(f"Missing value of 'post_frequency' in ini! Post frequency has been set to the default of {self._new_submission_frequency}!")

		if self._config['DEFAULT']['image_post_frequency']:
			self._image_post_frequency = self._config['DEFAULT'].getfloat('image_post_frequency')
		else:
			logging.warning(f"Missing value of 'image_post_frequency' in ini! Image post frequency has been set to the default of {self._image_post_frequency}!")

		if self._config['DEFAULT']['image_post_search_prefix']:
			self._image_post_search_prefix = self._config['DEFAULT']['image_post_search_prefix']

		# start a reddit instance
		# this will automatically pick up the configuration from praw.ini
		self._praw = praw.Reddit(config_interpolation="basic")

	def run(self):

		# pick up incoming submissions, comments etc from reddit and submit jobs for them

		while True:
			logging.info(f"Beginning to process inbox stream")

			try:
				self.poll_inbox_stream()
			except:
				logging.exception("Exception occurred while processing the inbox streams")

			logging.info(f"Beginning to process incoming reddit streams")

			try:
				self.poll_incoming_streams()
			except:
				logging.exception("Exception occurred while processing the incoming streams")

			logging.info(f"Beginning to process outgoing post jobs")

			try:
				self.post_outgoing_reply_jobs()
			except:
				logging.exception("Exception occurred while processing the outgoing reply jobs")

			logging.info(f"Beginning to process outgoing new submission jobs")

			try:
				self.post_outgoing_new_submission_jobs()
			except:
				logging.exception("Exception occurred while processing the outgoing new submission jobs")

			try:
				if self._new_submission_frequency.seconds > 0:
					logging.info(f"Beginning to attempt to schedule a new submission")
					self.schedule_new_submission()
			except:
				logging.exception("Exception occurred while scheduling a new submission")

			time.sleep(120)

	def poll_inbox_stream(self):

		for praw_thing in self._praw.inbox.stream(pause_after=0):

			if praw_thing is None:
				break

			if isinstance(praw_thing, praw_Comment):

				record = self.is_praw_thing_in_database(praw_thing)

				if not record:
					logging.info(f"New {praw_thing.type} received in inbox, {praw_thing.id}")

					reply_probability = self.calculate_reply_probability(praw_thing)

					text_generation_parameters = None

					if random.random() < reply_probability:
						# It will generate a reply, so grab the parameters before we put it into the database
						text_generation_parameters = self.get_text_generation_parameters(praw_thing)

					# insert it into the database
					self.insert_praw_thing_into_database(praw_thing, text_generation_parameters)

				# mark the inbox item read
				praw_thing.mark_read()

	def poll_incoming_streams(self):

		# Setup all the streams for new comments and submissions
		sr = self._praw.subreddit(self._subreddit)
		submissions = sr.stream.submissions(pause_after=0)
		comments = sr.stream.comments(pause_after=0)

		# Merge the streams in a single loop to DRY the code
		for praw_thing in chain_listing_generators(submissions, comments):

			# Check in the database to see if it already exists
			record = self.is_praw_thing_in_database(praw_thing)

			# If the thing is already in the database then we've already calculated a reply for it.
			if not record:
				thing_label = 'comment' if isinstance(praw_thing, praw_Comment) else 'submission'
				logging.info(f"New {thing_label} thing received {praw_thing.name}")

				reply_probability = self.calculate_reply_probability(praw_thing)

				text_generation_parameters = None

				if random.random() < reply_probability:
					# It will generate a reply, so grab the parameters before we put it into the database
					text_generation_parameters = self.get_text_generation_parameters(praw_thing)

				# insert it into the database
				self.insert_praw_thing_into_database(praw_thing, text_generation_parameters)

	def get_text_generation_parameters(self, praw_thing):

		logging.info(f"Configuring a textgen job for {praw_thing.name}")

		prompt = self._collate_tagged_comment_history(praw_thing) + self._get_reply_tag(praw_thing)

		if prompt:
			# If a prompt was returned, we can go ahead and create the text generation parameters dict
			text_generation_parameters = self._default_text_generation_parameters.copy()
			text_generation_parameters['prompt'] = prompt

			return text_generation_parameters

	def post_outgoing_reply_jobs(self):

		for post_job in self.pending_reply_jobs():

			logging.info(f'Starting to post reply job {post_job.id} to reddit')

			# Increment the post attempts counter.
			# This is to prevent posting too many times if there are errors
			post_job.reddit_post_attempts += 1
			post_job.save()

			if len(self._negative_keyword_matches(post_job.generated_text)) > 0:
				# A negative keyword was found, so don't post this text back to reddit
				continue

			# Get the praw object of the original thing we are going to reply to
			source_praw_thing = None

			if post_job.source_name[:3] == 't1_':
				# Comment
				source_praw_thing = self._praw.comment(post_job.source_name[3:])
			elif post_job.source_name[:3] == 't3_':
				# Submission
				source_praw_thing = self._praw.submission(post_job.source_name[3:])

			if not source_praw_thing:
				# Couldn't get the source thing for some reason
				logging.error(f'Could not get the source praw thing for {post_job.id}')
				continue

			reply_parameters = self.extract_reply_from_generated_text(\
				post_job.text_generation_parameters['prompt'], post_job.generated_text, post_job.text_generation_parameters['truncate'])

			if not reply_parameters:
				logging.info(f"Reply body could not be found in generated text of job {post_job.id}")
				continue

			# Reply to the source thing with the generated text. A new praw_thing is returned
			reply_praw_thing = source_praw_thing.reply(**reply_parameters)

			# Add the new thing directly into the database,
			# without text_gen parameters so that a new reply won't be started
			self.insert_praw_thing_into_database(reply_praw_thing)

			# Set the name value of the reply that was posted, to finalize the job
			post_job.posted_name = reply_praw_thing.name
			post_job.save()

			logging.info(f"Job {post_job.id} reply submitted successfully")

	def post_outgoing_new_submission_jobs(self):

		for post_job in self.pending_new_submission_jobs():

			logging.info(f'Starting to post new submission job {post_job.id} to reddit')

			# Increment the post attempts counter.
			# This is to prevent posting too many times if there are errors
			post_job.reddit_post_attempts += 1
			post_job.save()

			generated_text = post_job.generated_text

			if len(self._negative_keyword_matches(generated_text)) > 0:
				# A negative keyword was found, so don't post this text back to reddit
				continue

			post_parameters = self.extract_submission_text_from_generated_text(\
				post_job.text_generation_parameters['prompt'], generated_text)

			if not post_parameters:
				logging.info(f"Submission text could not be found in generated text of job {post_job.id}")
				continue

			post_parameters['flair_id'] = self._new_submission_flair_id

			if generated_text.startswith('<|sols|>'):
				# Get a list of images that match the search string
				image_urls = self.find_image_urls_for_search_string(post_parameters['title'])

				if not image_urls:
					logging.info(f"Could not get any images for the submission: {post_parameters['title']}")
					continue

				for image_url in image_urls:
					post_parameters['url'] = image_url

					try:
						# Post the submission to reddit
						submission_praw_thing = self._praw.subreddit(post_job.subreddit).submit(**post_parameters)
						break

					except praw.exceptions.RedditAPIException as e:
						if 'DOMAIN_BANNED' in str(e):
							# continue and try again with another image_url
							continue
						# Otherwise raise the exception
						raise e

			elif generated_text.startswith('<|soss|>'):

				# Post the submission to reddit
				submission_praw_thing = self._praw.subreddit(post_job.subreddit).submit(**post_parameters)

			if not submission_praw_thing:
				# no submission has been made
				logging.info(f"Failed to make a submission for job {post_job.id}")
				continue

			post_job.posted_name = submission_praw_thing.name
			post_job.save()

			logging.info(f"Job {post_job.id} submission submitted successfully")

	def synchronize_bots_comments_submissions(self):
		# at first run, pick up Bot's own recent submissions and comments
		# to 'sync' the database and prevent duplicate replies

		submissions = self._praw.redditor(self._praw.user.me().name).submissions.new(limit=25)
		comments = self._praw.redditor(self._praw.user.me().name).comments.new(limit=200)

		for praw_thing in chain_listing_generators(submissions, comments):

			# if it's already in the database, do nothing
			record = self.is_praw_thing_in_database(praw_thing)

			if not record:
				logging.info(f"New thing in sync stream {praw_thing.name}")
				# Add the record into the database, with no chance of reply
				record = self.insert_praw_thing_into_database(praw_thing)

		logging.info("Completed syncing the bot's own submissions/comments")

	def is_praw_thing_in_database(self, praw_thing):
		# Note that this is using the prefixed reddit id, ie t3_, t1_
		# do not mix it with the unprefixed version which is called id!
		record = db_Thing.get_or_none(db_Thing.source_name == praw_thing.name)
		return record

	def insert_praw_thing_into_database(self, praw_thing, text_generation_parameters=None):
		record_dict = {}
		record_dict['source_name'] = praw_thing.name

		if text_generation_parameters:
			# If we want to generate a text reply, then include these parameters in the record
			record_dict['text_generation_parameters'] = text_generation_parameters

		return db_Thing.create(**record_dict)

	def schedule_new_submission(self):
		# Attempt to schedule a new submission
		# Check that one has not been completed or in the process of, before submitting

		# First, find all new submissions for this subreddit that fall within the new submission timeframe
		all_recent_new_submissions = (db_Thing.select(db_Thing).where(fn.Lower(db_Thing.subreddit) == self._subreddit.lower()).
					where(db_Thing.source_name == 't3_new_submission').
					where(db_Thing.created_utc > (datetime.utcnow() - self._new_submission_frequency)))

		# Extend the first query to filter successful submissions
		recent_successful_submissions = list(all_recent_new_submissions.where(db_Thing.posted_name.is_null(False)))

		if recent_successful_submissions:
			logging.info(f"A submission was made within the last {self._new_submission_frequency} on {self._subreddit}")
			return

		# Extend the first query to find ones that are still being processed and not yet submitted
		recent_pending_submissions = list(all_recent_new_submissions.where(db_Thing.posted_name.is_null()).
			where((db_Thing.text_generation_attempts < 3) & (db_Thing.reddit_post_attempts < 1)))

		if recent_pending_submissions:
			logging.info(f"A submission for {self._subreddit} is still being processed in the queue")
			return

		logging.info(f"Scheduling a new submission on {self._subreddit}")

		new_submission_thing = {}

		new_submission_thing['source_name'] = 't3_new_submission'
		new_submission_thing['subreddit'] = self._subreddit

		text_generation_parameters = self._default_text_generation_parameters.copy()
		text_generation_parameters['prompt'] = self._get_random_new_submission_tag()
		text_generation_parameters['max_length'] = 1000

		new_submission_thing['text_generation_parameters'] = text_generation_parameters

		return db_Thing.create(**new_submission_thing)

	def pending_reply_jobs(self):
		# A list of Comment reply Things from the database that have had text generated,
		# but not a reddit post attempt
		return list(db_Thing.select(db_Thing).
					where(db_Thing.source_name != 't3_new_submission').
					where(db_Thing.reddit_post_attempts < 1).
					where(db_Thing.generated_text.is_null(False)).
					where(db_Thing.posted_name.is_null()))

	def pending_new_submission_jobs(self):
		# A list of pending Submission Things from the database that have had text generated,
		# but not a reddit post attempt
		return list(db_Thing.select(db_Thing).
					where(db_Thing.source_name == 't3_new_submission').
					where(db_Thing.reddit_post_attempts < 1).
					where(db_Thing.generated_text.is_null(False)).
					where(db_Thing.posted_name.is_null()))

	def _find_depth_of_comment(self, praw_comment):
		"""
		Adapted from:
		https://praw.readthedocs.io/en/latest/code_overview/models/comment.html#praw.models.Comment.parent
		Loop back up the tree until reaching the root ancestor
		Returns integer representing the depth
		"""

		refresh_counter = 0
		# it's a 1-based index so init the counter with 1
		depth_counter = 1
		ancestor = praw_comment
		while not ancestor.is_root:
			depth_counter += 1
			ancestor = ancestor.parent()
			if refresh_counter % 9 == 0:
				try:
					ancestor.refresh()
				except praw.exceptions.ClientException:
					# An error can occur if a message is missing for some reason.
					# To keep the bot alive, return early.
					logging.exception("Exception when counting the comment depth. returning early.")
					return depth_counter

				refresh_counter += 1
		return depth_counter

	def _positive_keyword_matches(self, text):
		if self._positive_keywords:
			return [keyword for keyword in self._positive_keywords if re.search(r"\b{}\b".format(keyword), text, re.IGNORECASE)]
		return []

	def _negative_keyword_matches(self, text):
		if self._negative_keywords:
			return [keyword for keyword in self._negative_keywords if re.search(r"\b{}\b".format(keyword), text, re.IGNORECASE)]
		return []


def chain_listing_generators(*iterables):
	# Special tool for chaining PRAW's listing generators
	# It joins the three iterables together so that we can DRY
	for it in iterables:
		for element in it:
			if element is None:
				break
			else:
				yield element
