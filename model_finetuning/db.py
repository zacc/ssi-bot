#!/usr/bin/env python3

import json
import logging
import os
import time

from functools import partial, singledispatch

from playhouse.sqlite_ext import *
from playhouse.migrate import *

import numpy as np

db_file_path = os.path.join('pushshift.sqlite3')
db_instance = SqliteExtDatabase(db_file_path, thread_safe=True, pragmas={'journal_mode': 'wal2', 'foreign_keys': 0}, regexp_function=True)


@singledispatch
def to_serializable(val):
	"""Used by default."""
	return str(val)


@to_serializable.register(np.float32)
def ts_float32(val):
	"""Used if *val* is an instance of numpy.float32."""
	return np.float64(val)

# We use a special partial wrapper around json.dumps to convert numpy's float32 number to a compatible float
numpy_safe_dumps = partial(json.dumps, default=to_serializable)


class Submission(Model):

	author = TextField()
	author_flair_text = TextField(null=True)
	created_utc = TimestampField(utc=True)
	id = TextField(primary_key=True)
	is_self = BooleanField()
	num_comments = IntegerField()
	over_18 = BooleanField()
	permalink = TextField()
	score = IntegerField()
	selftext = TextField()
	spoiler = BooleanField(null=True)
	stickied = BooleanField(default=False)
	subreddit = TextField()
	title = TextField()
	url = TextField(null=True)

	# Non-standard fields
	detoxify_prediction = JSONField(null=True, json_dumps=numpy_safe_dumps)

	@property
	def combined_text(self):
		# A property that combines the title and selftext
		# For link
		return f'{self.title} {self.selftext}'.strip()

	class Meta:
		database = db_instance


class Comment(Model):

	author = TextField()
	author_flair_text = TextField(null=True)
	body = TextField()
	created_utc = TimestampField(utc=True)
	id = TextField(primary_key=True)
	link_id = TextField()
	nest_level = IntegerField(null=True)
	parent_id = TextField(index=True)
	score = IntegerField()
	stickied = BooleanField(default=False)

	# Non-standard fields
	is_url_only = BooleanField()
	detoxify_prediction = JSONField(null=True, json_dumps=numpy_safe_dumps)

	def parent(self):
		# This function gets the parent Comment or Submission
		# and is useful for traversing up the comment tree
		try:
			if self.link_id and self.link_id == self.parent_id:
				return Submission.get_by_id(self.link_id[3:])
			else:
				return Comment.get_or_none(Comment.id == self.parent_id[3:])
		except:
			# TODO probably should raise an Exception here
			return None

	def submission(self):
		return Submission.get_by_id(self.link_id[3:])

	class Meta:
		database = db_instance
		indexes = (
			(("score", "link_id"), False),
		)


def create_tables():

	table_list = [Submission, Comment]
	db_instance.create_tables(models=table_list)

	# attempt to add any columns that are new, to the database
	migrator = SqliteMigrator(db_instance)

	submission_table_cols = [i.name for i in db_instance.get_columns(Submission._meta.table_name)]
	if Submission.detoxify_prediction.name not in submission_table_cols:
		migrate(
			migrator.add_column(Submission._meta.table_name, 'detoxify_prediction', Submission.detoxify_prediction),
		)

	comment_table_cols = [i.name for i in db_instance.get_columns(Comment._meta.table_name)]
	if Comment.detoxify_prediction.name not in comment_table_cols:
		migrate(
			migrator.add_column(Comment._meta.table_name, 'detoxify_prediction', Comment.detoxify_prediction),
		)
