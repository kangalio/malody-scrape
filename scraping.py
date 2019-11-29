import shutil, hashlib, gzip, os
from zipfile import ZipFile, BadZipFile
from multiprocessing import Pool
import requests
from util import *

def download(url, output_path):
	def try_download():
		# ~ from urllib.request import urlretrieve
		# ~ urlretrieve(url, output_path)
		# ~ return
		
		# ~ with requests.get(url, stream=True, timeout=2) as r:
			# ~ with open(output_path, 'wb') as f:
				# ~ for chunk in r.iter_content():
					# ~ f.write(chunk)
		with requests.get(url, timeout=2) as r:
			with open(output_path, 'wb') as f:
				f.write(r.content)
	
	try:
		retry(try_download, 20, verbose=True)
	except Exception as e:
		if os.path.exists(output_path):
			print("Deleting incomplete download")
			os.remove(output_path)
		raise Panic(url) from e

"""def try_unzip(zip_path):
	try:
		with ZipFile(zip_path, "r") as zip_obj:
			zip_obj.extractall(os.path.dirname(zip_path))
		os.remove(zip_path)
		return True
	except BadZipFile:
		return False

def try_ungzip(src, dst):
	try:
		with gzip.open(src, 'rb') as f_in:
			with open(dst, 'wb') as f_out:
				shutil.copyfileobj(f_in, f_out)
		os.remove(src)
		return True
	except OSError:
		return False

def download_maybe_compressed(url, output_path):
	target_dir = os.path.dirname(output_path)
	compressed = os.path.join(target_dir, "tempfile")
	
	urlretrieve_retry(url, compressed)
	
	# If extension is .mc (probably stands for Malody Compressed), the
	# file MIGHT be a zip that needs to be extracted first
	if output_path.endswith(".mc"):
		if try_unzip(compressed): return
	
	if try_ungzip(compressed, output_path): return
	
	# This happens when it was uncompressed
	os.rename(compressed, output_path)

def md5(path): return hashlib.md5(open(path, "rb").read()).hexdigest()

def download_chart(info):
	sid = info["data"]["sid"]
	uid = info["data"]["uid"]
	
	for file_data in info["data"]["list"]:
		fileid = file_data["file"]
		filename = file_data["name"]
		
		target_dir = f"output/_song_{sid}/{uid}"
		output_path = os.path.join(target_dir, filename)
		
		# Check if file already exists via hash comparison
		if os.path.exists(output_path):
			supposed_md5 = file_data["hash"]
			if md5(output_path) == supposed_md5:
				print(f"Skipping {filename} (already downloaded)")
				continue
			else:
				temp_path = os.path.join(target_dir, "temp")
				os.rename(output_path, temp_path)
				if try_ungzip(temp_path, output_path) and \
						md5(output_path) == supposed_md5:
					print(f"Existing {filename} was automatically detected and compressed as GZip")
					continue
				else:
					print(f"{filename} doesn't match website hash. Re-downloading")
		
		url = f"http://chart.mcbaka.com/{sid}/{uid}/{fileid}"
		os.makedirs(target_dir, exist_ok=True)
		
		download_maybe_compressed(url, output_path)"""

# Returns if the path matches the given md5 hash
def hash_match(path, md5):
	if not os.path.exists(path): return False
	return md5 == hashlib.md5(open(path, "rb").read()).hexdigest()

# Unzips and removes zip afterwards
def try_unzip(zip_path):
	try:
		with ZipFile(zip_path, "r") as zip_obj:
			zip_obj.extractall(os.path.dirname(zip_path))
		os.remove(zip_path)
		return True
	except BadZipFile:
		return False

# ~ # Ungzip, remove original file afterwards
# ~ def try_ungzip(src, dst):
	# ~ try:
		# ~ with gzip.open(src, 'rb') as f_in:
			# ~ with open(dst, 'wb') as f_out:
				# ~ shutil.copyfileobj(f_in, f_out)
		# ~ os.remove(src)
		# ~ return True
	# ~ except OSError:
		# ~ return False

