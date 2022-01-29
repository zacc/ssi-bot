default_text_generation_parameters = {
		'max_length': 260,
		'num_return_sequences': 1,
		'prompt': None,
		'temperature': 0.8,
		'top_k': 40,
}

from .model_text_generator import ModelTextGenerator
