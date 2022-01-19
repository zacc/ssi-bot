
Minimum Python requirement: Python 3.6

Full support/developed on:
Ubuntu-flavor Linux.

A setup guide for Windows is here:
https://docs.google.com/document/d/1t9b8QSsWiTU5uSBRZQBavKn9jK040t08


### Overview

This is the framework for an AI/Machine Learning Reddit Chatbot.

The bot works by reading the comments and then using OpenAI's GPT-2 model to generate a new comment. The AI model is smart enough to generate a new comment on the topic.

This framework also contains scripts and tools for fine-tuning the GPT-2 model. Fine-tuning will give your chatbot a personality and make it generate text in particular themes.

An overview of AI/Machine Learning Text Generation can be found here:
https://huggingface.co/tasks/text-generation


### Choosing training material

Choosing good training material for your bot is very important.
Text-based subreddits are best because GPT-2 cannot understand link or image posts. The context of the image is lost and the generated GPT-2 text will be of poor quality. 
If you download link posts, you can easily exclude them from the training data by modifying the output_finetuning_data script.

#### Bannable/offensive content
Bots using this framework have been banned by reddit.

Although the Subreddit Automoderator might remove some posts and comments, Reddit might still ban your bot for posting offensive content even if nobody except the moderator team saw it. The subreddit moderators have no control over this ban.
It's very important to use the negative_keywords feature in the config to prevent bad text being posted to Reddit in the first place.

The best way to avoid getting your bot banned is to train it with safe material in the first place. Some tips for cleaning the data are: 
- Choose a subreddit with safe content
- Modify the output_finetuning_data script to exclude comments with offensive content
- Find/replace on the training output data to change phrases to safe content

#### Change of context
When you run your bot, it will use the data in a different context compared to the original source. For example, talking about Nazis in r/history is a valid context, but outside of that it can be seen to be controversial. The context is important when deciding if your bot is posting offensive content or not.


### Glossary / PyPI packages used
`simpletransformers` An open source Python package made by Thilina Rajapakse. It wraps pytorch and enables fine tuning and text generation of huggingface transformer models and others.

Documentation: https://simpletransformers.ai/docs/installation/

`peewee` A database ORM that creates Python access to the database. SQL functions and queries can be completed using Python functions. It's like SQLAlchemy but much much easier to use!

Documentation: http://docs.peewee-orm.com/en/latest/index.html

`praw` A Python package to interface with Reddit's API. It streamlines a lot of the hard work of interacting with the API.

Documentation: https://praw.readthedocs.io/en/latest/

## OVERVIEW OF CREATING A GPT-2 BOT
This is a very broad overview of the workflow for creating an ssi-bot

1. Decide your bot's personality and choose which subreddit to get training data from.
Be aware that GPT-2 cannot understand images, so subreddits which focus on images are not
really suitable. Subreddits where text is the main content are most suitable.
1. Download the subreddit training data from Pushshift
1. Format and output the training data into a text file
1. Finetune the GPT-2 model on a GPU (Google Collaboratory or locally)
1. Setup a server (or 24/7 computer) to run the reddit bot on
1. Install/unzip the model in `models/` directory
1. Create your reddit bot on reddit and enable the API acccess
1. Setup the config files
1. Run the bot!

## FINETUNING A GPT-2 MODEL
### Summary
A GPT-2 model already has a very good knowledge of language and a large vocabulary.

However, we can finetune the model with our chosen training data, which is what will give the bot its personality.
Finetuning will also teach it about reddit-style comments and conversation style.
This is done by showing it a few dozen megabytes of existing reddit data.

The reddit training data will have metatags applied so that the model can distinguish between posts and replies (which in real life have different styles of language, from the perspective of the author).

For example in the training we will surround all comments with:
`<|sor|>This is a comment reply!<|eor|>`
The GPT-2 alrgorithm will learn that <|sor|> means to start generating comment reply-type text. 
It will also learn average length of text and so on, so training data with short replies will produce short replies and other such nuances.

The final finetuned model will reflect the data you have trained it with.

### Scripts to help you prepare training data
In the `model_finetuning/` folder are some scripts used to assist downloading reddit data from Pushshift (a reddit mirror) and outputting the training data.

`download_reddit_training_data.py`
This script downloads submission and comment JSON files from Pushshift and saves them to the hard disk. It will take a long time due to the rate limiting on Pushshift.
It then parses the JSON file and pushes it into a database.
Putting the file into a database makes it easier to filter the data (by score, exclude NSFW, etc).
You will need to download a few hundred Mb of data to produce enough training data.

`output_training_data.py`
This script will output all of the data from the pushshift database into two text files for finetuning.
One text file is the training data and the other is a control sample used for evaluating the fine tuning process.

Using the 124M GPT-2 model, at least 10mb of training data is preferred.
With less than 10mb of data you are at risk of overfitting the model to the data and you won't get good results.

To use these scripts, copy `dataset_template.ini` to `dataset.ini` and configure it accordingly.

