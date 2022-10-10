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

class PolicySpider(scrapy.Spider):
	name = 'policyspider'
	start_urls = ["https://corriere.it/", "https://unieuro.it/", "https://lercio.it/"]

	def save_policy_html(self, response, file_name = "policy"):
		file_name = DATADIR + file_name + ".html"

		try:
			f = open(file_name, 'x')
		except FileExistsError:
			f = open(file_name, 'w')

		print("Saving html")
		f.write(response.css('*').get())

	def parse(self, response):
		domain = (response.request.url).split('/')[2]
		policy_file_name = "policy_" + domain
		print("Examining " + domain)

		print("Setting up data directory")
		try:
			os.mkdir(DATADIR)
		except FileExistsError:
			print("Data directory already present")

		print("Parsing")

		# link_to_policy = response.xpath("//a[contains(text(), 'Policy')]/@href").get()
		link_to_policy = response.xpath("""//a[contains(., 'privacy')
												or contains(., 'Policy')]/@href""").get()
		if link_to_policy is not None:
			print("Found a link to a privacy policy at " + link_to_policy)

			if link_to_policy.startswith("//"): # Some websites do this for some reason
				link_to_policy = "https:" + link_to_policy
			elif link_to_policy.startswith(domain): # Add https:// if protocol isn't specified
				link_to_policy = "https://" + link_to_policy
			elif link_to_policy.startswith("/"): # If relathive path is used
				link_to_policy = "https://" + domain + link_to_policy

			save_policy_text(link_to_policy, policy_file_name)