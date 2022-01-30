
from collections import OrderedDict

from nltk import pos_tag, TweetTokenizer
from nltk.tokenize import sent_tokenize


def main():

	samples = [
		'I am a fan of the Miami Dolphins. AMA!',
		'LAD WE AINT THE WORLD SERIES',
		"With the Broncos' loss to the Chargers today, the Broncos have lost four in a row, including one in Denver. The last time this happened was in 1999.",
		"Tottenham have been relegated to the Championship since a February 2018 fixture against Newcastle",
		"Luka Doncic has been traded to the Boston Celtics for a draft pick, source tells ESPN.",
		"I think James Harden is so good that it's safe to say that the Rockets are the GOAT.",
		"Lebron on shooting up the Cavs: I was never really happy with the team. I'm not a shooter anymore, I'm just a basketball player, not a star athlete. I'm not a superstar athlete now, I'm just a guy who plays basketball",
		"Celtics fans, what are your thoughts on the draft lottery?",
		"Kelvin Benjamin has been signed to a $420M contract. This will be his first full season with the New Orleans Saints",
		"Marlins trade Joey Votto to the Yankees for Mike Trout.",

	]

	for text in samples:
		print('---------')
		print('input: ', text)

		# Split into sentences
		sentences = sent_tokenize(text)
		first_sentence = sentences[0]

		# Remove numbers
		# first_sentence = first_sentence.translate({ord(ch): None for ch in '0123456789'})

		# remove numbers and tokenize the text
		tokenized = TweetTokenizer().tokenize(first_sentence)

		# remove single letter tokens
		tokenized = [i for i in tokenized if len(i) > 1]
		# remove duplicates from the token list
		tokenized = list(OrderedDict.fromkeys(tokenized))

		# put nltk tags on it
		pos_tagged_text = nltk.pos_tag(tokenized)
		# print('pos_tagged', pos_tagged_text)

		# Extract all nouns, verbs and adverbs
		search_keywords = [i for i in pos_tagged_text if (i[1][:2] in ['NN', 'VB', 'RB'])]

		print('Filtered keywords:', search_keywords)
		print('length', len(search_keywords))

		print('final: ', ' '.join([i[0] for i in search_keywords[:10]]))

if __name__ == '__main__':
	main()
