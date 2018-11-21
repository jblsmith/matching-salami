import os
import youtube_dl
import numpy as np
import pandas as pd
import json
import dataset
from apiclient.discovery import build
import time
import mutagen.mp3
import plistlib

# Handy functions
def ensure_dir(path):
	if not os.path.exists(path):
		os.makedirs(path)

def printjson(rawjson):
	print json.dumps(rawjson,sort_keys=True,indent=4)

# Point to folders and metadata files:
downloaded_audio_folder = os.getcwd() + "/downloaded_audio"
ensure_dir(downloaded_audio_folder)
salami_public_audio_folder = os.path.expanduser("~/Documents/data/SALAMI/audio")
salami_private_audio_folder = os.path.expanduser("~/Documents/data/SALAMI/priv")
salami_public_metadata_path = os.path.expanduser("~/Documents/repositories/") + "salami-data-public/metadata"
salami_public_metadata_file = salami_public_metadata_path + "/metadata.csv"
fingerprint_public_filename = os.getcwd() + "/salami_public_fpdb.pklz"
fingerprint_private_filename = os.getcwd() + "/salami_private_fpdb.pklz"
matchlist_csv_filename = os.getcwd() + "/match_list.csv"
salami_xml_filename = salami_public_metadata_path + "/SALAMI_iTunes_library.xml"
codaich_info_filename = salami_public_metadata_path + "/id_index_codaich.csv"
salami_xml = plistlib.readPlist(open(salami_xml_filename,'r'))
track_keys = salami_xml["Tracks"].keys()
track_to_persistent_id = {tk:salami_xml["Tracks"][tk]["Persistent ID"] for tk in track_keys}
persistent_id_to_track = {track_to_persistent_id[tk]:tk for tk in track_keys}

ydl_opts = {
	'outtmpl': os.path.join(downloaded_audio_folder, u'%(id)s.%(ext)s'),
	'format': 'bestaudio/best',
	'postprocessors': [{
		'key': 'FFmpegExtractAudio',
		'preferredcodec': 'mp3',
		'preferredquality': '192',
	}],
}

# Create the fingerprint database
# 		!! WARNING !!
# 		This command is designed to be run ONCE.
#		Do not overwrite the database unnecessarily.
def create_fingerprint_database(database_filename, audio_folder):
	subcall = ["python","./audfprint/audfprint.py","new","--dbase", database_filename,  audio_folder+"/*/*.mp3"]
	os.system(" ".join(subcall))	

# Load local song metadata
def load_song_info():
	global salami_public_metadata_file
	with open(salami_public_metadata_file, 'r') as f:
		x = f.readlines()
	metadata_lines = [line.strip().split(",") for line in x]
	mddf = pd.DataFrame(metadata_lines[1:], columns=['salami_id'] + [x.lower() for x in metadata_lines[0][1:]])
	# mddf.columns = ['salami_id', 'source', 'annotator1', 'annotator2', 'path',
	# 				'length', 'blank', 'title', 'artist', 'audio_format',
	# 				'ann1_time', 'ann2_time', 'ann1_filename', 'ann2_filename',
	# 				'class', 'genre', 'ann1_date', 'ann2_date',
	# 				'trash1', 'trash2', 'xeqs1', 'xeqs2']
	mddf.index = mddf.salami_id.astype(int)
	return mddf

def get_true_artist(salami_id):
	global codaich_info_filename
	global salami_xml
	global persistent_id_to_track
	cod_df = pd.read_csv(codaich_info_filename)
	index = cod_df.index[cod_df["SONG_ID"]==salami_id]
	if index.empty:
		print "Invalid salami_id. Returning nothing."
		return None, None, None
	persistent_id = cod_df.loc[index]["PERSISTENT_ID"].tolist()[0]
	tk = persistent_id_to_track[persistent_id]
	info = salami_xml["Tracks"][tk]
	if "Artist" in info.keys():
		artist = info["Artist"]
	else:
		artist = ""
	if "Name" in info.keys():
		title = info["Name"]
	else:
		title = ""
	if "Composer" in info.keys():
		composer = info["Composer"]
	else:
		composer = ""
	if "Album" in info.keys():
		album = info["Album"]
	else:
		composer = ""
	return artist, title, composer, album

