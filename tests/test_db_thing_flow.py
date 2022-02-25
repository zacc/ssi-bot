import pytest
from playhouse.sqliteq import SqliteQueueDatabase

from bot_db.db import Thing
MODELS = [Thing]

test_db = SqliteQueueDatabase(':memory:')


class DBTestCase():
	def setup_function(self):

		test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
		test_db.connect()
		test_db.create_tables(MODELS)
		print(test_db)

	def teardown_function(self):
		test_db.drop_tables(MODELS)
		test_db.close()


class TestThingFlow(DBTestCase):

	def test_text_image_flow(self):
		default_thing = {'bot_username': 'testbot',
					'source_name': 't3_new_submission',
					'author': 'testuser',
					'text_generation_parameters': {}}
		thing = Thing.create(**default_thing)

		assert thing.status == 1

		thing.generated_text = "This was generated"
		thing.text_generation_attempts += 1
		thing.save()

		assert thing.status == 7
