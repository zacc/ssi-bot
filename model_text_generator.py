#!/usr/bin/env python3

import logging
import os
import threading
import time

from configparser import ConfigParser

from simpletransformers.language_generation import LanguageGenerationModel

from db import Thing as db_Thing

from keyword_helper import KeywordHelper

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


class ModelTextGenerator(threading.Thread):

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

			try:
				# get the top job in the list
				jobs = self.top_pending_jobs()
				if not jobs:
					# there are no jobs at all in the queue
					# Rest a little before attempting again
					time.sleep(30)
					continue

				for job in jobs:
					logging.info(f"Starting to generate text for job_id {job.id}.")

					# Increment the counter because we're about to generate text
					job.text_generation_attempts += 1
					job.save()

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

						# if the model generated text, set it into the 'job'
						job.generated_text = generated_text
						job.save()

			except:
				logging.exception("Generating text for a job failed")

	def top_pending_jobs(self):
		"""
		Get a list of jobs that need text to be generated, by treating
		each database Thing record as a 'job'.
		Three attempts at text generation are allowed.

		"""

		query = db_Thing.select(db_Thing).\
					where(db_Thing.text_generation_parameters.is_null(False)).\
					where(db_Thing.generated_text.is_null()).\
					where(db_Thing.text_generation_attempts < 3).\
					order_by(db_Thing.created_utc)
		return list(query)

	def generate_text(self, bot_username, text_generation_parameters):

		model_path = os.path.join(ROOT_DIR, self._config[bot_username]['model_path'])

		if not model_path:
			logging.error(f'Cannot generate GPT-2 text: Bot {bot_username} model path config could not be found.')

		# if you are generating on CPU, keep use_cuda and fp16 both false.
		# If you have a nvidia GPU you may enable these features
		# TODO shift these parameters into the ssi-bot.ini file
		model = LanguageGenerationModel("gpt2", model_path, use_cuda=False, args={'fp16': False})

		start_time = time.time()

		# pop the prompt out from the args
		prompt = text_generation_parameters.pop('prompt')

		output_list = model.generate(prompt=prompt, args=text_generation_parameters)

		end_time = time.time()
		duration = round(end_time - start_time, 1)

		logging.info(f'{len(output_list)} sample(s) of text generated in {duration} seconds.')

		if output_list:
			return output_list[0]
