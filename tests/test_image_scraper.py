
from generators.scraper import ImageScraper


class TestImageDownload():

	def test_scraper_image_download(self):

		scraper = ImageScraper()
		image_url = scraper._download_image_for_search_string("sportsfan-bot", {'type': 'scraper', 'image_post_search_prefix': 'sport', 'prompt': "Liverpool FC"}, 0)
		print(image_url)
		assert image_url is not None