# Search for a song using the YouTube API client
def search_for_song(salami_id):
	developer_key = json.load(open(os.path.realpath("./keys.json"),'r'))["youtube_developer_key"]
	youtube_handle = build("youtube", "v3", developerKey=developer_key)
	song_info = get_true_artist(salami_id)
	query_text = " ".join(["'"+item+"'" for item in song_info if item != ""])
	search_responses = youtube_handle.search().list(q=query_text, part="id,snippet", maxResults=50, type="video", pageToken="").execute()
	return search_responses

# def store_result_in_database(salami_id, youtube_id, outcome, expected_length, video_length, database=matching_dataset_filename):
# 	ds = dataset.connect('sqlite:///' + matching_dataset_filename)
# 	table = ds['songs']
# 	table.insert(dict(salami_id=salami_id, youtube_id=youtube_id, outcome=outcome, expected_length=expected_length, video_length=video_length))

# Updated function to use readable, human-editable CSV instead of finnicky dataset:
def store_result_in_database(salami_id, youtube_id):
	global matchlist_csv_filename
	df = load_matchlist()
	# if outcome in ["downloaded"]:
	# if outcome in ["stopped", "error"]:
	index = df.index[df['salami_id'] == salami_id].tolist()[0]
	ytid_list = df["candidate_youtube_ids"][index].split(" ")
	if youtube_id in ytid_list:
		print "Already have that youtube ID in the list. Skipping storage step."
	if youtube_id not in ytid_list:
		print "Adding new youtube ID to storage so you can test for matches later."
		df.loc[index,"candidate_youtube_ids"] = " ".join(ytid_list + [youtube_id]).strip()
	# df["youtube_id"][salami_id] = youtube_id
	# df["youtube_length"][salami_id] = video_length
	# table.insert(dict(salami_id=salami_id, youtube_id=youtube_id, outcome=outcome, expected_length=expected_length, video_length=video_length))
	df.to_csv(matchlist_csv_filename, header=True, index=False)

# !!! WARNING !!!
# This overwrites the match list. So, only run it only once to initialize the file.
def create_matchlist_csv():
	global matchlist_csv_filename
	global salami_public_audio_folder
	csv_header = ["salami_id", "salami_length", "youtube_id", "youtube_length", "time_offset", "time_stretch", "pitch_shift", "candidate_youtube_ids", "rejected_youtube_ids"]
	df = pd.DataFrame(columns=csv_header)
	md = load_song_info()
	md.sort_index(inplace=True)
	# Populate with SALAMI IDs
	df.salami_id = md.salami_id
	# Populate with mp3 file lengths, taken from file since metadata doesn't have them all:
	print "Getting SALAMI song lengths..."
	for salid in md.index:
		mp3_path = salami_public_audio_folder + "/" + str(salid) + "/audio.mp3"
		audio = mutagen.mp3.MP3(mp3_path)
		song_length = audio.info.length
		df["salami_length"][salid] = song_length
	df.to_csv(matchlist_csv_filename, header=True, index=False)
	# Note: salami files 1126, 1227, 1327 were flacs mistakenly labelled as mp3s.
	# Also, 1599 isn't a real entry! I deleted it from the metadata file.

# To check actual mp3 lengths against metadata lengths:
# for i in md.index:
# 	diff = df.loc[i]['salami_length'] - float(md.loc[i]["song_duration"])
# 	if ~np.isnan(diff) and diff>1:
# 		print i, diff

def load_matchlist():
	global matchlist_csv_filename
	df = pd.read_csv(matchlist_csv_filename, header=0)
	df = df.fillna("")
	return df

