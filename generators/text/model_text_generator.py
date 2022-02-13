#!/usr/bin/env python3

import logging
import threading
import time

import ftfy
import codecs

from pathlib import Path
from configparser import ConfigParser

from simpletransformers.language_generation import LanguageGenerationModel

from reddit_io.tagging_mixin import TaggingMixin
from bot_db.db import Thing as db_Thing

from utils.keyword_helper import KeywordHelper

ROOT_DIR = Path(__file__).parent.parent.parent


class ModelTextGenerator(threading.Thread, TaggingMixin):

	daemon = True
	name = "MTGThread"

	_config = None

	def __init__(self):
		threading.Thread.__init__(self)

		self._config = ConfigParser()
		self._config.read('ssi-bot.ini')

		# Configure the keyword helper to check negative keywords in the generated text
		self._keyword_helper = KeywordHelper()

	def run(self):

		while True:

			jobs = self.top_pending_jobs()

			for job in jobs:

				try:
					logging.info(f"Starting to generate text for bot {job.bot_username}, job_id {job.id}.")

					# use the model to generate the text
					# pass a copy of the parameters to keep the job values intact
					generated_text = self.generate_text(job.bot_username, job.text_generation_parameters.copy())

					if generated_text:

						# Check for any negative keywords in the generated text and if so, return nothing
						negative_keyword_matches = self._keyword_helper.negative_keyword_matches(generated_text)
						if len(negative_keyword_matches) > 0:
							# A negative keyword was found, so don't post this text back to reddit
							logging.info(f"Negative keywords {negative_keyword_matches} found in generated text, this text will be rejected.")
							continue

						# Perform a very basic validation of the generated text
						prompt = job.text_generation_parameters.get('prompt', '')
						valid = self.validate_generated_text(job.source_name, prompt, generated_text)
						if not valid:
							logging.info(f"Generated text for {job} failed validation, this text will be rejected.")
							continue

						# if the model generated text, set it into the 'job'
						job.generated_text = generated_text
						job.save()

				except:
					logging.exception(f"Generating text for a {job} failed")

				finally:
					# Increment the counter because we're about to generate text
					job.text_generation_attempts += 1
					job.save()

			if not jobs:
				# there are no jobs at all in the queue
				# Rest a little before attempting again
				time.sleep(30)
				continue

	def generate_text(self, bot_username, text_generation_parameters):

		model_path = ROOT_DIR / self._config[bot_username]['model_path']

		# if you are generating on CPU, keep use_cuda and fp16 both false.
		# If you have a nvidia GPU you may enable these features
		# TODO shift these parameters into the ssi-bot.ini file
		model = LanguageGenerationModel("gpt2", model_path, use_cuda=False, args={'fp16': False})

		start_time = time.time()

		# pop the prompt out from the args
		prompt = text_generation_parameters.pop('prompt', '')

		if len(prompt) > 1500:
			# The model can handle 1024 tokens, but a token is not just one character.
			# Just truncate the long string to be safe and hope for the best :)
			prompt = prompt[-1450:]

		output_list = model.generate(prompt=prompt, args=text_generation_parameters)

		end_time = time.time()
		duration = round(end_time - start_time, 1)

		logging.info(f'{len(output_list)} sample(s) of text generated in {duration} seconds.')

		if output_list:
			return ftfy.fix_text(codecs.decode(output_list[0], "unicode_escape"))
			# return output_list[0]

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
