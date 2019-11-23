import json, os, logging
import multiprocessing
from multiprocessing import Pool
import requests

def cached(fn, cache_path, force = False):
	if os.path.exists(cache_path) and not force:
		return json.load(open(cache_path))
	else:
		result = (fn)()
		json.dump(result, open(cache_path, "w"))
		return result

def retry(fn, tries):
	for i in range(tries):
		try:
			result = (fn)()
			if i > 0: print(f"Success after {i} attempt{'s' if i > 1 else ''}!")
			return result
		except Exception:
			LOGGER.exception("Caught exception (retrying):")
	
	raise Exception(f"Couldn't download after {tries} tries!")

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

def urlretrieve_retry(url, output_path):
	from urllib.request import urlretrieve
	import shutil
	
	def try_download():
		with requests.get(url, stream=True, timeout=10) as r:
			with open(output_path, 'wb') as f:
				shutil.copyfileobj(r.raw, f)
	retry(try_download, 7)

def download_chart(info):
	from zipfile import ZipFile
	import hashlib
	
	sid = info["data"]["sid"]
	uid = info["data"]["uid"]
	
	for file_data in info["data"]["list"]:
		fileid = file_data["file"]
		filename = file_data["name"]
		
		target_directory = f"output/_song_{sid}/{uid}"
		output_path = f"{target_directory}/{filename}"
		
		# Check if file already exists via hash comparison
		if os.path.exists(output_path):
			supposed_md5 = file_data["hash"]
			md5 = hashlib.md5(open(output_path, "rb").read()).hexdigest()
			if md5 == supposed_md5:
				print(f"Skipping {filename} (already downloaded)")
				continue
			else:
				print(f"{filename} doesn't match website hash. Re-downloading.")
		
		url = f"http://chart.mcbaka.com/{sid}/{uid}/{fileid}"
		os.makedirs(target_directory, exist_ok=True)
		
		zip_parse_failed = False
		
		# If extension is .mc (probably stands for Malody
		# Compressed), the file MIGHT be a zip that needs to be
		# extracted first. Sometimes it's not though
		if output_path.endswith(".mc"):
			try:
				zip_path = f"{target_directory}/temp.zip"
				urlretrieve_retry(url, zip_path)
				
				with ZipFile(zip_path, "r") as zip_obj:
					zip_obj.extractall(target_directory)
				
				os.remove(zip_path)
			except Exception:
				# Then the file was apparently not a zip
				zip_parse_failed = True
		
		if not output_path.endswith(".mc") or zip_parse_failed:
			urlretrieve_retry(url, output_path)

def download_everything(session, chart_list, cid_filter=None):
	pool = Pool(API_THREADS)
	
	if cid_filter:
		chart_list = [c for c in chart_list if c["id"] in cid_filter]
	
	num_charts = len(chart_list)
	
	if os.path.exists("faulty-charts.json"):
		with open("faulty-charts.json", "r") as f:
			faulty_cids = json.load(f)
	else:
		faulty_cids = []
	
	cids = map(lambda chart: chart["id"], chart_list)
	for i, info in enumerate(pool.imap(session.get_chart_download, cids)):
		chart = chart_list[i]
		cid = chart["id"]
		print()
		if int(info["code"]) >= 0:
			print(f"[{i+1}/{num_charts}] Downloading CID={cid} {chart['title']} | {chart['version']}")
		
			try:
				download_chart(info)
				if cid in faulty_cids: faulty_cids.remove(cid)
				continue
			except Exception:
				LOGGER.exception("Something went wrong. Please report this")
		else:
			print(f"[{i+1}/{num_charts}] Skipping CID={cid} {chart['title']} | {chart['version']} | Error code {info['code']}")
		
		# Code only gets to this point if something went wrong
		if cid not in faulty_cids: faulty_cids.append(cid)
		with open("faulty-charts.json", "w") as f:
			json.dump(faulty_cids, f, indent=4)

def chooser(question, options):
	print(question)
	for i, option in enumerate(options):
		print(f" {i+1}) {option}")
	
	query = "Enter the number of your answer: "
	while True:
		try:
			answer = int(input(query)) - 1
			if answer >= 0 and answer < len(options):
				return answer
		except ValueError:
			pass
		query = f"Enter a valid number between 1 and {len(options)}: "

if __name__ == "__main__":
	global API_THREADS, LOGGER
	
	multiprocessing.freeze_support()
	
	API_THREADS = 50
	GAMEMODES = ["Key", "Catch", "Pad", "Taiko", "Ring", "Slide"]
	STABILITIES = ["Alpha", "Beta", "Stable"]
	LOGGER = logging.getLogger()
	
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
		download_everything(session, charts)
	elif mode == 1:
		with open("faulty-charts.json", "r") as f:
			faulty_cids = json.load(f)
			print(f"Redownloading faulty charts...")
			download_everything(session, charts, faulty_cids)

	print()
	input("Script finished. Press enter to quit")
