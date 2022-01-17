import logging
import time
import praw

from model_text_generator import ModelTextGenerator
from reddit_io import RedditIO

from db import create_db_tables


def main():

	_praw = praw.Reddit(config_interpolation="basic")

	# enable minimal logging with a custom format showing the bot's username
	NEW_LOG_FORMAT = f"[{_praw.user.me().name}] " + logging.BASIC_FORMAT
	logging.basicConfig(format=NEW_LOG_FORMAT, level=logging.INFO)

	# Create the database. If the table already exists, nothing will happen
	create_db_tables()

	# initialise reddit_io
	reddit_io = RedditIO()
	# synchronize bot's own posts to the databse
	reddit_io.synchronize_bots_comments_submissions()

	# Start the reddit IO daemon which will pick up incoming
	# submissions/comments and send outgoing ones
	reddit_io.start()

	# Start the text generation daemon
	mtg = ModelTextGenerator()
	mtg.start()

	# Set up a game loop
	# Cancel it with Ctrl-C
	try:
		while True:
			time.sleep(5)
	except KeyboardInterrupt:
		logging.info('Shutdown')

if __name__ == '__main__':
	main()
