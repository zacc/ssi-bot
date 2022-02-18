import psutil
import torch


def get_available_memory(gpu=False):

	if gpu:
		# Only supporting NVidia and the first (0-index) GPU at this stage
		reserved_memory = torch.cuda.memory_reserved(0)
		allocated_memory = torch.cuda.memory_allocated(0)
		available_memory = (reserved_memory - allocated_memory) / 1024
		print(f'gpu available_memory {available_memory}')
		return available_memory

	else:
		available_memory = psutil.virtual_memory().available / 1024
		print(f'cpu available_memory {available_memory}')
		return available_memory
