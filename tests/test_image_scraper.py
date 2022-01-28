
from daemon.scraper_text_to_image import ImageScraper


class TestImageDownload():

	def test_title_parsing(self):

		scraper = ImageScraper()
		image_url = scraper._download_image_for_search_string("Liverpool FC", {'type': 'scraper', 'prompt': ''}, 0)
		print(image_url)

		assert image_url is not None
