import re
import json
import random
import ftfy

from configparser import ConfigParser

from functools import reduce
import operator

from datetime import datetime

from peewee import fn
from peewee import Expression

from db import (Comment as db_Comment, Submission as db_Submission)

import concurrent.futures

import sys
# Hack to allow us to import the negative_keywords list
sys.path.append("..")

random.seed()

config = ConfigParser()
config.read('dataset.ini')

# a list of common bots to ignore.
author_list = [
	'AmputatorBot', 'analyzeHistory', 'anti-gif-bot', 'AnimalFactsBot', 'automoderator', 'autotldr', 'auto-xkcd37', 'autourbanbot', 'AyyLmao2DongerBot-v2',
	'backtickbot', 'BadDadBot', 'BaseballBot', 'b0trank', 'Bot_Metric',
	'CakeDay--Bot', 'checks_out_bot', 'ClickableLinkBot', 'CodeFormatHelperBot', 'CoolDownBot', 'CommonMisspellingBot', 'converter-bot', 'could-of-bot',
	'DailMail_Bot', '[deleted]',
	'EmojifierBot', 'enzo32ferrari', 'exponant',
	'fast-parenthesis-bot', 'FatFingerHelperBot', 'FlairHelperBot', 'Freedom_Unit_Bot', 'friendly-bot', 'fukramosbot',
	'GenderNeutralBot', 'gfy_mirror', 'gifv-bot', 'GitCommandBot', 'GitHubPermalinkBot', 'Gyazo_Bot', 'GoodBot_BadBot',
	'haikubot-1911', 'haikusbot', 'HelperBot_', 'highlightsbot', 'HuachiBot',
	'IamYodaBot', 'i-am-dad-bot', 'imguralbumbot', 'ImJimmieJohnsonBot', 'Its_URUGUAY_bot', 'JobsHelperBot', 'JustAHooker', 'kmcc93',
	'LinkFixerBot', 'LinkifyBot', 'link-reply-bot', 'LearnProgramming_Bot', 'LimbRetrieval-Bot', 'LinkExpanderBot',
	'MAGIC_EYE_BOT', 'MaxImageBot', 'Mentioned_Videos', 'metric_units', 'MLBVideoConverterBot', 'ModeratelyHelpfulBot', 'morejpeg_auto',
	'NASCARThreadBot', 'NBA_MOD', 'NFL_Warning', 'NFLVideoConverterBot', 'nice-scores', 'NicolasBotCage', 'Not_RepostSleuthBot',
	'of_have_bot', 'ootpbot', 'originalpostsearcher', 'oofed-bot',
	'parenthesis-bot', 'PicDescriptionBot', 'phonebatterylevelbot', 'PORTMANTEAU-BOT', 'ProgrammerHumorMods', 'BeginnerProjectBot', 'pythonHelperBot',
	'reddit-blackjack-bot', 'Reddit-Book-Bot', 'redditstreamable', 'relevant_post_bot', 'remindmebot', 'repliesnice',
	'RepostSleuthBot', 'RepostCheckerBot', 'ReverseCaptioningBot', 'roastbot', 'RoastBotTenThousand',
	'sexy-snickers', 'should_have_listened', 'Simultate_Me_Bot', 'SmallSubBot', 'SnapshillBot', 'sneakpeekbot',
	'Spam_Detector_Bot', 'Shakespeare-Bot', 'SpellCheck_Privilege', 'StreamableReddit', 'streamablemirrors', 'sub_doesnt_exist_bot', 'SwagmasterEDP',
	'table_it_bot', 'thank_mr_skeltal_bot', 'Thatonefriendlybot', 'THE_GREAT_SHAZBOT', 'TheDroidNextDoor', 'timezone_bot', 'Title2ImageBot', 'TitleToImageBot', 'totesmessenger',
	'twittertostreamable', 'tweetposter', 'TweetsInCommentsBot', 'tweettranscriberbot', 'twitterInfo_bot', 'TwitterVideoBot',
	'User_Simulator',
	'vredditdownloader', 'video_descriptionbot',
	'WaterIsWetBot', 'WellWishesBot', 'WikiTextBot', 'WikiSummarizerBot',
	'xkcd-Hyphen-bot', 'xkcd_transcriber',
	'YoMammaJokebot', 'youtubefactsbot', 'YTubeInfoBot'
	]

lowercase_author_list = [a.lower() for a in author_list]

from utils.keyword_helper import KeywordHelper
# import the default negative keywords
kw_helper = KeywordHelper()
default_negative_keywords = kw_helper._negative_keywords

config_negative_keywords = []

if config['DEFAULT']['negative_keywords']:
	# import config negative keywords
	config_negative_keywords = config['DEFAULT']['negative_keywords'].split(',')

lowercase_neg_kw_list = [a.lower().strip() for a in default_negative_keywords + config_negative_keywords]

mega_negative_keywords_regex = r'\b{}'.format('|'.join(lowercase_neg_kw_list))

# The name of the subreddits trained from
training_subreddits = []

# Pull configs from dataset.ini
if config['DEFAULT']['training_subreddits']:
	training_subreddits = config['DEFAULT']['training_subreddits'].split(',')


def tag_submission(sub):

	if sub.is_self:
		# is_self parameter means it is a selftext submission with code
		return f"<|soss r/{sub.subreddit}|><|sot|>{sub.title}<|sost|>{repr(sub.selftext)[1:-1]}"
	else:
		# if there's no selftext then it's just a linkpost.
		return f"<|sols r/{sub.subreddit}|><|sot|>{sub.title}<|sol|>"


def end_tag_for_submission(sub):
	if sub.is_self:
		return f"<|eoss|>"
	else:
		return f"<|eols|>"