# Returns whether unzipping made the hash match
# Throws exception when it can't cope with the situation anymore.
def try_to_match_hash(output_path, temp_path, md5):
	# If hash already matches, well, then we're done already
	if hash_match(output_path, md5):
		return True
	
	# ~ shutil.move(output_path, temp_path)
	os.rename(output_path, temp_path)
	
	# Maybe file is meant to be unzipped
	if try_unzip(temp_path):
		# If hash matches unzipped file too, done
		if hash_match(output_path, md5):
			return True
		else:
			raise Panic("Hash mismatch (or file is missing) after unzip")
	
	# ~ # Maybe file is meant to be un-gzipped
	# ~ if try_ungzip(temp_path, output_path):
		# ~ # If hash matches uncompressed file, fine
		# ~ if hash_match(output_path, md5):
			# ~ return True
		# ~ else:
			# ~ raise Panic("Hash mismatch after un-gzip")
	
	return False

def download_file(info, target_dir, dsid):
	# Path to place the final file in
	output_path = os.path.join(target_dir, info["name"])
	# Construct a temporary file path to use
	temp_path = os.path.join(target_dir, "tempfile")
	
	# If file exists
	if os.path.exists(output_path):
		# If the file matches, or can be transformed in a way
		# to match the hash, fine
		if try_to_match_hash(output_path, temp_path, info["hash"]):
			print(f"Already exists: {info['name']}")
			return True
		# The file doesn't match in any way, so redownload it is
	
	# Construct URL to download the file from
	# ~ url = f"http://chart.malody.cn/{dsid}/{info['uid']}/{info['file']}"
	url = f"http://chart.malody.cn/{dsid}/0/{info['file']}"
	# Download the file
	print(f"Downloading {info['name']}...")
	download(url, output_path)
	
	if try_to_match_hash(output_path, temp_path, info["hash"]):
		return True
	
	raise Panic(f"{output_path} can't be hash-matched: {url}")

# IMPORTANT!!!!!!!
# For the download url we _need_ to use the *dsid*!!
# For output dir the sid is used!
def download_chart(info):
	info = info["data"]
	target_dir = f"output/_song_{info['sid']}/{info['cid']}"
	os.makedirs(target_dir, exist_ok=True)
	
	for fileinfo in info["list"]:
		try:
			download = lambda: download_file(fileinfo, target_dir, info["dsid"])
			# Sometimes the download corrupts I think and the hash
			# doesn't match. Just try again for that case
			retry(download, 3, verbose=True)
		except Panic as e:
			print(f"Panic: {e}")
	

def download_everything(session, chart_list, cid_filter=None, start=0):
	if cid_filter:
		chart_list = [c for c in chart_list if c["id"] in cid_filter]
	
	num_charts = len(chart_list)
	
	if os.path.exists("faulty-charts.json"):
		with open("faulty-charts.json", "r") as f:
			faulty_cids = json.load(f)
	else:
		faulty_cids = []
	
	cids = map(lambda chart: chart["id"], chart_list[start:])
	i = start - 1
	for info in map(session.get_chart_download, cids):
		i += 1
		
		chart = chart_list[i]
		cid = chart["id"]
		print()
		if int(info["code"]) >= 0:
			print(f"[{i+1}/{num_charts}] Downloading CID={cid} {chart['title']} | {chart['version']}")
		
			try:
				download_chart(info)
				if cid in faulty_cids: faulty_cids.remove(cid)
				continue
			except Exception as e:
				logger.exception("Something went wrong. Please report this")
		else:
			print(f"[{i+1}/{num_charts}] Skipping CID={cid} {chart['title']} | {chart['version']} | Error code {info['code']}")
		
		# Code only gets to this point if something went wrong
		if cid not in faulty_cids: faulty_cids.append(cid)
		with open("faulty-charts.json", "w") as f:
			json.dump(faulty_cids, f, indent=4)
