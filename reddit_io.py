#!/usr/bin/env python3

import logging
import random
import threading
import time
import regex as re
import difflib
from configparser import ConfigParser
from datetime import datetime, timedelta

import praw
from praw.models import (Submission as praw_Submission, Comment as praw_Comment, Message as praw_Message)

from logic_mixin import LogicMixin

from db import Thing as db_Thing
from peewee import fn
from keyword_helper import KeywordHelper


class RedditIO(threading.Thread, LogicMixin):
	"""
	Advised that praw can have problems with threads,
	so decided to keep all praw tasks in one daemon
	"""
	daemon = True

	_praw = None

	_default_text_generation_parameters = {
			'max_length': 260,
			'num_return_sequences': 1,
			'prompt': None,
			'temperature': 0.8,
			'top_k': 40,
	}

	_default_image_generation_parameters = {
		'type': 'scraper',
		'prompt': None,
	}

	_subreddit_flair_id_map = {}
	_new_submission_schedule = []

	def __init__(self, bot_username):
		threading.Thread.__init__(self)

		self._bot_username = bot_username

		# daemon Thread for logging
		self.name = f"{self._bot_username}_io"

		# seed the random generator
		random.seed()

		self._config = ConfigParser()
		self._config.read('ssi-bot.ini')

		self._keyword_helper = KeywordHelper(self._bot_username)

		subreddits_config_string = self._config[self._bot_username].get('subreddits', 'test')
		self._subreddits = [x.strip() for x in subreddits_config_string.lower().split(',')]

		logging.info(f"Bot will reply to comments on subreddits: {', '.join(self._subreddits)}.")

		subreddit_flair_id_string = self._config[self._bot_username].get('subreddit_flair_id_map', '')
		if subreddit_flair_id_string != '':
			self._subreddit_flair_id_map = {y[0].lower().strip(): y[1].strip() for y in [x.split('=') for x in subreddit_flair_id_string.split(',')]}

		new_submission_schedule_string = self._config[self._bot_username].get('new_submission_schedule', '')
		if new_submission_schedule_string != '':
			self._new_submission_schedule = [(y[0].lower().strip(), int(y[1])) for y in [x.split('=') for x in new_submission_schedule_string.split(',')]]
			logging.info(f"New submission schedule: {self._new_submission_schedule}")

		self._image_post_frequency = self._config[self._bot_username].getfloat('image_post_frequency', 0)
		logging.info(f"Image post frequency has been set to {(self._image_post_frequency * 100)}%.")

		self._image_post_search_prefix = self._config[self._bot_username].get('image_post_search_prefix', None)

		self._set_nsfw_flair_on_submissions = self._config[self._bot_username].getboolean('set_nsfw_flair_on_submissions', False)

		self._inbox_replies_enabled = self._config[self._bot_username].getboolean('enable_inbox_replies', False)

		self._submission_image_generator = self._config[self._bot_username].get('submission_image_generator', 'scraper')

		if self._submission_image_generator == 'scraper':
			# TODO import the parameters from scraper
			pass

		# start a reddit instance
		# this will automatically pick up the configuration from praw.ini
		self._praw = praw.Reddit(self._bot_username)

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
				for post_job in self.pending_reply_jobs():
					self.post_outgoing_reply_jobs(post_job)
			except:
				logging.exception("Exception occurred while processing the outgoing reply jobs")

			logging.info(f"Beginning to process outgoing new submission jobs")

			try:
				for post_job in self.pending_new_submission_jobs():
					self.post_outgoing_new_submission_jobs(post_job)
			except:
				logging.exception("Exception occurred while processing the outgoing new submission jobs")

			try:
				logging.info(f"Beginning to attempt to schedule a new submission")

				for subreddit, frequency in self._new_submission_schedule:
					self.schedule_new_submission(subreddit, frequency)
			except:
				logging.exception("Exception occurred while scheduling a new submission")

			time.sleep(120)

	def poll_inbox_stream(self):

		for praw_thing in self._praw.inbox.stream(pause_after=0):

			if praw_thing is None:
				break

			if isinstance(praw_thing, praw_Message) and not self._inbox_replies_enabled:
				# Skip if it's an inbox message and replies are disabled
				continue

			record = self.is_praw_thing_in_database(praw_thing)

			if not record:
				logging.info(f"New message received in inbox, {praw_thing.id}")

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
		sr = self._praw.subreddit('+'.join(self._subreddits))
		submissions = sr.stream.submissions(pause_after=0)
		comments = sr.stream.comments(pause_after=0)

		# Merge the streams in a single loop to DRY the code
		for praw_thing in chain_listing_generators(submissions, comments):

			# Check in the database to see if it already exists
			record = self.is_praw_thing_in_database(praw_thing)

			# If the thing is already in the database then we've already calculated a reply for it.
			if not record:
				thing_label = 'comment' if isinstance(praw_thing, praw_Comment) else 'submission'
				logging.info(f"New {thing_label} thing received {praw_thing.name} from {praw_thing.subreddit}")

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

	def post_outgoing_reply_jobs(self, post_job):

		bypass_finally = False

		try:
			logging.info(f'Starting to post reply job {post_job.id} to reddit')

			# Get the praw object of the original thing we are going to reply to
			source_praw_thing = None

			if post_job.source_name[:3] == 't1_':
				# Comment
				source_praw_thing = self._praw.comment(post_job.source_name[3:])
			elif post_job.source_name[:3] == 't3_':
				# Submission
				source_praw_thing = self._praw.submission(post_job.source_name[3:])
			elif post_job.source_name[:3] == 't4_':
				# Inbox message
				source_praw_thing = self._praw.inbox.message(post_job.source_name[3:])

			if not source_praw_thing:
				# Couldn't get the source thing for some reason
				logging.error(f'Could not get the source praw thing for {post_job.id}')
				return

			reply_parameters = self.extract_reply_from_generated_text(\
				post_job.text_generation_parameters['prompt'], post_job.generated_text)

			if not reply_parameters:
				logging.info(f"Reply body could not be found in generated text of job {post_job.id}")
				return

			# Begin to check whether the generated matches the text the bot is replying to.
			# The model can get fixated on repeating words and it looks bad.

			# First, capture the text we want to compare
			source_text_to_compare = None

			if isinstance(source_praw_thing, praw_Submission):
				# On a submission we'll only check the title
				source_text_to_compare = source_praw_thing.title
			elif isinstance(source_praw_thing, praw_Comment) or isinstance(source_praw_thing, praw_Message):
				source_text_to_compare = source_praw_thing.body

			if source_text_to_compare and reply_parameters['body'] and\
				difflib.SequenceMatcher(None, source_text_to_compare.lower(), reply_parameters['body'].lower()).ratio() > 0.95:
				# The generated text is 95% similar to the previous comment (ie it's a boring duplicate)
				logging.info(f"Job {post_job.id} had duplicated generated text.")

				bypass_finally = True
				# Clear the generated text on the post_job
				# then it can try to re-generate it with a new random seed
				post_job.generated_text = None
				post_job.save()
				return

			# Reply to the source thing with the generated text. A new praw_thing is returned
			reply_praw_thing = source_praw_thing.reply(**reply_parameters)

			# Add the new thing directly into the database,
			# without text_gen parameters so that a new reply won't be started
			self.insert_praw_thing_into_database(reply_praw_thing)

			# Set the name value of the reply that was posted, to finalize the job
			post_job.posted_name = reply_praw_thing.name
			post_job.save()

			logging.info(f"Job {post_job.id} reply submitted successfully")
		except Exception as e:
			logging.exception(e)

		finally:
			if not bypass_finally:
				# Increment the post attempts counter.
				# This is to prevent posting too many times if there are errors
				post_job.reddit_post_attempts += 1
				post_job.save()

	def post_outgoing_new_submission_jobs(self, post_job):

		bypass_finally = False

		try:
			logging.info(f'Starting to post new submission job {post_job.id} to reddit')

			generated_text = post_job.generated_text

			post_parameters = self.extract_submission_from_generated_text(generated_text)

			if not post_parameters:
				logging.info(f"Submission text could not be found in generated text of job {post_job.id}")
				return

			if post_job.generated_image_path:
				# If an image has been generated for this job

				if post_job.generated_image_path.startswith('http'):
					# it's actually a HTTP url
					post_parameters['url'] = post_job.generated_image_path
				else:
					# Otherwise assume it's on the file system and we can upload it to reddit
					post_parameters['image_path'] = post_job.generated_image_path

			post_parameters['flair_id'] = self._subreddit_flair_id_map.get(post_job.subreddit.lower(), None)

			if 'image_path' in post_parameters:
				submission_praw_thing = self._praw.subreddit(post_job.subreddit).submit_image(**post_parameters, nsfw=self._set_nsfw_flair_on_submissions)

			else:
				# Sometimes url links posted are banned by reddit.
				# It will raise a DOMAIN_BANNED exception
				submission_praw_thing = self._praw.subreddit(post_job.subreddit).submit(**post_parameters, nsfw=self._set_nsfw_flair_on_submissions)

			if not submission_praw_thing:
				# no submission has been made
				logging.info(f"Failed to make a submission for job {post_job.id}")
				return

			post_job.posted_name = submission_praw_thing.name
			post_job.save()

			logging.info(f"Job {post_job.id} submission submitted successfully")

		except praw.exceptions.RedditAPIException as e:
			if 'DOMAIN_BANNED' in str(e):
				# DOMAIN_BANNED exception can occur when the domain of a url/link post is blacklisted by reddit
				bypass_finally = True
				# 'Reset' the generated image and try again
				post_job.generated_image_path = None
				post_job.reddit_post_attempts = 0
				post_job.save()

		except Exception as e:
			raise e

		finally:
			if not bypass_finally:
				# Increment the post attempts counter.
				# This is to prevent posting too many times if there are errors
				post_job.reddit_post_attempts += 1
				post_job.save()

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
		# Filter by the bot username
		record = db_Thing.get_or_none(db_Thing.source_name == praw_thing.name, db_Thing.bot_username == self._bot_username)
		return record

	def insert_praw_thing_into_database(self, praw_thing, text_generation_parameters=None):
		record_dict = {}
		record_dict['source_name'] = praw_thing.name
		record_dict['bot_username'] = self._bot_username

		if text_generation_parameters:
			# If we want to generate a text reply, then include these parameters in the record
			record_dict['text_generation_parameters'] = text_generation_parameters

		return db_Thing.create(**record_dict)

	def schedule_new_submission(self, subreddit, hourly_frequency):
		# Attempt to schedule a new submission
		# Check that one has not been completed or in the process of, before submitting

		recent_submissions = (db_Thing.select(db_Thing).where(fn.Lower(db_Thing.subreddit) == subreddit.lower()).
					where(db_Thing.source_name == 't3_new_submission').
					where(db_Thing.bot_username == self._bot_username).
					where(db_Thing.status <= 8).
					where(db_Thing.created_utc > (datetime.utcnow() - timedelta(hours=hourly_frequency))))

		if recent_submissions:
			# If there was any submission that is either pending or submitted in the timeframe
			logging.info(f"A submission was made within the last {hourly_frequency} hours on {subreddit}")
			return

		logging.info(f"Scheduling a new submission on {subreddit}")

		new_submission_thing = {}

		new_submission_thing['source_name'] = 't3_new_submission'
		new_submission_thing['bot_username'] = self._bot_username
		new_submission_thing['subreddit'] = subreddit

		text_generation_parameters = self._default_text_generation_parameters.copy()
		new_submission_tag = self._get_random_new_submission_tag()
		text_generation_parameters['prompt'] = new_submission_tag
		text_generation_parameters['max_length'] = 1000
		new_submission_thing['text_generation_parameters'] = text_generation_parameters

		if new_submission_tag.startswith(self._link_submission_start_tag):
			print('its a link submission')
			image_generation_parameters = self._default_image_generation_parameters.copy()
			image_generation_parameters['prompt'] = self._image_post_search_prefix
			new_submission_thing['image_generation_parameters'] = image_generation_parameters

		return db_Thing.create(**new_submission_thing)

	def pending_reply_jobs(self):
		# A list of Comment reply Things from the database that have had text generated,
		# but not a reddit post attempt
		return list(db_Thing.select(db_Thing).
					where(db_Thing.source_name != 't3_new_submission').
					where(db_Thing.bot_username == self._bot_username).
					where(db_Thing.status == 7))

	def pending_new_submission_jobs(self):
		# A list of pending Submission Things from the database that have had text generated,
		# but not a reddit post attempt

		# Base criteria
		query = (db_Thing.select(db_Thing).
					where(db_Thing.source_name == 't3_new_submission').
					where(db_Thing.bot_username == self._bot_username).
					where(db_Thing.status == 7))
		return list(query)

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


def chain_listing_generators(*iterables):
	# Special tool for chaining PRAW's listing generators
	# It joins the three iterables together so that we can DRY
	for it in iterables:
		for element in it:
			if element is None:
				break
			else:
				yield element