def make_download_attempt(youtube_id, expected_length, max_ratio_deviation=0.2):
	global ydl_opts
	try:
		with youtube_dl.YoutubeDL(ydl_opts) as ydl:
			x = ydl.extract_info('http://www.youtube.com/watch?v='+youtube_id, download=False)
			video_length = x['duration']
			download_title = x['title']
	except:
		print "Video connection failed."
		return "error", 0
	if expected_length == 0:
		ratio_deviation = 0
	else:
		ratio_deviation = np.abs(expected_length-video_length)*1.0/expected_length
	if ratio_deviation > max_ratio_deviation:
		print "Stopping -- unexpected length ({0})".format(youtube_id)
		return "stopped", video_length
	if video_length > 60*10:
		print "Stopping -- longer than 10 minutes without reason ({0})".format(youtube_id)
		return "stopped", video_length
	try:
		with youtube_dl.YoutubeDL(ydl_opts) as ydl:
			x = ydl.download(['http://www.youtube.com/watch?v='+youtube_id])
		# video_handle.streams.first().download(output_path = downloaded_audio_folder, filename = youtube_id)
		print "Successfully downloaded ({0})".format(youtube_id)
		return "downloaded", video_length
	except:
		print "Error downloading video ({0})".format(youtube_id)
		return "error", video_length

# Download at least one video for a song (trying from the top of the search result list)
def download_at_least_one_video(salami_id, search_responses, max_count=10, min_sleep_interval=120):
	print get_true_artist(salami_id)
	# , matching_dataset_filename=matching_dataset_filename):
	global downloaded_audio_folder
	# Look up row in current match_list. We don't want to bother downloading audio for youtube_ids we've already rejected.
	df = load_matchlist()
	index = df.index[df['salami_id'] == salami_id].tolist()[0]
	candidate_list = df["candidate_youtube_ids"][index].split(" ")
	rejects_list = df["rejected_youtube_ids"][index].split(" ")
	metadata = load_song_info()
	outcome = "empty"
	try_count = 0
	expected_length = metadata.loc[salami_id]["song_duration"]
	try:
		expected_length = int(expected_length)
	except:
		expected_length = 0
	if (try_count>=len(search_responses.get("items"))):
		print "There are no search results to parse. Quitting with Nones."
		return None, None
	while (outcome != "downloaded") and (try_count<max_count) and (try_count<len(search_responses.get("items"))):
		youtube_id = search_responses.get("items", [])[try_count]['id']['videoId']
		mp3_location = downloaded_audio_folder + "/" + youtube_id + ".mp3"
		print "Next search result to consider: {0}".format(youtube_id)
		if youtube_id in rejects_list:
			print "Not bothering to consider because we already rejected it."
			try_count += 1
		elif os.path.exists(mp3_location):
			print "Already downloaded!"
			# store_result_in_database(salami_id, youtube_id)
			return youtube_id, "downloaded"
		else:
			outcome, video_length = make_download_attempt(youtube_id, expected_length)
			if outcome in ["downloaded"]:
				store_result_in_database(salami_id, youtube_id)
				time.sleep(min_sleep_interval)
			try_count += 1
	return youtube_id, outcome

def download_for_salami_ids(salami_ids, min_sleep_interval=120):
	for salami_id in salami_ids:
		try:
			print "\n\n\n\n\n" + str(salami_id) + "\n\n\n"
			search_responses = search_for_song(salami_id)
			youtube_id, outcome = download_at_least_one_video(salami_id, search_responses, min_sleep_interval=min_sleep_interval)
		except (KeyboardInterrupt):
			raise
		except:
			print "Error downloading {0}. Maybe skipping sleep interval.".format(salami_id)

