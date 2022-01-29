#!/usr/bin/env python3

import json
import logging
import requests
import threading
import time
import urllib.parse

from bs4 import BeautifulSoup
from nltk import tokenize

from logic_mixin import LogicMixin

from db import Thing as db_Thing


class ImageScraper(threading.Thread, LogicMixin):

	daemon = True
	name = "ImageScraper"

	def __init__(self):
		threading.Thread.__init__(self)

	def run(self):

		while True:

			# get the top job in the list
			jobs = self.top_pending_jobs()

			for job in jobs:

				try:
					logging.info(f"Starting to find an image for job_id {job.id}.")

					# Logic mixin extract title
					title_text = self.extract_title_from_generated_text(job.generated_text)
					if not title_text:
						continue

					image_url = self._download_image_for_search_string(title_text, job.image_generation_parameters, job.image_generation_attempts)

					print('found image_url', image_url)

					if image_url:
						job.generated_image_path = image_url
						job.save()

					# Sleep a bit here to not hammer the servers
					time.sleep(10)

				except:
					logging.exception(f"Scraping image for a {job} failed")

				finally:
					job.image_generation_attempts += 1
					job.save()
					print(f'job status is {job.status}')

			# Sleep a bit more to be nice to dem servers
			time.sleep(120)
			# Testing
			# time.sleep(10)

	def _download_image_for_search_string(self, search_string, image_generation_parameters, attempt):

		logging.info(f"Searching on Bing for an image for: \"{search_string}\"")

		# pop the prompt out from the args
		prompt = image_generation_parameters.pop('prompt', None)

		# split the search string into sentences
		sentences = tokenize.sent_tokenize(search_string)

		# Truncate to improve effectiveness of the search
		search_terms = ' '.join(sentences[0].split()[:8])

		# If it exists, add the prefix to improve results
		if prompt:
			search_terms = prompt + ' ' + search_terms

		# Collect and encode all search url parameters
		# If on the 2nd attempt, jump ahead
		search_parameters = {'q': search_terms,
							'form': 'HDRSC2',
							# 'qft': '+filterui:imagesize-large',
							'safeSearch': 'strict',
							'first': int(1 + (attempt * 10))}

		encoded_search_parameters = urllib.parse.urlencode(search_parameters)
		search_url = "https://www.bing.com/images/search?" + encoded_search_parameters

		logging.info(f"Searching for an image with url: {search_url}")

		# Use Win10 Edge User Agent
		header = {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36 Edg/92.0.902.78"}

		r = requests.get(search_url, headers=header)

		if r.ok:
			soup = BeautifulSoup(r.text, 'html.parser')
			link_results = soup.find_all("a", {"class": "iusc"})

			for link in link_results[:10]:
				if link.has_attr('m'):
					# convert json in the link's attributes into a python dict
					m = json.loads(link["m"])
					if 'murl' in m:
						image_url = m['murl']
						return image_url

	def top_pending_jobs(self):
		"""
		Get a list of jobs that need an image to be found via the scraper

		"""

		query = db_Thing.select(db_Thing).\
					where(db_Thing.image_generation_parameters['type'] == 'scraper').\
					where(db_Thing.status == 5).\
					order_by(db_Thing.created_utc)
		return list(query)
