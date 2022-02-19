#!/usr/bin/env python3

import html
import os
import json
import threading
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from queue import Queue

import requests
from datetime import datetime, timedelta

from configparser import ConfigParser

from db import (Comment as db_Comment, Submission as db_Submission)
from db import create_tables

config = ConfigParser()
config.read('dataset.ini')

# Set session globally fo the run
http = requests.Session()

verbose = False

if config['DEFAULT']['verbose']:
	verbose = config['DEFAULT'].getboolean('verbose')


def loop_between_dates(start_datetime, end_datetime):
	# yields start and end dates between the dates given
	# at weekly intervals
	time_interval = timedelta(weeks=1)

	# Make sure the start_datetime is always a Monday by shifting the start back to monday
	start_datetime = start_datetime - timedelta(days=start_datetime.weekday())

	period_start_date = start_datetime

	while period_start_date < end_datetime:
		period_end_date = min(period_start_date + time_interval, end_datetime)

		yield (period_start_date, period_end_date)

		if (period_start_date + time_interval) >= end_datetime:
			# if this loop's date is beyond the end_datetime, break the loop
			break
		period_start_date = period_end_date


def clean_text(text):
	# have to unescape it twice, for reason I don't fully understand
	text = html.unescape(text)
	text = html.unescape(text)
	# Strip and whitespace off of the end
	text = text.strip()

	return text


def get_with_retry(link: str):
	"""
	Performs a request using a re-try mechanism. Throws if an exception is thrown from the parent handler after
	the back-up mechanism has failed. Current benchmarks suggests you can scrap about ~50% of the data from r/AskReddit
	from 2018-2022 before this mechanism fails due to upstream api failures before requiring a restart of the application.
	"""
	retry_options = Retry(
		total=10,  # Total number of attempts to try to perform a request. Adjust this parameter for number attempts.
		status_forcelist=[429, 500, 502, 503, 504],  # Acceptable status codes to re-try on
		allowed_methods=["GET"],  # Methods to allow re-try for
		backoff_factor=1  # 1 second the successive sleeps will be 0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256.
	)
	# Network connections are lossy, congested and servers fail. Account for failures and apply retry mechanism.
	adapter = HTTPAdapter(max_retries=retry_options)
	http.mount(link, adapter)
	response = http.get(link)
	if len(response.text) > 0:
		return response
	else:
		# I have never seen this actually occur but if it does it would be unexpected. Use recursion and let it throw
		# how it be like it do.
		print("No response body found")
		return get_with_retry(link)


def write_to_database(q):
	while True:
		json_filepath = q.get()

		with open(json_filepath, 'r') as f:
			data = json.load(f)

		for json_item in data['data']:

			if 'body' in json_item:
				# if 'body' is present then assume it's a comment

				db_record = db_Comment.get_or_none(db_Comment.id == json_item['id'])

				if not db_record:

					json_item['body'] = clean_text(json_item['body'])

					# Try to detect whether the comment is a URL only with no text so we can ignore it later
					json_item['is_url_only'] = (json_item['body'].startswith('[') and json_item['body'].endswith(')')) \
											   or ('http' in json_item['body'].lower() and ' ' not in json_item['body'])

					db_record = db_Comment.create(**json_item)
					if verbose:
						print(f"comment {json_item['id']} written to database")

			elif 'selftext' in json_item:
				# if 'selftext' is present then assume it's a submission
				db_record = db_Submission.get_or_none(db_Submission.id == json_item['id'])

				if not db_record:

					json_item['selftext'] = clean_text(json_item['selftext'])

					db_record = db_Submission.create(**json_item)
					if verbose:
						print(f"submission {json_item['id']} written to database")

		q.task_done()


