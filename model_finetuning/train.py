from simpletransformers.language_modeling import LanguageModelingModel
from datetime import datetime

# edit these to include the names of the training and eval .txt files created by output_finetuning_data.py
training_file = "bot_train.txt"
eval_file = "bot_eval.txt"

# the model type to use, you can usually just leave this as-is unless you'd like to experiment with other transformers
model_type = "gpt2"
# IF USING GPT2: for the small model, use just "gpt2", otherwise append "-medium"/"-large"/"-xl" depending on the model size you'd like to use
# anything above small is very unlikely to run unless you have a whole lot of memory and a beefy GPU - even the colab instance usually can't do medium
model_name = "gpt2"

# if set to False, training will occur exclusively on the CPU without multiprocessing (this will be EXTREMELY slow but will work on more systems)
use_gpu = False

current_date_time = datetime.now()
bot_label = "bot_" + current_date_time.strftime("%d%m%Y_%H%M")

args = {
    "overwrite_output_dir": True,
    "learning_rate": 1e-4,
    # larger batch sizes will use more training data but consume more ram
    "train_batch_size": 4,
    # accumulation steps
    "gradient_accumulation_steps": 1,
    "max_steps": 12000,

    # Use text because of grouping by reddit submission
    "dataset_type": "simple",
    # Sliding window will help it manage very long bits of text in memory
    "sliding_window": True,
    "max_seq_length": 512,

    "mlm": False, # has to be false for gpt-2

    "evaluate_during_training": True,
    # default 2000, will save by default at this step.
    "evaluate_during_training_steps": 2000,
    "use_cached_eval_features": True,
    "evaluate_during_training_verbose": True,

    # don't save optimizer and scheduler we don't need it
    "save_optimizer_and_scheduler": False,
    # Save disk space by only saving on checkpoints
    "save_eval_checkpoints": True,
    "save_model_every_epoch": False,
    # disable saving each step to save disk space
    "save_steps": -1, 

    "use_multiprocessing": use_gpu, # set to false when not using a gpu due to instability (often throws RuntimeErrors)

    "output_dir": f"{bot_label}/",
		"best_model_dir": f"{bot_label}/best_model",
}

model = LanguageModelingModel(model_type, model_name, use_cuda=use_gpu)

model.train_model(train_file=training_file, eval_file=eval_file, args=args, verbose=True)
