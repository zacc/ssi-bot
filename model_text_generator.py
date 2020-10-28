#!/usr/bin/env python3

import logging
import os
import random
import threading
import time

from configparser import ConfigParser

import gpt_2_simple as gpt2

from db import Thing as db_Thing

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


class ModelTextGenerator(threading.Thread):

	daemon = True
	name = "MTGThread"

	_tf_session = None
	_config = None

	def __init__(self):
		threading.Thread.__init__(self)

		self._config = ConfigParser()
		self._config.read('ssi-bot.ini')

		self._checkpoint_dir = os.path.join(ROOT_DIR, self._config['DEFAULT']['model_path'])

		# seed the random generator
		random.seed()

	def run(self):

		# open session
		self._tf_session = gpt2.start_tf_sess()

		while True:

			try:
				# get the top job in the list 
				jobs = self.top_pending_jobs()
				if not jobs:
					# there are no jobs at all in the queue
					# Rest a little before attempting again
					time.sleep(30)
					continue

				# load the model
				self._tf_session = gpt2.reset_session(self._tf_session)
				gpt2.load_gpt2(self._tf_session, checkpoint_dir=self._checkpoint_dir)

				for job in jobs:
					logging.info(f"Starting to generate text for job_id {job.id}.")

					# Increment the counter because we're about to generate text
					job.text_generation_attempts += 1
					job.save()

					# use the model to generate the text
					generated_text = self.generate_text(**job.text_generation_parameters)
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

	def generate_text(self, seed, length, prefix, temperature, top_k, truncate):

		start_time = time.time()

		if not seed:
			# Usually seed will be None so generate one to input to generate function
			# This will ensure the output will be different every time
			seed = random.randint(1, 1000000)

		output_list = gpt2.generate(self._tf_session,
				checkpoint_dir=self._checkpoint_dir,
				seed=seed,
				length=length,
				temperature=temperature,
				top_k=top_k,
				prefix=prefix,
				truncate=None,  # do not use the method signature in truncate
				nsamples=1, # this could be increased to generate several samples of text to choose from
				batch_size=1,
				return_as_list=True
			)

		logging.info(output_list)

		# Because the truncate term (<|eor|>) can exist in the prefix,
		# we'll roll our own logic to extract the generated text for the bot reply

		cleaned_list = []
		for t in output_list:
			# remove any cruft
			t = t.replace('&amp;#x200B;\n', '')

			# find the first instance of the end-of-comment tag, starting from the end of the prefix
			index_of_truncate = t.find(truncate, len(prefix))

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

			# extract the text from between the prefix and the truncate point
			final_string = t[len(prefix):index_of_truncate]
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