def main():
	print("starting download, use Ctrl+C to pause at any point in the process")

	create_tables()

	# Queue for the write to db thread to receive from
	q = Queue()

	# The worker thread will run in the background copying files into the database
	# even while we're still downloading new ones (saves time)
	threading.Thread(target=write_to_database, args=(q,), daemon=True).start()

	# dataset subreddits, start date, and end date
	training_subreddits = []
	start_date = '2018-01-01'
	end_date = '2021-08-09'
	min_comments = 1

	# limit of submissions to download (per loop period)
	# Pushshift will only allow 100 per file, so use score/gilding/etc filtering to get the best quality submissions
	# If you are combining multiple subreddits, you can reduce this number to reduce download time
	submission_limit = 100

	# pull configs from dataset.ini
	if config['DEFAULT']['start_date']:
		start_date = config['DEFAULT']['start_date']
	if config['DEFAULT']['end_date']:
		end_date = config['DEFAULT']['end_date']
	if config['DEFAULT']['training_subreddits']:
		training_subreddits = config['DEFAULT']['training_subreddits'].split(',')
	if config['DEFAULT']['submission_limit']:
		submission_limit = int(config['DEFAULT']['submission_limit'])
	if config['DEFAULT']['min_comments']:
		min_comments = int(config['DEFAULT']['min_comments'])

	# reassign date variables to datetime object
	start_date = datetime.fromisoformat(start_date)
	end_date = datetime.fromisoformat(end_date)

	date_range = end_date.timestamp() - start_date.timestamp()

	for subreddit in training_subreddits:

		# check that the output dir exists, if not create it
		output_dir = f'json_data/{subreddit}'
		if not os.path.exists(output_dir):
			os.makedirs(output_dir)

		for start, end in loop_between_dates(start_date, end_date):

			time_delta = (end.timestamp() - start_date.timestamp()) / date_range

			print(f"downloading submission data from {start.date()} to {end.date()}... {round(time_delta * 100, 2)}%")

			submission_output_path = f"json_data/{subreddit}/{subreddit}_submissions_{int(start.timestamp())}.json"

			if not os.path.isfile(submission_output_path):
				print(f"submission does not exist on the disk; starting to download {submission_output_path}")
				# The file already exists so just skip ahead in the loop

				# Get the top (x) number of submissions for that period.
				submission_search_link = ('https://api.pushshift.io/reddit/submission/search/?subreddit={}&after={}&before={}&stickied=0&sort_type=score&sort=desc&limit={}&mod_removed=0')
				submission_search_link = submission_search_link.format(subreddit, int(start.timestamp()), int(end.timestamp()), submission_limit)

				submission_response = get_with_retry(submission_search_link)
				# Download if not found
				with open(submission_output_path, "w") as f:
					f.write(submission_response.text)
			else:
				print(f"{submission_output_path} file exists on the disk, skipping download")

			# Put the submission path into the queue to write into the database
			q.put(submission_output_path)

			with open(submission_output_path, 'r', encoding='utf8') as json_file:
				submission_json = json.load(json_file)

			for submission_json_item in submission_json['data']:

				if 'num_comments' not in submission_json_item:
					# Sometimes the json['data'] can be empty
					print(f"There are no comments for {0}. Something might be wrong ".format(submission_json_item))
					continue

				if submission_json_item['num_comments'] < min_comments:
					# ignore submissions with less comments than the minimum
					continue

				if 'selftext' not in submission_json_item:
					# ignore submissions with no selftext key (buggy)
					continue

				if submission_json_item['selftext'] in ['[removed]', '[deleted]']:
					# ignore submissions that have no content
					continue

				comment_output_path = f"json_data/{subreddit}/{subreddit}_{submission_json_item['id']}_comment.json"

				if not os.path.isfile(comment_output_path):
					if verbose:
						print(f"{comment_output_path} does not exist on the disk, downloading...")

					comment_search_link = ('https://api.pushshift.io/reddit/comment/search/?subreddit={}&link_id={}&sort_type=created_utc&sort=asc')
					comment_search_link = comment_search_link.format(subreddit, submission_json_item['id'])

					comment_response = get_with_retry(comment_search_link)

					with open(comment_output_path, "w") as f:
						f.write(comment_response.text)

				# Put it into the queue to write into the database
				q.put(comment_output_path)

	q.join()
	print("finished!")


if __name__ == '__main__':
	main()
