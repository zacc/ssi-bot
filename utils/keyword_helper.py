import re

from configparser import ConfigParser


class KeywordHelper():

	# These hard-coded negative keywords are used to prevent the bot posting distasteful stuff.
	# It's only inteded as a basic defence.
	# Operator should train their model to avoid falling back on this.
	_default_negative_keywords = [
		('ar', 'yan'), ('ausch, witz'),
		('black', ' people'),
		('child p', 'orn'), ('chi', 'nk'), ('concentrati', 'on camp'),
		('da', 'go'),
		('fag', 'got'), ('fuc', 'k you'),
		('hit', 'ler'), ('holo', 'caust'),
		('inc', 'est'), ('israel'),
		('jew', 'ish'), ('je', 'ws'),
		('k', 'ill'), ('kk', 'k'),
		('lol', 'i'),
		('maste', 'r race'), ('mus', 'lim'),
		('nation', 'alist'), ('na', 'zi'), ('nig', 'ga'), ('nig', 'ger'),
		('pae', 'do'), ('pak', 'i'), ('pale', 'stin'), ('ped', 'o'),
		('rac' 'ist'), (' r', 'ape'), ('ra', 'ping'), ('ret', 'ard'),
		('sl', 'ut'), ('sp', 'ic'), ('swas', 'tika'),
		('tra', 'nny'),
		('white p', 'ower'),
	]

	_positive_keywords = []
	_negative_keywords = ["".join(s) for s in _default_negative_keywords]

	def __init__(self, bot_username=None):

		self._config_section_key = bot_username if bot_username else 'DEFAULT'

		self._config = ConfigParser()
		self._config.read('ssi-bot.ini')

		self._positive_keywords += self._config[self._config_section_key].get('positive_keywords', '').lower().split(',')

		# Append user's custom negative keywords
		self._negative_keywords += self._config[self._config_section_key].get('negative_keywords', '').lower().split(',')

	def positive_keyword_matches(self, text):
		if self._positive_keywords:
			return [keyword for keyword in self._positive_keywords if re.search(r"\b{}".format(keyword), text, re.IGNORECASE)]
		return []

	def negative_keyword_matches(self, text):
		# Negative keyword is matched with a starting boundary so basic word forms
		# like plurals are matched, for example humans and humanoid would both match for just the keyword human.

		if self._negative_keywords:
			return [keyword for keyword in self._negative_keywords if re.search(r"\b{}".format(keyword), text, re.IGNORECASE)]
		return []
