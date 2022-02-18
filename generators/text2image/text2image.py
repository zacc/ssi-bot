#!/usr/bin/env python3

import logging
import os
import psutil
import subprocess
import threading
import time
import torch

from configparser import ConfigParser
from pathlib import Path

from reddit_io.tagging_mixin import TaggingMixin

from bot_db.db import Thing as db_Thing
from utils.memory import get_available_memory

ROOT_DIR = Path(__file__).parent.parent.parent


class Text2Image(threading.Thread, TaggingMixin):

	daemon = True
	name = "Text2Image"

	# The amount of RAM required to start, in KB
	# The default value here is sufficient for a 380x380 image 
	_memory_required = 8000000

	def __init__(self):
		threading.Thread.__init__(self)
		# Detect if a GPU is available, needed for memory calculations
		self._use_gpu = torch.cuda.is_available()

		self._config = ConfigParser()
		self._config.read('ssi-bot.ini')

	def run(self):

		while True:

			# get the top job in the list
			jobs = self.top_pending_jobs()

			if not jobs:
				# there are no jobs at all in the queue
				# Rest a little before attempting again
				time.sleep(30)
				continue

			if get_available_memory(self._use_gpu) < self._memory_required:
				# Not enough memory.. Sleep and start again
				time.sleep(30)
				continue

			for job in jobs:

				try:
					logging.info(f"Starting to generate an image for job_id {job.id}.")

					if not job.image_generation_parameters['prompt'] and job.generated_text:
						# If there is no prompt, but generated text, attempt to extract the title
						# from the generated text and use it as the prompt
						job.image_generation_parameters['prompt'] = self.extract_title_from_generated_text(job.generated_text)

					image_path = self.generate_image(job.bot_username, job.image_generation_parameters.copy())

					if image_path:
						job.generated_image_path = image_path
						job.save()

				except:
					logging.exception(f"Generating an image for a {job} failed")
					time.sleep(30)
				finally:
					job.image_generation_attempts += 1
					job.save()

	def generate_image(self, bot_username, image_generation_parameters):

		vqgan_path = ROOT_DIR / self._config[bot_username]['vqgan-clip_path']
		print('vqgan path', vqgan_path)

		filename = f"{bot_username}_vqgan_output_{int(time.time())}.png"
		filepath = ROOT_DIR / "generated_images" / filename
		print('filename/path', filename, filepath)

		start_time = time.time()

		x = image_generation_parameters.pop('x_size', 256)
		y = image_generation_parameters.pop('y_size', 256)
		iterations = image_generation_parameters.pop('iterations', 500)

		# pop the prompt out from the args
		prompt = image_generation_parameters.pop('prompt', '')
		print('vqgan prompt', prompt)

		cmd_change_directory = f"cd {vqgan_path}"
		print(cmd_change_directory)
		cmd_generate = f"python {vqgan_path}/generate.py -p '{prompt}' -s {x} {y} -o {filepath} -i {iterations}"
		print(cmd_generate)

		p = subprocess.run(f"{cmd_change_directory} ; {cmd_generate}", shell=True, capture_output=True)

		end_time = time.time()
		duration = round(end_time - start_time, 1)

		# Assert that the generated file exists and has a size
		assert os.path.isfile(filepath)
		# A decently generated 256x256 image should be a bit over 100Kb
		# An under-generated image will be undersized
		# assert os.path.getsize(filepath) > 100000
		assert os.path.getsize(filepath) > 50000

		logging.info(f'{filename} image generated in {duration} seconds.')

		# Return the filepath so it can be written into the database
		return filepath

	def top_pending_jobs(self):
		"""
		Get a list of jobs that need an image to be found via the scraper

		"""

		query = db_Thing.select(db_Thing).\
					where(db_Thing.image_generation_parameters['type'] == 'text2image').\
					where(db_Thing.status == 5).\
					order_by(db_Thing.created_utc)
		return list(query)