def tag_comment(comment, include_author):

	author_string = ""
	parent_parent = get_parent_parent(comment)
	tag = "r"

	if comment.submission().author == comment.author:
		# the tag changes if it's the op replying
		tag = "opr"
	elif parent_parent:
		if parent_parent.author == comment.author:
			# the tag used changes if 2 posts were before was also the same author
			tag = f"ocr"

	if include_author:
		author_string = f" u/{comment.author}"

	return f"<|so{tag}{author_string}|>{repr(comment.body)[1:-1]}"


def get_parent_parent(db_object):

	try:
		return db_object.parent().parent()
	except Exception as e:
		return None


def gather_comments_for_submission(sub):

	submission_author = sub.author
	parent = sub

	db_object_output_list = [sub]

	for i in range(0, 10):
		if isinstance(parent, db_Submission):
			parent_id = f't3_{parent.id}'
		else:
			parent_id = f't1_{parent.id}'

		# Base comment query which filters all comments by parent_id
		base_comment_query = db_Comment.select().where(
				(db_Comment.parent_id == parent_id) &
				(db_Comment.is_url_only == False) &
				(~fn.Lower(db_Comment.body).regexp(mega_negative_keywords_regex)) &
				(fn.Lower(db_Comment.author).not_in(lowercase_author_list)))

		if i == 0:
			# Prevent comments where the author themselves posts a top-level comment
			base_comment_query = base_comment_query.where(db_Comment.author != submission_author)

		# Score filter is unreliable. 
		top_children = list(base_comment_query.order_by(db_Comment.score.desc()))

		# Alternative top children query to filter by length of the comment
		# top_children = list(base_comment_query.order_by(fn.Length(db_Comment.body).desc()))

		# Alternative top children query to filter by newest comments
		# top_children = list(base_comment_query.order_by(db_Comment.created_utc.desc()))

		for child_comment in top_children:
			parent_parent = get_parent_parent(child_comment)

			# Check that this record's parent text is not identical, because we would prefer variation.
			# Skip ahead to the next comment
			if type(parent) == db_Comment and parent.body.lower() == child_comment.body.lower():
				continue
			if type(parent_parent) == db_Comment and parent_parent.body.lower() == child_comment.body.lower():
				continue

			db_object_output_list.append(child_comment)
			parent = child_comment
			break

		else:
			break

	output_string = ""
	end_tag = ""

	for i, obj in enumerate(db_object_output_list):

		if isinstance(obj, db_Submission):

			output_string += tag_submission(obj)
			end_tag = end_tag_for_submission(obj)

		elif isinstance(obj, db_Comment):
			# For the last comment, do not include the author's name
			# So include_author will be False
			include_author = i < len(db_object_output_list) - 1
			output_string += tag_comment(obj, include_author)

	return output_string + end_tag + "<|endoftext|>"


def main():

	# Check all of the negative keywords can be converted to regex
	for kw in lowercase_neg_kw_list:
		if not kw_helper._test_keyword_is_compilable(kw):
			print(f"Error in negative keyword {kw}, it cannot be converted to regex. You may need to use regex escaping.")
			return

	all_submissions = []

	link_submissions = list(db_Submission.select()
		.where((fn.Lower(db_Submission.subreddit).in_(training_subreddits)) &
				(db_Submission.is_self == False) &
				(~fn.Lower(db_Submission.title).regexp(mega_negative_keywords_regex)) &
				(fn.Lower(db_Submission.author).not_in(lowercase_author_list))))

	selftext_submissions = list(db_Submission.select()
		.where((fn.Lower(db_Submission.subreddit).in_(training_subreddits)) &
				(db_Submission.selftext) &
				(~fn.Lower(db_Submission.title).regexp(mega_negative_keywords_regex)) &
				(~fn.Lower(db_Submission.selftext).regexp(mega_negative_keywords_regex)) &
				(fn.Lower(db_Submission.author).not_in(lowercase_author_list))))

	for s in link_submissions + selftext_submissions:
		if len(s.title.split(' ')) >= 6:
			all_submissions.append(s)

	# file strings for output
	date_string = datetime.today().strftime('%d%m%y%H%M')
	# global filename
	filename = f'training_output_{date_string}'

	# Random sort all of the submissions so we get a mix of types in the 
	# training and evaluation files.
	random.shuffle(all_submissions)
	all_submissions = all_submissions

	split_point = min(int(len(all_submissions) * 0.10), 3000)

	eval_submissions = all_submissions[:split_point]
	train_submissions = all_submissions[split_point:]

	print("Training submissions", len(train_submissions), "Eval submissions", len(eval_submissions))

	# use multiprocessing to speed up the output
	with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:

		counter = 0
		string_counter = 0

		with open(f'{filename}_train.txt', 'a', encoding='utf-8') as fd:
			for return_val, text_gen_string in zip(train_submissions, executor.map(gather_comments_for_submission, train_submissions)):
				counter += 1
				if text_gen_string:
					fd.write(text_gen_string + '\n')
					string_counter += 1

				print(f'Training {return_val.id} subs counted: {counter}. strings output: {string_counter} {round(string_counter/counter, 2)}, completion: {round(counter/len(train_submissions), 2)}')

		counter = 0
		string_counter = 0

		with open(f'{filename}_eval.txt', 'a', encoding='utf-8') as fd:
			for return_val, text_gen_string in zip(eval_submissions, executor.map(gather_comments_for_submission, eval_submissions)):
				counter += 1
				if text_gen_string:
					fd.write(text_gen_string + '\n')
					string_counter += 1

				print(f'Eval {return_val.id} subs counted: {counter}. strings output: {string_counter} {round(string_counter/counter, 2)}, completion: {round(counter/len(eval_submissions), 2)}')


if __name__ == '__main__':
	main()
