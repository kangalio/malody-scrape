import os, json, logging

logger = logging.getLogger()

class Panic(Exception):
	def __init__(self, text):
		super().__init__(f"\x1B[1;31m{text}\x1B[0m")

def cached(fn, cache_path, force = False):
	if os.path.exists(cache_path) and not force:
		return json.load(open(cache_path))
	else:
		result = (fn)()
		json.dump(result, open(cache_path, "w"))
		return result

def retry(fn, tries, verbose=True):
	last_exception = None
	
	for i in range(tries):
		try:
			result = (fn)()
			if i > 0 and verbose: print(f"Success on attempt {i+1}!")
			return result
		except Exception as e:
			last_exception = e
	
	raise Panic(f"[All {tries} attempts failed] {str(last_exception)}")

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
