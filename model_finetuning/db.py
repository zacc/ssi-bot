#!/usr/bin/env python3

import logging
import os
import time

from peewee import *

db_file_path = os.path.join('pushshift.sqlite3')
db_instance = SqliteDatabase(db_file_path, thread_safe=True, pragmas={'journal_mode': 'wal2', 'foreign_keys': 0})


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
	parent_id = TextField()
	score = IntegerField()
	stickied = BooleanField(default=False)

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
