import justext
import os
import pandas as pd
import requests
import scrapy
import json
import textract
import tempfile
import time

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from twisted.internet.error import DNSLookupError

DATADIR = "data"
RESOURCES_DIR = "resources"
CSV_WEBSITES_FILE_NAME = "allsites.csv"
JSON_WEBSITES_FILE_NAME = "websites.json"
KEYWORS_FILE_NAME = "policy_keywords.json"


class BadPolicyError(Exception):
	"""To be raised when no policy has been found"""
	pass

def get_text_from_pdf(pdf_file):
	pdf_file_name = os.path.join(tempfile.gettempdir(), pdf_file.name)
	output_text = textract.process(pdf_file_name)
	return output_text

def selenium_get_policy_from_url(url):
	"""Returns the text found at url when opened with selenium"""
	print("Trying selenium at " + url)
	
	options = Options()
	options.headless = True
	driver = webdriver.Firefox(options=options)
	driver.get(url)
	time.sleep(5)
	source = driver.page_source

	driver.quit()

	res = ""	
	paragraphs = justext.justext(source, justext.get_stoplist("Italian"))

	for paragraph in paragraphs:
		res = res + paragraph.text + " "

	return res

def policy_text_is_good(policy_text):
	"""Returns true if the input text is considered good.
	Returns false and prints what the problems is if a problem is found"""

	spolicy_text = str(policy_text)

	if spolicy_text == "" or spolicy_text is None:
		print("Couldn't find policy text")
		return False
	elif spolicy_text.startswith("404 Not Found") \
		or spolicy_text.startswith("403 Forbidden") \
		or spolicy_text.startswith("Forbidden"):
		print("Bad policy (Error)")
		return False

	policy_word_count = len(spolicy_text.split())
	if policy_word_count < 500:
		print("Policy too short")
		return False

	return True

def save_policy_text(policy_url, file_name):
	"""Saves the policy found at the given URL to a text file with name file_name inside DATADIR"""
	file_name = os.path.join(DATADIR, file_name)

	print("Saving policy text to", file_name)

	output_text = ""

	response = requests.get(policy_url)

	if policy_url.split(".")[len(policy_url.split(".")) - 1] == "pdf":
		print("Policy may be a pdf file, attempting to extract plain text")
		pdf_file = tempfile.NamedTemporaryFile("wb", suffix = ".pdf", prefix = "policy_")
		pdf_file.write(response.content)
		output_text = get_text_from_pdf(pdf_file)
		pdf_file.close()
	else:
		source = response.content

		paragraphs = justext.justext(source, justext.get_stoplist("Italian"))

		for paragraph in paragraphs:
			output_text = output_text + paragraph.text + " "

	if not policy_text_is_good(output_text):
		output_text = selenium_get_policy_from_url(policy_url)
	
	if not policy_text_is_good(output_text):
		raise BadPolicyError("No viable policy found at " + policy_url)

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

def websites_from_csv():
	csv_file_path = os.path.join("resources", CSV_WEBSITES_FILE_NAME)
	csv = pd.read_csv(csv_file_path)
	domains = csv['url'].tolist()
	urls = []
	for domain in domains:
		if not domain.startswith("https://") or domain.startswith("http://"):
			urls.append("https://" + domain)
		else:
			urls.append(domain)

	print("Loaded " + str(len(urls)) + " websites")
	
	return urls


class PolicySpider(scrapy.Spider):
	name = "policyspider"

	custom_settings = {
		"DEFAULT_REQUEST_HEADERS" : {
			"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", # This is the default value
			"Accept-Language": "it",
		}
	}

	start_urls = []

	def start_requests(self):
		# websites_file = open(os.path.join(RESOURCES_DIR, JSON_WEBSITES_FILE_NAME), "r")
		# websites_file_json = json.load(websites_file)
		# start_urls = websites_file_json["websites"]
		# websites_file.close()

		self.start_urls = websites_from_csv()
		
		for url in self.start_urls:
			yield scrapy.Request(url = url,
				callback = self.parse,
				errback = self.parse_err)

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
		keywords_file = open(os.path.join(RESOURCES_DIR, KEYWORS_FILE_NAME), "r")
		keywords_file_json = json.load(keywords_file)
		xpath_query = make_xpath_query(keywords_file_json["keywords"])
		keywords_file.close()

		link_to_policy = response.selector.xpath(xpath_query).get()

		success = False

		if link_to_policy is not None and not link_to_policy.startswith("javascript:void"):
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
		
		uses_iubenda = "cdn.iubenda.com" in response.text

		yield {
			"url" : current_url,
			"policy_domain" : get_domain_from_url(link_to_policy),
			"policy_url" : link_to_policy,
			"policy_file" : policy_file_name,
			"uses_iubenda" : uses_iubenda,
			"success" : success,
			"ignore" : False,
		}
	
	def parse_err(self, failure):
		if failure.check(DNSLookupError):
			request = failure.request
			if not request.url.startswith("www."):
				print("Trying to add www. to " + request.url)
				self.start_urls.append("www." + request.url)