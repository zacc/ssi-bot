#!/usr/bin/env python3

import torch

from detoxify import Detoxify
from db import (Comment as db_Comment, Submission as db_Submission)


def main():

	cuda_available = torch.cuda.is_available()
	detox = Detoxify('unbiased-small', device='cuda' if cuda_available else 'cpu')

	all_submissions = db_Submission.select().where(db_Submission.detoxify_prediction.is_null(True))

	for s in all_submissions.iterator():
		print('submission', s.id)
		s.detoxify_prediction = detox.predict(f"{s.title} {s.selftext}".strip())
		s.save()

	all_comments = db_Comment.select().where(db_Comment.detoxify_prediction.is_null(True))
	for c in all_comments.iterator():
		print('comment', c.id)
		c.detoxify_prediction = detox.predict(c.body)
		c.save()

	print('detoxify predictions complete')

if __name__ == '__main__':
	main()