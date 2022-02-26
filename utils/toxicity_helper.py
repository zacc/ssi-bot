import logging

from configparser import ConfigParser
from detoxify import Detoxify

from utils import ROOT_DIR


class ToxicityHelper():

	_detoxify = None
	_threshold_map = {'toxicity': 0.7, 'severe_toxicity': 0.05, 'obscene': 0.7, 'identity_attack': 0.7, 'insult': 0.7, 'threat': 0.4, 'sexual_explicit': 0.7}

	def __init__(self, config_section='DEFAULT'):

		self._config = ConfigParser()
		self._config.read(ROOT_DIR / 'ssi-bot.ini')

		self.load_config_section(config_section)

		self._detoxify = Detoxify('unbiased-small')

	def load_config_section(self, config_section):
		# This can be used to re-configure on the fly.
		logging.info(f"Configuring toxicity helper with section {config_section}...")

		for key in self._threshold_map:
			# Loop through all of the detoxify keys,
			# and see if one exists in the config section for this bot.
			# If so, then update the map.
			config_key = f"{key}_threshold"
			if config_key in self._config[config_section]:
				self._threshold_map[key] = self._config[config_section].getfloat(config_key)

	def text_above_toxicity_threshold(self, input_text):
		logging.info(f"ToxicityHelper, testing {input_text}")

		try:
			results = self._detoxify.predict(input_text)
		except:
			logging.exception(f"Exception when trying to run detoxify prediction on {input_text}")

		logging.info(f"ToxicityHelper, results are {results}")

		if self._threshold_map.keys() != results.keys():
			logging.warning(f"Detoxify results keys and threshold map keys do not match. The toxicity level of the input text cannot be calculated.")
			return True

		for key in self._threshold_map:
			if results[key] > self._threshold_map[key]:
				return True