`ssi-bot_finetuning_notebook.ipynb`
This interactive Python notebook contains all the code and instructions for fine-tuning the GPT-2 model.
It can be uploaded to Google Colaboratory to use a free GPU, or can be run locally on Jupyter Notebook/etc if you have your own GPU.


`Google Query`
Some people have used Google Query to download the training data faster. You'll need to write your own script to output the data into the same structure of the output_training_data.py script.

### Customizing the output script to collect better training output data

The default script will just output all of the training data, excluding that which contains negative keywords.

By writing custom queries and joining up multiple sets of lists together we can create a custom training text file

Here are some examples of using Peewee to filter the reddit data we downloaded.

Text submissions are better for GPT-2. With link submissions, the context of the image is often lost.

    # Filter only text submissions
     
    all_submissions = list(db_Submission.select().
		where(db_Submission.is_self) &
				(fn.Lower(db_Submission.subreddit).in_([s.lower() for s in training_subreddits])) &
				(fn.Lower(db_Submission.author).not_in([a.lower() for a in author_blacklist]))))


Subreddits that have enormous volumes of data can be filtered down using a keyword on the title.

	# Filtering by one subreddit
	# Excluding titles by a single keyword
     
	all_submissions = []
     
	filtered_submissions = list(db_Submission.select().
		where((fn.Lower(db_Submission.subreddit) == 'minecraft') &
				(fn.Lower(db_Submission.title).contains('java')))
     
	all_submissions.extend(filtered_submissions)

Repetitive content makes the model and the bot repeat that content too much. We can avoid it by excluding posts that include certain keywords.

	# Excluding multiple strings
     
	import operator
	from functools import reduce
          
	all_submissions = []
     
	exclude_title_strings = ['Weekly Thread', 'Moderator News']
     
	# creates a list of OR filters excluding each of the title strings
	# ~ means negative, to exclude all titles containing the word java
	exclude_title_filters = reduce(operator.or_, [~fn.Lower(db_Submission.title).contains(s) for s in exclude_title_strings])
     
	filtered_submissions = list(db_Submission.select().
		where((fn.Lower(db_Submission.subreddit) == 'learnpython') &
				(exclude_title_filters))
     
	all_submissions.extend(filtered_submissions)

Submissions with short titles often lack context when trained with GPT-2.
We can filter for longer titles with more words which will be more interesting.

	# Filter all selftext posts only
	# Filter by title having a minimum length of 50,
	# but selftext being < 1000 characters
     
	filtered_submissions = list(db_Submission.select().
		where((fn.Lower(db_Submission.subreddit) == 'showerthoughts') &
				(db_Submission.is_self) &
				(fn.Length(db_Submission.title) > 50) &
				(fn.Length(db_Submission.selftext) < 1000))
     
	all_submissions.extend(filtered_submissions)


Official documentation for the peewee ORM is here:
https://docs.peewee-orm.com/en/latest/peewee/querying.html#filtering-records
and a full list of peewee's query operators:
https://docs.peewee-orm.com/en/latest/peewee/query_operators.html


### Finetuning on Google Colaboratory

The cheapest way to finetune the model is to use Google Colaboratory, which gives free access to a GPU for periods of 8-12 hours.

A Python notebook file (`ssi-bot_finetuning_notebook.ipynb`) is kept in the `model_finetuning` directory.

Navigate to https://colab.research.google.com/ and click Upload. Upload the ipynb file and then follow the instructions.

After training, the optimum trained model will be saved in the `best_model` folder. Download the model and unzip it into the `models/` folder of your ssi-bot project.

### Finetuning locally

If you have a powerful GPU at home, you can finetune the bot on your own computer.
Copy the code from the Google Colab above into a Python script and run it on your computer. (And place a pull request on Github too, so we can improve the codebase).

## RUNNING THE BOT ON REDDIT

Although the bot is finetuned on a GPU, a CPU is sufficient for using the
model to generate text.

Any modern CPU can be used, having around 4Gb of RAM or more is the main requirement.

In order to run on SubSimGPT2Interactive, we require the bot to be running 24/7.
This means putting it on a VPS/server, or an old laptop in your house could suffice too.


### Setup your Python environment
1. Install packages with `pip install -Ur requirements.txt` (Advised: Use virtualenv)
To keep a terminal window open on Ubuntu Server, use an application
called `tmux`

ssi-bot Config file
1. Copy and rename ssi-bot_template.ini to ssi-bot.ini
1. Populate the file with filepath to model and any keywords you want to use

Create the bot account, setup reddit app and associated PRAW Config file
1. Create the bot account on reddit
1. Logged in as the bot, navigate to https://www.reddit.com/prefs/apps
1. Click "are you a developer? Create an app.." and complete the flow
1. Copy and rename praw_template.ini to praw.ini
1. Set all the data in praw.ini from step 3 above

Running the bot
1. The bot is run by typing `python run.py`
