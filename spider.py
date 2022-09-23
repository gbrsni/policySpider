import justext
import os
import requests
import scrapy

DATADIR = "data/"

# Saves the policy found at the given URL to a text file with name fileName (default "policy.txt") inside DATADIR
def savePolicyText(policyURL, fileName = "policy.txt"):
	fileName = DATADIR + fileName

	print("Saving policy text to", fileName)

	response = requests.get(policyURL)

	paragraphs = justext.justext(response.content, justext.get_stoplist("Italian"))

	outputText = ""

	for paragraph in paragraphs:
		if not paragraph.is_boilerplate:
			outputText += paragraph.text + " "

	try:
		f = open(fileName, 'x')
	except FileExistsError:
		f = open(fileName, 'w')

	f.write(outputText)

class PolicySpider(scrapy.Spider):
	name = 'policyspider'
	start_urls = ['https://corriere.it/']

	def savePolicyHtml(self, response, fileName = "policy.html"):
		fileName = DATADIR + fileName

		try:
			f = open(fileName, 'x')
		except FileExistsError:
			f = open(fileName, 'w')

		print("Saving html")
		f.write(response.css('*').get())

	def parse(self, response):
		print("Setting up data directory")
		try:
			os.mkdir(DATADIR)
		except FileExistsError:
			print("Data directory already present")

		print("Parsing")

		linkToPolicy = response.xpath("//a[contains(text(), 'Cookie')]/@href").get()
		if linkToPolicy is not None:
			print("Found a link to a privacy policy")
			linkToPolicy = 'https:' + linkToPolicy

			savePolicyText(linkToPolicy)

			request =  scrapy.Request(url = linkToPolicy, callback = self.savePolicyHtml)
			print("Yielding")
			yield request