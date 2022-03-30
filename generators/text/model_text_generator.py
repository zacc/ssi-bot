#!/usr/bin/env python3

import logging
import threading
import time

from pathlib import Path
from configparser import ConfigParser

from simpletransformers.language_generation import LanguageGenerationModel

from reddit_io.tagging_mixin import TaggingMixin
from bot_db.db import Thing as db_Thing

from utils.keyword_helper import KeywordHelper
from utils.toxicity_helper import ToxicityHelper

from utils.memory import get_available_memory
from utils import ROOT_DIR


class ModelTextGenerator(threading.Thread, TaggingMixin):

	daemon = True
	name = "MTGThread"

	# GPU is not really required for text generation
	# So the default is False
	_use_gpu = False

	_config = None

	# The amount of memory required to start generation, in KB
	# This is the default for GPT-2 Small (117M parameters)
	# This will need to be increased for larger GPT-2 models
	_memory_required = 1400000

	def __init__(self):
		threading.Thread.__init__(self)

		self._config = ConfigParser()
		self._config.read('ssi-bot.ini')

		# Configure the keyword helper to check negative keywords in the generated text
		self._toxicity_helper = ToxicityHelper()

	def run(self):

		logging.info("Starting GPT-2 text generator daemon")

		while True:

			jobs = self.top_pending_jobs()

			if not jobs:
				# there are no jobs at all in the queue
				# Rest a little before attempting again
				time.sleep(30)
				continue

			if get_available_memory(self._use_gpu) < self._memory_required:
				# Not enough memory.. Sleep and start again
				logging.info('Insufficient memory to generate text')
				time.sleep(30)
				continue

			for job in jobs:

				try:
					logging.info(f"Starting to generate text for bot {job.bot_username}, job_id {job.id}.")

					# use the model to generate the text
					# pass a copy of the parameters to keep the job values intact
					generated_text = self.generate_text(job.bot_username, job.text_generation_parameters.copy())

					if generated_text:

						# Check for any negative keywords in the generated text and if so, return nothing
						negative_keyword_matches = self.test_text_against_keywords(job.bot_username, generated_text)
						if negative_keyword_matches:
							# A negative keyword was found, so don't post this text back to reddit
							logging.info(f"Negative keywords {negative_keyword_matches} found in generated text, this text will be rejected.")
							continue

						# Perform a very basic validation of the generated text
						prompt = job.text_generation_parameters.get('prompt', '')
						valid = self.validate_generated_text(job.source_name, prompt, generated_text)
						if not valid:
							logging.info(f"Generated text for {job} failed validation, this text will be rejected.")
							continue

						toxicity_failure = self.validate_toxicity(job.bot_username, prompt, generated_text)
						if toxicity_failure:
							logging.info(f"Generated text for {job} failed toxicity test, this text will be rejected.-> {generated_text}")
							continue

						# if the model generated text, set it into the 'job'
						job.generated_text = generated_text
						job.save()

				except:
					logging.exception(f"Generating text for job {job} failed")

				finally:
					# Increment the counter because we're about to generate text
					job.text_generation_attempts += 1
					job.save()

	def generate_text(self, bot_username, text_generation_parameters):

		model_path = ROOT_DIR / self._config[bot_username]['text_model_path']

		# if you are generating on CPU, keep use_cuda and fp16 both false.
		# If you have a nvidia GPU you may enable these features
		# TODO shift these parameters into the ssi-bot.ini file
		model = LanguageGenerationModel("gpt2", model_path, use_cuda=self._use_gpu, args={'fp16': False})

		start_time = time.time()

		# pop the prompt out from the args
		prompt = text_generation_parameters.pop('prompt', '')

		output_list = model.generate(prompt=prompt, args=text_generation_parameters)

		end_time = time.time()
		duration = round(end_time - start_time, 1)

		logging.info(f'{len(output_list)} sample(s) of text generated in {duration} seconds.')

		if output_list:
			return output_list[0]

	def top_pending_jobs(self):
		"""
		Get a list of jobs that need text to be generated, by treating
		each database Thing record as a 'job'.
		Three attempts at text generation are allowed.

		"""

		query = db_Thing.select(db_Thing).\
					where(db_Thing.status == 3).\
					order_by(db_Thing.created_utc)
		return list(query)

	def test_text_against_keywords(self, bot_username, generated_text):
		# Load the keyword helper with this bot's config
		keyword_helper = KeywordHelper(bot_username)
		return keyword_helper.negative_keyword_matches(generated_text)

	def validate_toxicity(self, bot_username, prompt, generated_text):

		# Remove tags from the
		new_text = generated_text[len(prompt):]
		tagless_new_text = self.remove_tags_from_string(new_text)

		# Reconfigure the toxicity helper to use the bot's config
		self._toxicity_helper.load_config_section(bot_username)
		return self._toxicity_helper.text_above_toxicity_threshold(tagless_new_text)

	def validate_generated_text(self, source_name, prompt, generated_text):

		if source_name == 't3_new_submission':
			# The job is to create a new submission so
			# Check it has a title
			title = self.extract_title_from_generated_text(generated_text)
			if title is None:
				logging.info("Validation failed, no title")
			return title is not None

		else:
			# The job is to create a reply
			# Check that is has a closing tag
			new_text = generated_text[len(prompt):]
			if not self._end_tag in new_text:
				logging.info("Validation failed, no end tag")
			return self._end_tag in new_text
