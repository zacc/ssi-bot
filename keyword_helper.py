import re

from configparser import ConfigParser


class KeywordHelper():

	# These hard-coded negative keywords are used to prevent the bot posting distasteful stuff.
	# It's only inteded as a basic defence.
	# Operator should train their model to avoid falling back on this.
	_default_negative_keywords = [
		('ar', 'yan'), ('ausch, witz'),
		('black', ' people'),
		('child p', 'orn'), ('concentrati', 'on camp'),
		('fag', 'got'),
		('hit', 'ler'), ('holo', 'caust'),
		('inc', 'est'), ('israel'),
		('jew', 'ish'), ('je', 'ws'),
		('k', 'ill'), ('kk', 'k'),
		('lol', 'i'),
		('maste', 'r race'), ('mus', 'lim'),
		('nation', 'alist'), ('na', 'zi'), ('nig', 'ga'), ('nig', 'ger'),
		('pae', 'do'), ('pale', 'stin'), ('ped', 'o'),
		('rac' 'ist'), (' r', 'ape'), ('ra', 'ping'),
		('sl', 'ut'), ('swas', 'tika'),
	]

	_positive_keywords = []
	_negative_keywords = ["".join(s) for s in _default_negative_keywords]

	def __init__(self):

		self._config = ConfigParser()
		self._config.read('ssi-bot.ini')

		if self._config['DEFAULT']['positive_keywords']:
			self._positive_keywords = self._config['DEFAULT']['positive_keywords'].lower().split(',')
		if self._config['DEFAULT']['negative_keywords']:
			# Append user's custom negative keywords
			self._negative_keywords += self._config['DEFAULT']['negative_keywords'].lower().split(',')

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
