import html
from datetime import datetime, timedelta

import requests
from playhouse.shortcuts import model_to_dict, dict_to_model
from requests.adapters import HTTPAdapter, Response
from requests.packages.urllib3.util.retry import Retry
from configparser import ConfigParser

from db import *


class PushIOProcessor:
	"""
	A class for downloading from PUSHIO and writing directly to a DB as efficiently as possible without using a
	out of process mechanism.
	"""

	def __init__(self, start_date, end_date, subreddit, db_instance, min_score=5):
		self.score = min_score
		self.start_date_time = datetime.fromisoformat(start_date)
		self.end_date_time = datetime.fromisoformat(end_date)
		self.subreddit = subreddit
		self.session = requests.Session()
		self.db = db_instance

	@staticmethod
	def set_is_url_only(comment: dict) -> bool:
		comment_body = comment.get('body')
		return (comment_body.startswith('[') and comment_body.endswith(')')) or (
				'http' in comment_body.lower() and ' ' not in comment_body)

	@staticmethod
	def get_data_from_response(response: Response) -> [dict]:

		if response.status_code != 200:
			logging.error("Response has non 200 status code")
			return []

		try:
			json_content = response.json()
			data = json_content.get('data')
			if data:
				return data
			else:
				logging.error("No Data in Response")
				return []
		except Exception as e:
			logging.error(e)
			return []

	@staticmethod
	def clean_text(text) -> str:
		if text is None:
			text = ""
		# have to unescape it twice, for reason I don't fully understand
		text = html.unescape(text)
		text = html.unescape(text)
		# Strip and whitespace off of the end
		text = text.strip()
		return text

	def loop_between_dates(self):
		# yields start and end dates between the dates given
		# at weekly intervals
		time_interval = timedelta(weeks=1)

		# Make sure the start_datetime is always a Monday by shifting the start back to monday
		start_datetime = self.start_date_time - timedelta(days=self.start_date_time.weekday())

		period_start_date = start_datetime

		while period_start_date < self.end_date_time:
			period_end_date = min(period_start_date + time_interval, self.end_date_time)

			yield period_start_date, period_end_date

			if (period_start_date + time_interval) >= self.end_date_time:
				# if this loop's date is beyond the end_datetime, break the loop
				break
			period_start_date = period_end_date

	def calc_date_range(self):
		return self.end_date_time.timestamp() - self.start_date_time.timestamp()

	def get_with_retry(self, link: str) -> Response:
		try:
			retry_options = Retry(
				total=10,
				# Total number of attempts to try to perform a request. Adjust this parameter for number attempts.
				status_forcelist=[429, 500, 502, 503, 504, 522, 521],  # Acceptable status codes to re-try on
				allowed_methods=["GET"],  # Methods to allow re-try for
				backoff_factor=1  # 1 second the successive sleeps will be 0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256.
			)
			# Network connections are lossy, congested and servers fail. Account for failures and apply retry mechanism.
			adapter = HTTPAdapter(max_retries=retry_options)
			self.session.mount(link, adapter)
			response = self.session.get(link)
			if len(response.text) > 0:
				return response
			else:
				# I have never seen this actually occur but if it does it would be unexpected. Use recursion and let it throw
				logging.error("No response body found")
				response = Response()
				response.status_code = 500
				return response

		except Exception as e:
			logging.error(f"An exception has occurred while doing stupid internet stuff: {e}")
			response = Response()
			response.status_code = 500
			return response

	def get_related_comments(self, id: str) -> None:
		comment_search_link = f'https://api.pushshift.io/reddit/comment/search/?subreddit={self.subreddit}&link_id={id}&sort_type=created_utc&sort=asc'
		comment_response = self.get_with_retry(comment_search_link)
		self.process_comments(comment_response)
		return

	def process_submission(self, response: Response) -> None:

		submissions = self.get_data_from_response(response)

		if len(submissions) == 0:
			logging.debug("No submissions found for the response")
			return

		# Get all id's for the submission
		submission_ids = [submission.get('id') for submission in submissions]

		# check to see which id's have already been processed
		known_ids = [item.id for item in
					 list(Submission.select(Submission.id).where(Submission.id.in_(submission_ids)))]

		logging.info(f"{len(known_ids)} / {len(submission_ids)} submissions found in table")

		submissions_to_write = []
		for submission in submissions:

			submission_id = submission.get('id')

			if submission_id is None:
				return

			# Filter out all the know submissions...
			if 'num_comments' not in submission:
				# Sometimes the json['data'] can be empty
				print(f"There are no comments for {0}. Something might be wrong ".format(submission))
				continue

			if 'selftext' not in submission:
				logging.debug("Ignore submissions with no selftext key (buggy)")
				continue

			if submission['selftext'] in ['[removed]', '[deleted]']:
				logging.debug(f"Submission Was removed or deleted for {submission_id}")
				continue

			if submission_id in known_ids:
				logging.info(f"Skipping {submission_id} and detox for entry")
				continue

			submission['selftext'] = self.clean_text(submission.get('selftext'))

			submissions_to_write.append(submission)

			self.get_related_comments(submission_id)
			continue

		with db_instance.atomic():
			models = [dict_to_model(Submission, submission, ignore_unknown=True) for submission in submissions_to_write]
			jsons = [model_to_dict(model) for model in models]
			Submission.insert_many(jsons).execute()

		return

	def process_comments(self, response: Response) -> None:

		comments = self.get_data_from_response(response)

		comment_ids = [comment.get('id') for comment in comments]

		known_ids = [item.id for item in list(Comment.select(Comment.id).where(Comment.id.in_(comment_ids)))]

		logging.info(f"{len(known_ids)} / {len(comment_ids)} comments found in Db for this set.")

		if comments is None:
			return

		if len(comments) == 0:
			return

		comments_to_write = []

		for comment in comments:

			comment_id = comment.get('id')

			if comment_id in known_ids:
				logging.info(f"Skipping {comment_id} and detox for entry")
				continue

			comment['body'] = self.clean_text(comment.get('body'))

			comment['is_url_only'] = self.set_is_url_only(comment)

			if comment.get('body') in ['[removed]', '[deleted]']:
				logging.debug(f"Comment Was removed or deleted for {comment_id}")
				continue

			if comment_id in known_ids:
				logging.info(f"Skipping {comment_id} and detox for entry")
				continue

			comments_to_write.append(comment)

		with db_instance.atomic():
			# this is done to trick the serializer into accepting the fields. The correct thing to do would not direct
			# intake the blob but that is a lot of work to do when this works well enough.
			models = [dict_to_model(Comment, comment, ignore_unknown=True) for comment in comments_to_write]
			jsons = [model_to_dict(model) for model in models]
			Comment.insert_many(jsons).execute()

		return

	def run(self) -> None:
		for start, end in self.loop_between_dates():
			time_delta = (end.timestamp() - self.start_date_time.timestamp()) / self.calc_date_range()

			logging.info(
				f"downloading submission data from {start.date()} to {end.date()}... {round(time_delta * 100, 2)}%")

			submission_search_link = (
				'https://api.pushshift.io/reddit/submission/search/?subreddit={}&after={}&before={}&stickied=0&sort_type=score&sort=desc&limit={}&mod_removed=0&score{}')

			submission_search_link = submission_search_link.format(self.subreddit, int(start.timestamp()),
																   int(end.timestamp()), 100, self.score)

			submission_response = self.get_with_retry(submission_search_link)

			self.process_submission(submission_response)

			return


if __name__ == '__main__':
	logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
	config = ConfigParser()
	config.read('dataset.ini')
	# TODO: Add config stuff
	start_date = config.get("start_date", "DEFAULT")
	end_date = config.get("end_date", "DEFAULT")
	subreddits = config.get("training_subreddits", "DEFAULT")

	# NOTE: For those who care. Add a min_score to the configuration to allow a more contextual collection of
	# meaningful comments. The choice of one here is not-ideal for ALL subreddits

	# NOTE: It is less effective to run this in parallel. Let the lag between writing to the DB and performing a rest

	# request not compete against each other because at some point push will time you out or the DB will choke to a crawl.
	# Use multithreading at your own peril.
	for sub in subreddits:
		processor = PushIOProcessor(start_date=start_date, end_date=end_date, subreddit=sub, db_instance=db_instance,
									min_score=1)
		processor.run()
