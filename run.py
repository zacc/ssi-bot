import logging
import time
from configparser import ConfigParser

from model_text_generator import ModelTextGenerator
from reddit_io import RedditIO

from db import create_db_tables


def main():

	# enable minimal logging with a custom format showing the bot's username
	NEW_LOG_FORMAT = '%(asctime)s (%(threadName)s) %(levelname)s %(message)s'
	logging.basicConfig(format=NEW_LOG_FORMAT, level=logging.INFO)

	# Create the database. If the table already exists, nothing will happen
	create_db_tables()

	bot_config = ConfigParser()
	bot_config.read('ssi-bot.ini')

	for bot in bot_config.sections():

		# initialise reddit_io
		bot_io = RedditIO(bot_username=bot)
		# synchronize bot's own posts to the databse
		bot_io.synchronize_bots_comments_submissions()

		# Start the reddit IO daemon which will pick up incoming
		# submissions/comments and send outgoing ones
		bot_io.start()

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
