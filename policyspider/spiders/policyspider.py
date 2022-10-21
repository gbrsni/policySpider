import justext
import os
import requests
import scrapy
import json
import textract
import tempfile

from scrapy_selenium import SeleniumRequest

DATADIR = "data"


class BadPolicyError(Exception):
	"""To be raised when no policy has been found"""
	pass

def get_text_from_pdf(pdf_file):
	pdf_file_name = os.path.join(tempfile.gettempdir(), pdf_file.name)
	output_text = textract.process(pdf_file_name)

def save_policy_text(policy_url, file_name):
	"""Saves the policy found at the given URL to a text file with name file_name inside DATADIR"""
	file_name = os.path.join(DATADIR, file_name)

	print("Saving policy text to", file_name)

	response = requests.get(policy_url)

	paragraphs = justext.justext(response.content, justext.get_stoplist("Italian"))

	output_text = ""

	for paragraph in paragraphs:
		output_text += paragraph.text + " "

	if output_text == "" or output_text is None:
		raise BadPolicyError("Couldn't find policy at " + policy_url)
	elif output_text.startswith("404 Not Found") \
		or output_text.startswith("403 Forbidden") \
		or output_text.startswith("Forbidden"):
		raise BadPolicyError("Bad policy at " + policy_url)
	
	if output_text.startswith("%PDF-"):
		pdf_file = tempfile.NamedTemporaryFile(suffix = ".pdf", prefix = "policy_")
		pdf_file.write(response.content)
		output_text = get_text_from_pdf(pdf_file)
		pdf_file.close()
		if output_text == "" or output_text is None:
			raise BadPolicyError("Couldn't find policy at " + policy_url)

	policy_word_count = len(output_text.split())
	if policy_word_count < 500:
		raise BadPolicyError("Policy too short " + policy_url)

	try:
		f = open(file_name, "x")
	except FileExistsError:
		f = open(file_name, "w")

	f.write(output_text)
	f.close()

# xpath structure "//a[contains(., 'privacy') or contains(., 'Policy')]/@href"
def make_xpath_query(keywords):
	query = "//a["
	for i, keyword in enumerate(keywords):
		if i != 0:
			query += " or "
		query += "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '" + keyword +"')" # This exists to make the query case insensitive
	return query + "]/@href"

def get_domain_from_url(url):
	"""Returns None if input is none or empty string"""
	if url is None or url == "":
		return None
	return url.split("/")[2]

class PolicySpider(scrapy.Spider):
	name = "policyspider"

	custom_settings = {
		"DEFAULT_REQUEST_HEADERS" : {
			"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", # This is the default value
			"Accept-Language": "it",
		}
	}

	def start_requests(self):
		websites_file = open("resources/websites.json", "r")
		websites_file_json = json.load(websites_file)
		start_urls = websites_file_json["websites"]
		websites_file.close()
		
		for url in start_urls:
			yield SeleniumRequest(url = url, callback=self.parse)

	def save_policy_html(self, response, file_name = "policy"):
		file_name = DATADIR + file_name + ".html"

		try:
			f = open(file_name, "x")
		except FileExistsError:
			f = open(file_name, "w")

		print("Saving html")
		f.write(response.css("*").get())
		f.close()

	def parse(self, response):
		current_url = response.request.url
		domain = get_domain_from_url(current_url)
		policy_file_name = "policy_" + domain + ".txt"
		print("Examining " + domain)

		print("Setting up data directory")
		try:
			os.mkdir(DATADIR)
		except FileExistsError:
			print("Data directory already present")

		print("Parsing")

		keywords_file = open("resources/policy_keywords.json", "r")
		keywords_file_json = json.load(keywords_file)
		xpath_query = make_xpath_query(keywords_file_json["keywords"])
		keywords_file.close()

		link_to_policy = response.selector.xpath(xpath_query).get()
		
		success = False

		if link_to_policy is not None and link_to_policy != "javascript:void":
			print("Found a link to a privacy policy at " + link_to_policy)

			if link_to_policy.startswith("//"): # Some websites do this for some reason
				link_to_policy = "https:" + link_to_policy
			elif link_to_policy.startswith(domain): # Add https:// if protocol isn't specified
				link_to_policy = "https://" + link_to_policy
			elif link_to_policy.startswith("/"): # If relathive path is used
				link_to_policy = "https://" + domain + link_to_policy
			elif link_to_policy == "#":
				link_to_policy = current_url
			elif not link_to_policy.startswith("https://") and not link_to_policy.startswith("http://"): # Relative path not beginning with /
				link_to_policy = "https://" + domain + "/" + link_to_policy

			try:
				save_policy_text(link_to_policy, policy_file_name)
				success = True
			except BadPolicyError:
				print("Error while pulling policy at " + link_to_policy)
				success = False
		else:
			link_to_policy = None
			success = False

		yield {
			"url" : current_url,
			"policy_domain" : get_domain_from_url(link_to_policy),
			"policy_url" : link_to_policy,
			"policy_file" : policy_file_name,
			"success" : success
		}