# Tells you whether downloaded audio for [youtube_id] matches any audio in SALAMI, and saves the report under "match_report_[salami_id]".
def test_for_matching_audio(youtube_id, salami_id, redo=True, download_on_demand=False):
	global downloaded_audio_folder
	global fingerprint_public_filename
	filename = downloaded_audio_folder + "/" + youtube_id + ".mp3"
	if not os.path.exists(filename) and not download_on_demand:
		print "Corresponding audio not downloaded. Removing from row entirely."
		return "forget", None, None, None
	elif not os.path.exists(filename) and download_on_demand:
		print "Corresponding audio not downloaded. Attempting to download now."
		outcome, video_length = make_download_attempt(youtube_id,0)
		if outcome not in ["downloaded"]:
			print "Download attempt failed."
			return "error", None, None, None
	output_filename = "./match_report_" + str(salami_id) + ".txt"
	if (not os.path.exists(output_filename)) or (redo):
		subcall = ["python", "./audfprint/audfprint.py", "match", "--dbase", fingerprint_public_filename, filename, "-N", "10", "-x", "3", "-D", "1300", "-w", "10", "-o",output_filename, "-F", "10", "-n", "36"]
		os.system(" ".join(subcall))
	text = open(output_filename, 'r').readlines()
	if text[1].split(" ")[0] == "NOMATCH":
		return "reject", None, None, None
	else:
		line_info = text[1].split()
		matched_song_id = int(line_info[8].split("/")[-2])
		onset, hashes, total_hashes = [float(line_info[i]) for i in [10, 13, 15]]
		return matched_song_id, onset, hashes, total_hashes

def handle_candidate(salami_id, youtube_id, operation, onset=0):
	global downloaded_audio_folder
	global matchlist_csv_filename
	df = load_matchlist()
	index = df.index[df['salami_id'] == salami_id].tolist()[0]
	candidate_list = df["candidate_youtube_ids"][index].split(" ")
	rejects_list = df["rejected_youtube_ids"][index].split(" ")
	matched_id = df["youtube_id"][index]
	# temp_output_filename = "blorp.csv"
	assert youtube_id in candidate_list
	new_candidate_list = [cand for cand in candidate_list if cand != youtube_id]
	df.loc[index,"candidate_youtube_ids"] = " ".join(new_candidate_list).strip()
	if operation == "match":
		# Assert that the youtube_id we're moving is already where we expect it
		# Assert that no other youtube_id has been matched already.
		assert matched_id == ""
		# Take youtube_id, move it from candidate list to match, and write corresponding info (onset, length) about match.
		df.loc[index,"youtube_id"] = youtube_id
		df.loc[index,"time_offset"] = onset
		# We have time stretch and pitch shift columns in case we get a different fingerprinter in.
		df.loc[index,"time_stretch"] = 0
		df.loc[index,"pitch_shift"] = 0
		# Record file length
		mp3_path = downloaded_audio_folder + "/" + youtube_id + ".mp3"
		audio = mutagen.mp3.MP3(mp3_path)
		song_length = audio.info.length
		df.loc[index,"youtube_length"] = song_length
		df.to_csv(matchlist_csv_filename, header=True, index=False)
	if operation == "reject":
		# Take youtube_id, move it from candidate list to rejects.
		# Check if already in rejects list
		rejects_list = df["rejected_youtube_ids"][index].split(" ")
		if youtube_id not in rejects_list:
			rejects_list += [youtube_id]
		else:
			print "This youtube_id was already rejected before!"
		df.loc[index,"rejected_youtube_ids"] = " ".join(rejects_list).strip()
		df.to_csv(matchlist_csv_filename, header=True, index=False)
	if operation == "forget":
		df.to_csv(temp_output_filename, header=True, index=False)

