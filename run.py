import logging
import time
from configparser import ConfigParser

from generators.text import ModelTextGenerator
from generators.scraper import ImageScraper
from generators.text2image import Text2Image

from reddit_io import RedditIO

from bot_db.db import create_db_tables


def main():

	bot_config = ConfigParser()
	bot_config.read('ssi-bot.ini')

	# enable minimal logging with a custom format showing the bot's username
	NEW_LOG_FORMAT = '%(asctime)s (%(threadName)s) %(levelname)s %(message)s'
	logging.basicConfig(format=NEW_LOG_FORMAT, level=logging.INFO)

	# Create the database. If the table already exists, nothing will happen
	create_db_tables()

	start_scraper_daemon = False
	start_t2i_daemon = False

	for bot in bot_config.sections():

		# initialise reddit_io
		bot_io = RedditIO(bot_username=bot)

		# Start the reddit IO daemon which will pick up incoming
		# submissions/comments and send outgoing ones
		bot_io.start()

		if bot_io._submission_image_generator == 'scraper' and not start_scraper_daemon:
			start_scraper_daemon = True
		if bot_io._submission_image_generator == 'text2image' and not start_t2i_daemon:
			start_t2i_daemon = True

	# Start the text generation daemon
	mtg = ModelTextGenerator()
	mtg.start()

	if start_scraper_daemon:
		print('starting scraper daemon')
		# Start the image scraper daemon
		imgscr = ImageScraper()
		imgscr.start()

	if start_t2i_daemon:
		print('starting t2i daemon')
		# Start the t2i daemon
		t2i = Text2Image()
		t2i.start()

	# Set up a game loop
	# Cancel it with Ctrl-C
	try:
		while True:
			time.sleep(5)
	except KeyboardInterrupt:
		logging.info('Shutdown')

if __name__ == '__main__':
	main()
