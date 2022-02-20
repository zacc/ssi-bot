import time

from peewee import IntegerField, TextField, TimestampField
from playhouse.signals import Model, pre_save
from playhouse.sqlite_ext import JSONField
from playhouse.sqliteq import SqliteQueueDatabase

db = SqliteQueueDatabase('bot_db/bot-db.sqlite3', pragmas={'journal_mode': 'wal', 'foreign_keys': 1})


class Thing(Model):
	# This table is not meant to represent a complete relationship of submissions/comments on reddit

	# Its behaviour is more of a log to track submissions and comments
	# that have had replies attempted and prevent replying twice

	# It also acts as a job queue of sorts, for the model text generator daemon

	# timestamp representation of when this record was entered into the database
	created_utc = TimestampField(default=time.time, utc=True)
	status = IntegerField(default=1)

	# The bot which submitted this thing. *NOT* the author
	bot_username = TextField()

	# the praw *name* of the original comment or submission,
	# where t3_ prefix = submission, t1_ = comment, t4_ = message
	source_name = TextField()

	# Author of the post (Redditor's username)
	author = TextField()
	# the subreddit used by new_submission job type
	subreddit = TextField(null=True)

	# json object of the model parameters, passed into the generator daemon function
	text_generation_parameters = JSONField(null=True)
	# Count text generation attempts. In normal operation this will only be 0 or 1
	text_generation_attempts = IntegerField(default=0)
	# text generated by model and returned to the job
	generated_text = TextField(null=True)

	# Image generation parameters; scraper or text2img GAN
	image_generation_parameters = JSONField(null=True)
	# Counter for image generation attempts
	image_generation_attempts = IntegerField(default=0)
	# File path to image on disk, used in URL submissions
	generated_image_path = TextField(null=True)

	# attempts to post the generated_text back to reddit
	reddit_post_attempts = IntegerField(default=0)

	# The 'name' of the object posted back to reddit
	# where t3_ prefix = submission, t1_ = comment, t4_ = message
	posted_name = TextField(null=True)

	class Meta:
		database = db


@pre_save(sender=Thing)
def on_presave_handler(model_class, instance, created):
	# This handler stores all business logic for how a thing/job status changes

	# 9 = FAILED
	# 8 = COMPLETE
	# 7 = SUBMIT_READY
	# 5 = IMAGE_GEN
	# 3 = TEXT_GEN
	# 1 = NEW

	if instance.status >= 8:
		# Status might already be set to 8 when the thing has come from the sync
		return

	text_gen_attempts_allowed = 3
	image_gen_attempts_allowed = 3
	reddit_submit_attempts_allowed = 1

	before_status = instance.status

	if (instance.text_generation_attempts >= text_gen_attempts_allowed and instance.generated_text is None) or \
		(instance.image_generation_attempts >= image_gen_attempts_allowed and instance.generated_image_path is None) or \
		(instance.reddit_post_attempts >= reddit_submit_attempts_allowed and instance.posted_name is None):
		# Attempts have been attempted and no content was created so fail the job
		instance.status = 9

	elif instance.posted_name is not None or instance.text_generation_parameters is None:
		# If it has a posted_name then it's been posted to reddit and it's complete.
		# Or if it doesn't have text_generation_parameters at all, set to 8
		instance.status = 8

	elif instance.text_generation_parameters and instance.generated_text is None:
		# Thing has text gen parameters but hasn't yet generated text
		instance.status = 3

	elif instance.image_generation_parameters and instance.generated_image_path is None:
		# Thing has image gen parameters but hasn't yet generated a path
		instance.status = 5

	elif instance.generated_text and (instance.generated_image_path or instance.image_generation_parameters is None):
		# Text has been generated and either an image is ready or no image is to be made.
		instance.status = 7

	# print(f'updating status of {instance} from {before_status} to {instance.status}')


def create_db_tables():

	db.create_tables(models=[Thing])
	# these stop/start calls are required
	# because of nuance in SqliteQueueDatabase
	db.stop()
	db.start()
