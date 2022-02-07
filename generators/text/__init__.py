default_text_generation_parameters = {
		'max_length': 1000,
		'num_return_sequences': 1,
		'prompt': None,
		'temperature': 0.8,
		'top_k': 40,
		'repetition_penalty': 1.008,
		'stop_token': '<|endoftext|>',
}

from .model_text_generator import ModelTextGenerator
