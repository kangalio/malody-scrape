import requests, json, os, sys, subprocess, hashlib;
from concurrent.futures import ThreadPoolExecutor;

target_dir = "/home/kangalioo/desktop/malody/beatmap"
cfduid = "de82f976c9753d7465c334a4dedaa1ff31531048380";
login_key = "51b3880de58765d77593a57c7f9a53b7";
login_uid = "126488";

def get_download_response(chart_id):
	url = "http://m.mugzone.net/cgi/chart/download?v=2&cid=%s&key=%s&uid=%s" % (chart_id, login_key, login_uid);
	response = requests.get(url, cookies={"__cfduid": cfduid}).text;
	return response;

def get_resource(sid, uid, fileid):
	url = get_resource_url(sid, uid, fileid);
	print("From URL %s" % url);
	# ~ response = requests.get(url).content;
	response = urllib.request.urlopen(url).read();
	return response;

# ~ def get_resource_size(sid, uid, fileid):
	# ~ url = get_resource_url(sid, uid, fileid);
	# ~ requests.head(url).

def get_resource_url(sid, uid, fileid):
	url = "http://chart.mcbaka.com/%s/%s/%s" % (sid, uid, fileid);
	return url;

target_dir = "/home/kangalioo/desktop/malody-beatmaps";
chart_dirs = os.listdir(target_dir);
def do():
	chart_dir = chart_dirs.pop();
	cid = chart_dir[5:];
	cjson = json.loads(get_download_response(cid));
	sid = str(cjson["data"]["sid"]);
	cuid = str(cjson["data"]["uid"]);
	dest_dir = "_sid_%s" % sid;
	
	print("mkdir --parents %s/%s" % (dest_dir, cuid));
	print("mv %s/%s/* %s/%s" % (chart_dir, cuid, dest_dir, cuid));

pool = ThreadPoolExecutor(max_workers=50);
for _ in range(len(chart_dirs)): pool.submit(do);
pool.shutdown();

"""
with open("malody-charts.txt") as chart_id_file:
	chart_ids = [c.strip() for c in chart_id_file.readlines()];
	def make_network_request():
		chart_id = chart_ids.pop();
		chart_json = json.loads(get_download_response(chart_id));
		print("Chart JSON: " + str(chart_json));
		if chart_json["code"] == -1000:
			print("Key has expired: %s. Please replace it." % login_key);
			sys.exit(1);
		elif chart_json["code"] < 0:
			print("Some error occured. JSON = %s" % str(chart_json));
			print("CID %s is skipped" % chart_id);
			return;
		chart_sid = chart_json["data"]["sid"];
		chart_uid = chart_json["data"]["uid"];
		rel_song_dir = "_cid_%s/%s" % (chart_id, chart_uid);
		song_dir = "%s/%s" % (target_dir, rel_song_dir);
		files = [(f["name"], f["file"], f["hash"]) for f in chart_json["data"]["list"]];
		os.makedirs(song_dir, exist_ok = True);
		for (filename, fileid, filehash) in files:
			file_path = "%s/%s" % (song_dir, filename);
			rel_file_path = "%s/%s" % (rel_song_dir, filename);
			if os.path.exists(file_path):
				real_filehash = hashlib.md5(open(file_path, "rb").read()).hexdigest();
				if real_filehash != filehash:
					print("Hash of file %s doesn't match - redownloading" % rel_file_path);
				else:
					print("Skipping %s - File exists" % rel_file_path);
					continue;
			print("Downloading %s for CID %s" % (filename, chart_id));
			# ~ fo = open(file_path, "wb");
			# ~ resource = get_resource(chart_sid, chart_uid, fileid);
			# ~ fo.write(resource);
			# ~ fo.close();
			url = get_resource_url(chart_sid, chart_uid, fileid);
			subprocess.run(["curl", url, "-o", file_path]);
		print("");
	
	def pop_chart_ids_until_empty():
		while len(chart_ids) > 0:
			try:
				make_network_request();
			except Exception as e:
				print("Exception, retrying: " + str(e));
				try:
					make_network_request();
				except Exception as e:
					print("Exception, not retrying again: " + str(e));
	
	while chart_ids.pop() != "9948": pass
	pop_chart_ids_until_empty();"""