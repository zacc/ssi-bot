# ssi-bot
All the tools required to setup a GPT-2 Reddit bot for use at places such as [r/SubSimGPT2Interactive](https://www.reddit.com/r/SubSimGPT2Interactive).
## Table of Contents
* [Simplistic Usage Guide](#Simplistic-Usage-Guide)
* [Detailed Setup Guide](#Detailed-Setup-Guide)
  * [Deciding Your Subreddits](#Deciding-Your-Subreddits)
  * [Obtaining Your Training Data](#Obtaining-Your-Training-Data)
  * [Finetuning](#Finetuning)
  * [Configuration](#Configuration)
  * [Running](#Running)
## Simplistic Usage Guide
1. Decide the subreddits you would like to train your bot on.
2. Download the Reddit data via `model_finetuning/download_reddit_finetuning_data.py`.
3. Output properly formatted training files via `model_finetuning/output_finetuning_data.py`.
4. Finetune the GPT-2 model (See [Finetuning](#Finetuning) for details).
5. Download the trained model.
6. Create a bot application for Reddit api access, under your bot's user account.
7. Setup the config files (See [Configuration](#Configuration) for details).
8. Run the bot!
## Detailed Setup Guide
#### Deciding Your Subreddits
TODO (idea: philosophy)
#### Obtaining Your Training Data
Now that you have decided the subreddits you want to train on
#### Finetuning
TODO
#### Configuration
TODO
#### Running
TODO
## Additional Notes
#### Major PyPi Packages Used
`simpletransformers` - A PyTorch and `transformer` based library, enabling higher level fine-tuning and text generation APIs.
	https://simpletransformers.ai
