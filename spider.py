import justext
import os
import requests
import scrapy
import json

DATADIR = "data/"


class NoPolicyError(Exception):
	"""To be raised when no policy has been found"""
	pass

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

	if output_text == "" or output_text is None:
		raise NoPolicyError("Couldn't find policy at " + policy_url)

	try:
		f = open(file_name, 'x')
	except FileExistsError:
		f = open(file_name, 'w')

	f.write(output_text)
	f.close()

# xpath structure "//a[contains(., 'privacy') or contains(., 'Policy')]/@href"
def make_xpath_query(keywords):
	query = "//a["
	for i, keyword in enumerate(keywords):
		if i != 0:
			query += " or "
		query += "contains(., '" + keyword +"')"
	return query + "]/@href"

# This is a one liner but having the function name improves readability
def get_domain_from_url(url):
	return url.split('/')[2]

class PolicySpider(scrapy.Spider):
	name = 'policyspider'

	websites_file = open("resources/websites.json", 'r')
	websites_file_json = json.load(websites_file)
	start_urls = websites_file_json["websites"]
	websites_file.close()

	def save_policy_html(self, response, file_name = "policy"):
		file_name = DATADIR + file_name + ".html"

		try:
			f = open(file_name, 'x')
		except FileExistsError:
			f = open(file_name, 'w')

		print("Saving html")
		f.write(response.css('*').get())
		f.close()

	def parse(self, response):
		domain = get_domain_from_url(response.request.url)
		policy_file_name = "policy_" + domain
		print("Examining " + domain)

		print("Setting up data directory")
		try:
			os.mkdir(DATADIR)
		except FileExistsError:
			print("Data directory already present")

		print("Parsing")

		keywords_file = open("resources/policy_keywords.json", 'r')
		keywords_file_json = json.load(keywords_file)
		link_to_policy = response.xpath(make_xpath_query(keywords_file_json["keywords"])).get()
		keywords_file.close()
		
		success = True

		if link_to_policy is not None:
			print("Found a link to a privacy policy at " + link_to_policy)

			if link_to_policy.startswith("//"): # Some websites do this for some reason
				link_to_policy = "https:" + link_to_policy
			elif link_to_policy.startswith(domain): # Add https:// if protocol isn't specified
				link_to_policy = "https://" + link_to_policy
			elif link_to_policy.startswith("/"): # If relathive path is used
				link_to_policy = "https://" + domain + link_to_policy

			try:
				save_policy_text(link_to_policy, policy_file_name)
			except NoPolicyError:
				success = False
		else:
			success = false

		yield {
			"domain" : domain,
			"policy_domain" : get_domain_from_url(link_to_policy),
			"policy_url" : link_to_policy,
			"policy_file" : policy_file_name,
			"success" : success
		}