def test_fingerprints_for_salami_id(salami_id):
	# Put more logic in here?
	df = load_matchlist()
	index = df.index[df['salami_id'] == salami_id].tolist()[0]
	match_found = df.loc[index,"youtube_id"] != ""
	candidates_exist = df.loc[index,"candidate_youtube_ids"] != ""
	if match_found:
		youtube_id = df.loc[index,"youtube_id"]
		print "There is already a known match: {1}. Stopping analysis of salami_id {0}.".format(salami_id, youtube_id)
		return youtube_id
	if not candidates_exist:
		print "There are no existing candidates for salami_id {0}.".format(salami_id)
		return None
	else:
		candidate_list = df["candidate_youtube_ids"][index].split(" ")
		for youtube_id in candidate_list:
			matched_song_id, onset, hashes, total_hashes = test_for_matching_audio(youtube_id, salami_id)
			if matched_song_id == salami_id:
				print "Success! Match found. Shifting {0} to match place for salami_id {1}.".format(youtube_id, salami_id)
				handle_candidate(salami_id, youtube_id, "match", onset=onset)
				return youtube_id
			elif matched_song_id == "reject":
				print "No match. Shifting {0} to rejects for salami_id {1}.".format(youtube_id, salami_id)
				handle_candidate(salami_id, youtube_id, "reject")
			elif matched_song_id == "forget":
				print "Audio does not exist. Deleting {0} from list of youtube_ids.".format(youtube_id)
				handle_candidate(salami_id, youtube_id, "forget")
			elif type(matched_song_id) is int:
				print "Match found for a different SALAMI ID... not sure what to do yet. Maybe handle manually."
				print "\nIntended SALAMI ID: {0}.\nMatched SALAMI ID: {1}.\nyoutube_id in question: {2}.\n\n".format(salami_id, matched_song_id, youtube_id)
	return None

# Download youtube files for all the genres
md = load_song_info()
salami_pop = md.index[md["class"]=="popular"]
salami_jazz = md.index[md["class"]=="jazz"]
salami_world = md.index[md["class"]=="world"]
salami_classical = md.index[md["class"]=="classical"]
all_salami = list(salami_pop) + list(salami_jazz) + list(salami_world) + list(salami_classical)
all_salami.sort()
# download_for_salami_ids(salami_pop, min_sleep_interval=180)

# Run all the fingerprint tests
for salami_id in all_salami:
	test_fingerprints_for_salami_id(salami_id)

# How many match?
df = load_matchlist()
resolved_ids = list(df.salami_id[df.youtube_id != ""])
unresolved_ids = list(df.salami_id[df.youtube_id == ""])
ia_rwc_ids = list((md.salami_id[(md["source"]=="IA") | (md.source=="RWC")]).astype(int))
len(resolved_ids)
cod_ids = list((md.salami_id[md.source=="Codaich"]).astype(int))
cod_ids.sort()
# Note: none of the IA audio is involved in this.
# Note: none of the RWC songs were found.
rwc_ids = list(md.index[md.source=='RWC'])
set.intersection(set(rwc_ids),set(resolved_ids))
# Some of the Isophonics was found, naturally
iso_ids = list(md.index[md.source=='Isophonics'])
len(set.intersection(set(cod_ids),set(resolved_ids)))
len(set.intersection(set(iso_ids),set(resolved_ids)))

# Success across class:
for clas in ["popular","jazz","classical","world"]:
	clasids = list((md.salami_id[(md["class"]==clas) & (md.source=="Codaich")]).astype(int))
	print "{0} / {1}".format(len(set.intersection(set(clasids),set(resolved_ids))), len(clasids))




# TODO:
# 1. Find the rest of the audio --- perhaps by re-running the system but using additional metadata fields, like album title.
# 2. Add convenience scripts for others, to:
# 	1. Download the audio from YouTube
# 	2. Zero-pad / crop the audio to fit the timing of the SALAMI annotations.


next_ids = list(set.difference(set(unresolved_ids),set(ia_rwc_ids)))
for id in next_ids[1:]:
	if (id >= 300):
		print id
		download_for_salami_ids([id],min_sleep_interval=60)
		test_fingerprints_for_salami_id(id)

