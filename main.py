import json, os, logging, multiprocessing
from multiprocessing import Pool
import requests

import scraping
from util import *

class AndroidSession:
	uid = None
	key = None
	
	def __init__(self, uid, key):
		self.uid = uid
		self.key = key
	
	def login(user, password_hash):
		url = "http://m.mugzone.net/cgi/login"
		data = {
			"name": user,
			"psw": password_hash,
		}
		
		result = requests.post(url, data=data, timeout=10).json()
		uid, key = result["data"]["uid"], result["data"]["key"]
		print(f"Session tokens: {uid} {key}")
		return AndroidSession(uid, key)
	
	def get(self, url, params={}, **kw_args):
		params.update({
			"uid": self.uid,
			"key": self.key,
		})
		
		url = "http://m.mugzone.net/cgi/" + url
		
		return requests.get(url, timeout=10, params=params, **kw_args)
	
	def chart_list(self, sid):
		params = {
			# Type of list request. Type 1 would list the 80 most recent
			# songs, type 2 lists the charts of one specific song. Not
			# sure if there's more types.
			"type": 2,
			# Song ID
			"sid": sid,
		}
		
		charts = self.get("list", params).json()
		return charts
	
	def get_chart_info(self, cid):
		params = {
			"type": 1,
			 # Search query
			"word": cid,
		}
		
		results = self.get("list", params).json()
		return results["data"][0]
	
	def get_chart_download(self, cid):
		params = {
			"v": 2,
			"cid": cid,
		}
		
		return retry(lambda: self.get("chart/download", params).json(), 5)

# Meant for usage inside get_song_list(). This is a top-level function
# because Python multiprocessing would complain otherwise
def dl_chart_list_page(i):
	global _mode, _status
	url = "http://m.mugzone.net/page/chart/filter"
	params = {
		# Song status. 0 = Alpha, 1 = Beta, 2 = Stable, 3 = All of them
		"status": _status,
		# Play mode. -1 = All, 0/3/4/5/6/7 = The individual game modes
		"mode": _mode,
		# Number of results to request. The server has only a few valid
		# choices for this param, among of them 10, 18, 30. 10 seems to
		# be the fallback value.
		"count": 30,
		# Page number
		"page": i,
	}
	
	return requests.get(url, timeout=10, params=params).json()

def get_chart_list(mode, status):
	global _mode, _status
	if mode == 0: mode = -1
	elif mode == 1: mode = 0
	elif mode >= 2: mode += 1
	_mode = mode
	if status == 0: status = 3
	else: status -= 1
	_status = status
	
	print("Initializing chart list download...")
	pool = Pool(API_THREADS)
	
	url = "http://m.mugzone.net/page/chart/filter"
	params = {
		# Song status. 0 = Alpha, 1 = Beta, 2 = Stable, 3 = All of them
		"status": status,
		# Play mode. -1 = All, 0/3/4/5/6/7 = The individual game modes
		"mode": mode,
		# Number of results to request. The server has only a few valid
		# choices for this param, among of them 10, 18, 30. 10 seems to
		# be the fallback value.
		"count": 30,
		# Page number
		"page": 0,
	}
	
	first_page = dl_chart_list_page(0)
	num_pages = first_page["data"]["total"]
	print(f"There's a total of {num_pages} pages")
	
	song_list = []
	for i, page in enumerate(pool.imap(dl_chart_list_page, range(num_pages))):
		print(f"Downloaded page {i+1}/{num_pages}")
		song_list.extend(page["data"]["list"])
	
	return song_list

"""
Account 1:
Name=scraper-bot
E-Mail=kangalioo654@gmail.com
Pass=scraper-bot
Hash=53a1dbcbaa38fce050b8f90263b28631

Account 2:
Name=codswallopgam
E-Mail=d1655996@urhen.com
Pass=codswallopgam
Hash=
"""

def main():
	global API_THREADS, logger
	
	multiprocessing.freeze_support()
	
	API_THREADS = 50
	GAMEMODES = ["Key", "Catch", "Pad", "Taiko", "Ring", "Slide"]
	STABILITIES = ["Alpha", "Beta", "Stable"]
	
	# REMEMBER
	#session = AndroidSession.login("scraper-bot", "53a1dbcbaa38fce050b8f90263b28631")
	session = AndroidSession("259089", "1868dd6ea073c6501f183b5ea05a48b3")
	charts = cached(lambda: get_chart_list(0, 0), "chartlist.json", force=False)
	scraping.download_everything(session, charts, start=724-1)
	exit()
	
	gamemode = chooser("Which game mode do you want to download?", [
		"All of them", *GAMEMODES
	])
	stability = chooser("Which stability status do you want to download?", [
		"All of them", *STABILITIES
	])
	mode = chooser("Which download mode?", [
		"Download all charts",
		"Download only those charts that failed in the last run"
	])
	if mode == 0:
		print()
		txt = input("Enter an index to start from (1 to start from the beginning, as usual): ")
		try:
			start = int(txt) - 1
		except ValueError:
			start = 0
	print()
	
	print("Logging in...")
	session = AndroidSession.login("scraper-bot", "53a1dbcbaa38fce050b8f90263b28631")

	chartlist_file = "chartlist"
	if gamemode != 0 or stability != 0:
		chartlist_file += f"-{GAMEMODES[gamemode]}-{STABILITIES[stability]}"
	chartlist_file += ".json"
	
	print("Fetching chart list...")
	fn = lambda: get_chart_list(gamemode, stability)
	charts = cached(fn, chartlist_file, force=False)
	
	if mode == 0:
		print("Downloading the main files...")
		download_everything(session, charts, start=start)
	elif mode == 1:
		with open("faulty-charts.json", "r") as f:
			faulty_cids = json.load(f)
			print(f"Redownloading faulty charts...")
			scraping.download_everything(session, charts, faulty_cids)

	print()
	input("Script finished. Press enter to quit")

if __name__ == "__main__":
	global logger
	logger = logging.getLogger()
	
	try:
		main()
	except:
		logger.exception("Error in main!")
		print()
		input("Press enter to quit/close")
