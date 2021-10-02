#!/usr/bin/env python3
import random

from datetime import datetime

from peewee import fn

from configparser import ConfigParser

from db import (Comment as db_Comment, Submission as db_Submission)

import concurrent.futures

config = ConfigParser()
config.read('dataset.ini')

# a list of common bots to ignore the comments of. They will pollute the training data with junk.
# unless you want that, of course..
author_blacklist = [
	'[deleted]',
	'AmputatorBot', 'analyzeHistory', 'anti-gif-bot', 'AnimalFactsBot', 'automoderator', 'autotldr', 'auto-xkcd37', 'autourbanbot', 'AyyLmao2DongerBot-v2',
	'BadDadBot', 'BaseballBot', 'b0trank', 'Bot_Metric',
	'CakeDay--Bot', 'checks_out_bot', 'ClickableLinkBot', 'CodeFormatHelperBot', 'CoolDownBot', 'CommonMisspellingBot', 'converter-bot', 'could-of-bot',
	'DailMail_Bot', '[deleted]',
	'EmojifierBot', 'enzo32ferrari',
	'fast-parenthesis-bot', 'FatFingerHelperBot', 'FlairHelperBot', 'Freedom_Unit_Bot', 'friendly-bot', 'fukramosbot',
	'gfy_mirror', 'gifv-bot', 'GitCommandBot', 'GitHubPermalinkBot', 'Gyazo_Bot', 'GoodBot_BadBot',
	'haikubot-1911', 'haikusbot', 'HelperBot_', 'highlightsbot', 'HuachiBot',
	'IamYodaBot', 'i-am-dad-bot', 'imguralbumbot', 'ImJimmieJohnsonBot', 'Its_URUGUAY_bot', 'JobsHelperBot', 'JustAHooker', 'kmcc93',
	'LinkFixerBot', 'link-reply-bot', 'LearnProgramming_Bot', 'LimbRetrieval-Bot', 'LinkExpanderBot',
	'MAGIC_EYE_BOT', 'MaxImageBot', 'Mentioned_Videos', 'metric_units', 'MLBVideoConverterBot', 'ModeratelyHelpfulBot', 'morejpeg_auto',
	'NASCARThreadBot', 'NBA_MOD', 'NFL_Warning', 'NFLVideoConverterBot', 'nice-scores', 'NicolasBotCage',
	'of_have_bot', 'ootpbot', 'originalpostsearcher',
	'parenthesis-bot', 'PicDescriptionBot', 'phonebatterylevelbot', 'PORTMANTEAU-BOT', 'ProgrammerHumorMods', 'pythonHelperBot',
	'reddit-blackjack-bot', 'Reddit-Book-Bot', 'redditstreamable', 'relevant_post_bot', 'remindmebot', 'repliesnice', 'RepostCheckerBot', 'ReverseCaptioningBot', 'roastbot', 'RoastBotTenThousand',
	'sexy-snickers', 'should_have_listened', 'Simultate_Me_Bot', 'SmallSubBot', 'SnapshillBot', 'sneakpeekbot',
	'Spam_Detector_Bot', 'SpellCheck_Privilege', 'StreamableReddit', 'streamablemirrors', 'sub_doesnt_exist_bot', 'SwagmasterEDP',
	'table_it_bot', 'thank_mr_skeltal_bot', 'THE_GREAT_SHAZBOT', 'timezone_bot', 'Title2ImageBot', 'TitleToImageBot', 'totesmessenger',
	'twittertostreamable', 'tweetposter', 'TweetsInCommentsBot', 'tweettranscriberbot', 'twitterInfo_bot', 'TwitterVideoBot',
	'User_Simulator',
	'vredditdownloader', 'video_descriptionbot',
	'WaterIsWetBot', 'WellWishesBot', 'WikiTextBot', 'WikiSummarizerBot',
	'xkcd-Hyphen-bot', 'xkcd_transcriber',
	'YoMammaJokebot', 'youtubefactsbot', 'YTubeInfoBot'
	]

# A list of bad words. If these words are in the reddit comment, ignore that comment
# A good way to get the bot to behave nicely is to finetune it on healthy content in the first place
# There is usually always enough training data to comfortably filter out junk content like this
negative_keywords = []

# The name of the subreddits trained from
training_subreddits = []

# Pull configs from dataset.ini
if config['DEFAULT']['training_subreddits']:
	training_subreddits = config['DEFAULT']['training_subreddits'].split(',')
if config['DEFAULT']['negative_keywords']:
	negative_keywords = config['DEFAULT']['negative_keywords'].split(',')

# Keywords to be stripped from the dataset output
text_removed = ['[removed', '[deleted']


