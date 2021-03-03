#!/usr/bin/env python3

import html
import time
import os
import json
import threading

from queue import Queue
from typing import Generator, List, NoReturn, Type

import requests
from datetime import datetime, timedelta

from db import (Comment as db_Comment, Submission as db_Submission)
from db import create_tables

start_date:datetime = datetime(2018, 1, 1)
end_date:datetime= datetime(2020, 10, 19)


def loop_between_dates(start_datetime:datetime, end_datetime:datetime)->Generator[datetime,datetime]:
	# yields start and end dates between the dates given
	# at weekly intervals
	time_interval:Type(timedelta) = timedelta(weeks=1)

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


def clean_text(text:str)->str:
	# have to unescape it twice, for reason I don't fully understand
	text = html.unescape(text)
	text = html.unescape(text)
	# Strip and whitespace off of the end
	text = text.strip()

	# add a period to the end of the line, if a proper line closure does not exist
	# This help GPT-2 know the end of the sentence.
	if len(text) > 1:
		if text[-1].isalnum():
			text = text + '.'

	return text


def write_to_database(q:Queue)->NoReturn:

	counter:int = 0

	while True:
		json_filepath = q.get()

		data = None

		with open(json_filepath, 'r') as f:
			data = json.load(f)

		for json_item in data['data']:

			if 'body' in json_item:
				# if 'body' is present then assume it's a comment

				db_record = db_Comment.get_or_none(db_Comment.id == json_item['id'])

				if not db_record:

					json_item['body'] = clean_text(json_item['body'])

					db_record = db_Comment.create(**json_item)
					print(f"comment {json_item['id']} written to database")
					counter += 1

			elif 'selftext' in json_item:
				# if 'selftext' is present then assume it's a submission
				db_record = db_Submission.get_or_none(db_Submission.id == json_item['id'])

				if not db_record:

					json_item['selftext'] = clean_text(json_item['selftext'])

					db_record = db_Submission.create(**json_item)
					print(f"submission {json_item['id']} written to database")
					counter += 1

		q.task_done()


def main()->None:

	create_tables()

	# Queue for the write to db thread to receive from
	q:Queue = Queue()

	# The worker thread will run in the background copying files into the database
	# even while we're still downloading new ones (saves time)
	threading.Thread(target=write_to_database, args=(q,), daemon=True).start()

	# which subreddits to download from
	subreddits:list = []

	# limit of submissions to download (per loop period)
	# Pushshift will only allow 100 per file, so use score/gilding/etc filtering to get the best quality submissions
	# If you are combining multiple subreddits, you can reduce this number to reduce download time
	submission_limit:int = 100

	for subreddit in subreddits:

		# check that the output dir exists, if not create it
		output_dir = f'json_data/{subreddit}'
		if not os.path.exists(output_dir):
			os.makedirs(output_dir)

		for start, end in loop_between_dates(start_date, end_date):

			submission_output_path = f"json_data/{subreddit}/{subreddit}_submissions_{int(start.timestamp())}.json"

			if not os.path.isfile(submission_output_path):
				print(f"submission does not exist on the disk; starting to download {submission_output_path}")
				# The file already exists so just skip ahead in the loop

				# Get the top (x) number of submissions for that period.
				submission_search_link = ('https://api.pushshift.io/reddit/submission/search/'
							   '?subreddit={}&after={}&before={}&stickied=0&sort_type=score&sort=desc&limit={}&mod_removed=0')
				submission_search_link = submission_search_link.format(subreddit, int(start.timestamp()), int(end.timestamp()), submission_limit)

				submission_response = requests.get(submission_search_link)

				if submission_response.status_code != 200:
					# the response was not OK, skip writing the file
					continue

				with open(submission_output_path, "w") as f:
					f.write(submission_response.text)

				time.sleep(0.1)

			else:
				print(f"{submission_output_path} file exists on the disk, skipping download")
				# The file already exists, but we'll go forwards and
				# check the comment files, download if required

			# Put the submission path into the queue to write into the database
			q.put(submission_output_path)

			# now re-open the file and load the json, 
			# we'll try and pick up the comments for each submission id
			submission_json = None

			with open(submission_output_path, 'r', encoding='utf8') as json_file:
				submission_json = json.load(json_file)

			for submission_json_item in submission_json['data']:

				if 'num_comments' not in submission_json_item:
					# Sometimes the json['data'] can be empty
					continue

				if submission_json_item['num_comments'] == 0:
					# ignore submissions with no comments
					continue

				if 'selftext' not in submission_json_item:
					# ignore submissions with no selftext key (buggy)
					continue

				if submission_json_item['selftext'] in ['[removed]', '[deleted]']:
					# ignore submissions that have no content
					continue

				comment_output_path = f"json_data/{subreddit}/{subreddit}_{submission_json_item['id']}_comment.json"

				if not os.path.isfile(comment_output_path):
					print(f"{comment_output_path} does not exist on the disk, downloading...")
					# print(submission_json_item)
					comment_search_link = ('https://api.pushshift.io/reddit/comment/search/'
								   '?subreddit={}&link_id={}&sort_type=created_utc&sort=asc')
					comment_search_link = comment_search_link.format(subreddit, submission_json_item['id'])

					comment_response = requests.get(comment_search_link)

					if comment_response.status_code != 200:
						# the response was not OK, skip writing the file
						continue

					with open(comment_output_path, "w") as f:
						f.write(comment_response.text)

					# Have to sleep a bit here or else pushshift will start to block our requests
					time.sleep(0.05)

				# Put it into the queue to write into the database
				q.put(comment_output_path)

	q.join()

if __name__ == '__main__':
	main()
