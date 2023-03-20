import logging
import os
import time

import pandas as pd
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

RESOURCES_DIR = "resources"
CSV_WEBSITES_FILE_NAME = "finalsites.csv"

logging.basicConfig(encoding = 'utf-8', level = logging.INFO, format = "%(asctime)s %(message)s")

def websites_from_csv():
	csv_file_path = os.path.join(RESOURCES_DIR, CSV_WEBSITES_FILE_NAME)
	csv = pd.read_csv(csv_file_path)
	domains = csv['url'].tolist()
	urls = []
	for domain in domains:
		if not domain.startswith("https://") or domain.startswith("http://"):
			urls.append("https://" + domain)
		else:
			urls.append(domain)

	logging.info("Loaded " + str(len(urls)) + " websites")
	
	return urls

def make_xpath_query(keywords):
	query = "//button["
	for i, keyword in enumerate(keywords):
		if i != 0:
			query += " or "
		query += "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '" + keyword +"')" # This exists to make the query case insensitive
	return query + "]"

urls = websites_from_csv()

keywords = ["accetta tutt", "accept all", "accetta e contiuna", "accept and continue", "accetta i cookie", "accept cookies"]

total_fresh_cookies = 0
total_accepted_cookies = 0
times_accepted = 0

for url in urls:
	logging.info("Current site: " + url)

	options = Options()
	options.headless = True
	driver = webdriver.Firefox(options=options)
	try:
		driver.get(url)
	except:
		continue
	time.sleep(1)
	# source = driver.page_source

	fresh_cookies = driver.get_cookies()
	logging.debug(str(fresh_cookies))
	logging.info("Cookies on page visit: " + str(len(fresh_cookies)))

	for keyword in keywords:
		try:
			# accept_button = driver.find_element(By.LINK_TEXT, keyword)
			
			xpath_query = make_xpath_query(keywords)

			accept_button = driver.find_element(By.XPATH, xpath_query)
		except NoSuchElementException:
			accept_button = None
		if accept_button is not None:
			break
	
	if accept_button is None:
		logging.warning("No button to accept all cookies found at " + url)
	else:
		try:
			accept_button.click()
		except:
			continue
		time.sleep(1)

		try:
			accepted_cookies =  driver.get_cookies()
		except:
			continue
		logging.debug(str(accepted_cookies))
		logging.info("Cookies on accept all: " + str(len(accepted_cookies)))

		total_fresh_cookies = total_fresh_cookies + len(fresh_cookies)
		total_accepted_cookies = total_accepted_cookies + len(accepted_cookies)
		times_accepted = times_accepted + 1

	driver.quit()

print("Total fresh cookies: " + str(total_fresh_cookies))
print("Total accepted cookies: " + str(total_accepted_cookies))
print("Times accepted: " + str(times_accepted))
print("Avg fresh to accepted: " + str(total_fresh_cookies / total_accepted_cookies))

# Total fresh cookies: 199
# Total accepted cookies: 351
# Times accepted: 66
# Avg fresh to accepted: 0.5669515669515669