def gather_comments_for_submission(sub):

	if any(s in sub.selftext for s in negative_keywords):
		# if the submission contains a negative keyword, 
		# ignore it so we don't train the bot on bad stuff
		print(f"{sub.id} contains negative keywords")
		return

	if any(s in sub.selftext for s in text_removed):
		# if the post has been edited or deleted it might contain [removed] or [deleted]
		# if it does, ignore this submission because we can't train on that
		print(f"text_removed selftext: {sub.selftext}")
		return

	record_string = ""
	comments_counted = 0

	if sub.is_self:
		# is_self parameter means it is a selftext submission
		record_string = f"<|soss|><|sot|>{sub.title}<|eot|><|sost|>{sub.selftext}<|eost|>"
		suffix = "<|eoss|>"
	else:
		# if there's no selftext then it's just a linkpost.
		record_string = f"<|sols|><|sot|>{sub.title}<|eot|><|sol|><|eol|>"
		suffix = "<|eols|>"

	parent = sub

	for i in range(0, 10):
		# Only go to x deep in the comments, but this can be increased to capture more data

		if i == 0:
			parent_id = f't3_{parent.id}'
		else:
			parent_id = f't1_{parent.id}'

		# Find all comments with this parent_id
		# Pro-tip: in this query you can filter out any types of comments you don't want in the training data
		# You can also change the sorting method
		comment_list = list(db_Comment.select().where((db_Comment.parent_id == parent_id) &
			(fn.Lower(db_Comment.author).not_in([a.lower() for a in author_blacklist])))
			.order_by(db_Comment.score.desc()))

		if not comment_list:
			# No comments were found.. we've reached the end of the tree
			# Break and return the string and its suffix
			break

		for comment in comment_list:

			if any(s.lower() in comment.body.lower() for s in text_removed):
				print(f"comemnt {comment.id} body has been deleted/removed")
				# Cannot use this comment in the training data
				continue

			if any(s.lower() in comment.body.lower() for s in negative_keywords):
				print(f"comemnt {comment.id} body contains negative keywords")
				# Cannot use this comment in the training data
				continue

			# Check that this record's parent text is not identical.
			# so we don't train the model to repeat itself
			try:
				if comment.body == comment.parent().body:
					print("comment body matches its parent", comment.body, comment.parent().body)
					continue
			except:
				pass

			parent_parent = None

			try:
				# See if we have the parent/parent in the database
				parent_parent = comment.parent().parent()
			except:
				pass

			if parent_parent and parent_parent.author == comment.author:
				# If parent_parent is the same as this comment then use the different tag
				record_string += f"<|soocr|>{comment.body}<|eoocr|>"
				comments_counted += 1
			else:
				record_string += f"<|sor|>{comment.body}<|eor|>"
				comments_counted += 1
			# If we haven't continued by this point we can break the loop
			break

		# Set the parent variable to be this comment
		parent = comment

	return record_string + suffix


def main():

	random.seed()

	bot_name = "training_output"

	all_submissions = []
	# all submissions ordered by date
	all_submissions = list(db_Submission.select().
		where((fn.Lower(db_Submission.subreddit).in_([s.lower() for s in training_subreddits])) &
				(fn.Lower(db_Submission.author).not_in([a.lower() for a in author_blacklist]))))

	# We'll shuffle all the submission records and split them into a training and evaluation
	# lists in a 90/10 ratio. simpletransformers will use the evaluation to test the accuracy
	# of the training
	random.shuffle(all_submissions)

	split_point = int(len(all_submissions) * 0.9)
	training_submissions = all_submissions[:split_point]
	eval_submissions = all_submissions[split_point:]

	print(f'{len(training_submissions)} training submissions, {len(eval_submissions)} evaluation submissions')

	# file name for the output text file
	date_string = datetime.today().strftime('%d%m%y_%H%M')
	counter = 0

	# use concurrent futures (multiprocessing) to speed up the output
	with concurrent.futures.ProcessPoolExecutor() as executor:
		filename = f'{bot_name}_{date_string}_training.txt'

		with open(filename, 'a', encoding='utf-8') as fd:
			for sub, output_text_gen_string in zip(training_submissions, executor.map(gather_comments_for_submission, training_submissions)):
				if output_text_gen_string:
					if counter > 0: fd.write('\n')
					fd.write(f'{output_text_gen_string}' + '<|endoftext|>')
				counter += 1
				print(f'subs counted: {counter}. {round(counter/len(all_submissions), 2)}')

		filename = f'{bot_name}_{date_string}_eval.txt'
		with open(filename, 'a', encoding='utf-8') as fd:
			for sub, output_text_gen_string in zip(eval_submissions, executor.map(gather_comments_for_submission, eval_submissions)):
				if output_text_gen_string:
					if counter > 0: fd.write('\n')
					fd.write(f'{output_text_gen_string}' + '<|endoftext|>')
				counter += 1
				print(f'subs counted: {counter}. {round(counter/len(all_submissions), 2)}')


if __name__ == '__main__':
	main()
