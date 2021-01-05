#!/usr/bin/env python3

import logging
import os
import threading
import time

from configparser import ConfigParser

from simpletransformers.language_generation import LanguageGenerationModel

from db import Thing as db_Thing

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


class ModelTextGenerator(threading.Thread):

	daemon = True
	name = "MTGThread"

	_config = None

	def __init__(self):
		threading.Thread.__init__(self)

		self._config = ConfigParser()
		self._config.read('ssi-bot.ini')

		self._model_path = os.path.join(ROOT_DIR, self._config['DEFAULT']['model_path'])

		# if you are generating on CPU, keep use_cuda and fp16 both false.
		# If you have a nvidia GPU you may enable these features
		# TODO shift these parameters into the ssi-bot.ini file
		self._model = LanguageGenerationModel("gpt2", self._model_path, use_cuda=False, args={'fp16': False})

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
					generated_text = self.generate_text(job.text_generation_parameters)
					if generated_text:
						# if the model generated text, set it into the 'job'
						job.generated_text = generated_text
						job.save()

			except:
				logging.exception("Generating text for a job failed")

	def top_pending_jobs(self):
		"""
		Get a list of text that need text to be generated, by treating
		each database Thing record as a 'job'.
		Three attempts at text generation are allowed.

		"""

		query = db_Thing.select(db_Thing).\
					where(db_Thing.text_generation_parameters.is_null(False)).\
					where(db_Thing.generated_text.is_null()).\
					where(db_Thing.text_generation_attempts < 3).\
					order_by(db_Thing.created_utc)
		return list(query)

	def generate_text(self, text_generation_parameters):

		start_time = time.time()

		truncate = text_generation_parameters.pop('truncate')
		prompt = text_generation_parameters.pop('prompt')

		output_list = self._model.generate(prompt=prompt, args=text_generation_parameters)

		# Because the truncate term (<|eor|>) can exist in the prompt,
		# we'll roll our own logic to extract the generated text for the bot reply
		cleaned_list = []

		for t in output_list:
			# remove any cruft
			t = t.replace('&amp;#x200B;\n', '')

			# find the first instance of the end-of-comment tag, starting from the end of the prompt
			index_of_truncate = t.find(truncate, len(prompt))

			if index_of_truncate == -1:
				# the original truncate tag couldn't be found,
				# but we'll still try and truncate the string at the last line break (end of paragraph)
				# so that the text still looks clean.
				index_of_truncate = t.rfind("\\n")

			if index_of_truncate == -1:
				# still nothing could be found so just skip this one
				# if this is hit often, increase the length of the generated text
				logging.info("Truncate string not found")
				continue

			# extract the text from between the prompt and the truncate point
			final_string = t[len(prompt):index_of_truncate]
			if final_string:
				cleaned_list.append(final_string)

		end_time = time.time()
		duration = round(end_time - start_time, 1)

		logging.info(f'{len(cleaned_list)} sample(s) of text generated in {duration} seconds.')

		if len(cleaned_list) > 0:
			# At the moment the database can only handle one string of generated text
			# Modifications to the database would be required to handle more than one
			return cleaned_list[0]

		# return None because we could not generated a string
		return None
