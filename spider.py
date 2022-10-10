import justext
import os
import requests
import scrapy

DATADIR = "data/"

# Saves the policy found at the given URL to a text file with name file_name (default "policy.txt") inside DATADIR
def save_policy_text(policy_url, file_name = "policy"):
	file_name = DATADIR + file_name + ".txt"

	print("Saving policy text to", file_name)

	response = requests.get(policy_url)

	paragraphs = justext.justext(response.content, justext.get_stoplist("Italian"))

	output_text = ""

	for paragraph in paragraphs:
		if not paragraph.is_boilerplate:
			output_text += paragraph.text + " "

	try:
		f = open(file_name, 'x')
	except FileExistsError:
		f = open(file_name, 'w')

	f.write(output_text)

# Assumes url starts with protocol identifier (ie "https://" et al)
# Returns the whole domain (including subdomains, "www" ...)
def get_domain_from_url(url):
	domain = url.split('/')[2]
	return domain

class PolicySpider(scrapy.Spider):
	name = 'policyspider'
	start_urls = ['https://corriere.it/']

	def save_policy_html(self, response, file_name = "policy"):
		file_name = DATADIR + file_name + ".html"

		try:
			f = open(file_name, 'x')
		except FileExistsError:
			f = open(file_name, 'w')

		print("Saving html")
		f.write(response.css('*').get())

	def parse(self, response):
		print("Setting up data directory")
		try:
			os.mkdir(DATADIR)
		except FileExistsError:
			print("Data directory already present")

		print("Parsing")

		domain = get_domain_from_url(response.request.url)
		policy_file_name = 
		# print(domain)

		link_to_policy = response.xpath("//a[contains(text(), 'Cookie')]/@href").get()
		if link_to_policy is not None:
			print("Found a link to a privacy policy")
			link_to_policy = 'https:' + link_to_policy

			save_policy_text(link_to_policy)

			request =  scrapy.Request(url = link_to_policy, callback = self.save_policy_html)
			print("Yielding")
			yield request