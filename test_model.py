
from simpletransformers.language_generation import LanguageGenerationModel, LanguageGenerationArgs

# This script generates 5 samples of text locally


def main():

	model_path = "models/<model_folder>/"
	lgm_args = {'fp16': False,
				'cache_dir': f"{model_path}.cache/",
			}

	# Enable use_cuda if your graphics card allows it.
	model = LanguageGenerationModel("gpt2", model_path, args=lgm_args, use_cuda=False)

	args = {
		'max_length': 1000,
		'num_return_sequences': 5,
		'repetition_penalty': 1.01,
		'stop_token': '<|endoftext|>',
		'temperature': 0.8,
		'top_k': 40,
	}

	prefix = '<|soss|><|sot|>'

	for text in model.generate(prompt=prefix, args=args, verbose=True):

		print("<<<<<<<<")
		print(text)
		continue


if __name__ == '__main__':
	main()
