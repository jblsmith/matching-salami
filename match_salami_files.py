import os
import youtube_dl
import numpy as np
import pandas as pd
import json
import dataset
from apiclient.discovery import build
import time
import plistlib
import librosa
import sox

# Audio directories
salami_public_audio_folder = os.path.expanduser("~/Documents/data/SALAMI/audio")
downloaded_audio_folder = os.getcwd() + "/downloaded_audio"
if not os.path.exists(downloaded_audio_folder):
	os.makedirs(downloaded_audio_folder)

# Metadata path and files
salami_public_metadata_path = os.path.expanduser("~/Documents/repositories/") + "salami-data-public/metadata"
salami_public_metadata_file = salami_public_metadata_path + "/metadata.csv"
salami_xml_filename = salami_public_metadata_path + "/SALAMI_iTunes_library.xml"
codaich_info_filename = salami_public_metadata_path + "/id_index_codaich.csv"

# Fingerprint databases
fingerprint_public_filename = os.getcwd() + "/salami_public_fpdb.pklz"
fingerprint_youtube_filename = os.getcwd() + "/youtube_public_fpdb.pklz"

# Match list info
salami_matchlist_csv_filename = os.getcwd() + "/match_list.csv"
salami_xml = plistlib.readPlist(open(salami_xml_filename,'r'))
track_keys = salami_xml["Tracks"].keys()
track_to_persistent_id = {tk:salami_xml["Tracks"][tk]["Persistent ID"] for tk in track_keys}
persistent_id_to_track = {track_to_persistent_id[tk]:tk for tk in track_keys}

# Youtube download and post-processing options
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
def create_fingerprint_database(database_filename, audio_folder_wildcard):
	subcall = ["python","./audfprint/audfprint.py","new","--dbase", database_filename, audio_folder_wildcard]
	os.system(" ".join(subcall))

def add_to_fingerprint_database(database_filename, audio_file):
	subcall = ["python","./audfprint/audfprint.py","add","--dbase", database_filename, audio_file]
	os.system(" ".join(subcall))	

# Load local song metadata
def load_song_info():
	global salami_public_metadata_file
	with open(salami_public_metadata_file, 'r') as f:
		x = f.readlines()
	metadata_lines = [line.strip().split(",") for line in x]
	mddf = pd.DataFrame(metadata_lines[1:], columns=['salami_id'] + [x.lower() for x in metadata_lines[0][1:]])
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
	artist_info = []
	for field in ["Artist","Name","Composer","Album"]:
		if field in info.keys():
			artist_info += [info[field]]
		else:
			artist_info += [""]
	return artist_info

# Search for a song using the YouTube API client
def search_for_song(salami_id):
	developer_key = json.load(open(os.path.realpath("./keys.json"),'r'))["youtube_developer_key"]
	youtube_handle = build("youtube", "v3", developerKey=developer_key)
	song_info = get_true_artist(salami_id)
	query_text = " ".join(["'"+item+"'" for item in song_info if item != ""])
	search_responses = youtube_handle.search().list(q=query_text, part="id,snippet", maxResults=50, type="video", pageToken="").execute()
	for i in range(len(search_responses['items'])):
		search_responses['items'][i]['rank'] = i
	return search_responses

def multiple_searches_for_song(salami_id):
	developer_key = json.load(open(os.path.realpath("./keys.json"),'r'))["youtube_developer_key"]
	youtube_handle = build("youtube", "v3", developerKey=developer_key)
	song_info = get_true_artist(salami_id)
	query_combos = [song_info[:2], song_info[1:3], song_info[:3], [song_info[1],song_info[3]], song_info]
	query_texts = [" ".join(["'"+item+"'" for item in info_list if item != ""]) for info_list in query_combos]
	output_list = []
	for query_text in query_texts:
		search_responses = youtube_handle.search().list(q=query_text, part="id,snippet", maxResults=20, type="video", pageToken="").execute()
		for i in range(len(search_responses['items'])):
			search_responses['items'][i]['rank'] = i
		output_list += search_responses['items']
	return output_list

def define_candidates_from_searches(salami_id, search_response_list, overwrite=False):
	df = load_matchlist()
	output_filename = "./search_lists/" + str(salami_id) + ".csv"
	if os.path.exists(output_filename) and (not overwrite):
		print "Cannot process candidates because saved list already exists."
		return
	expected_length = float(df["salami_length"][df.salami_id==salami_id].values)
	candidates = pd.DataFrame(columns=["top_rank", "n_hits", "title", "duration", "deviation", "salami_coverage", "decision", "in_top_5", "in_top_10", "same_plus_5", "same_less_5", "overall_score", "matching_length", "onset_in_youtube", "onset_in_salami", "hashes", "total_hashes"])
	candidates.index.name = 'youtube_id'
	try:
		for video in search_response_list:
			youtube_id = video["id"]["videoId"]
			video_info = None
			if youtube_id not in candidates.index:
				candidates.loc[youtube_id,:7] = [np.inf, 0, "", 0, np.inf, 0, ""]
				video_info = get_info_from_youtube(youtube_id)
			if video_info:
				candidates.loc[youtube_id,"duration"] = video_info["duration"]
				candidates.loc[youtube_id,"title"] = video_info["title"]
				candidates.loc[youtube_id,"deviation"] = expected_length - video_info["duration"]
			rank = video["rank"]
			candidates.loc[youtube_id, "top_rank"] = min(candidates.loc[youtube_id, "top_rank"], rank)
			candidates.loc[youtube_id, "n_hits"] += 1
		candidates.to_csv(output_filename, header=True, index=True, encoding="utf-8")
	except:
		print "Outputting list to temporary CSV file because something went wrong."
		candidates.to_csv(output_filename, header=True, index=True, encoding="utf-8")

def prioritize_candidates(salami_id):
	candidates = load_candidate_list(salami_id)
	# Prioritization:
	# 	- multiply-ranked first
	# 	- anything in top 10, by rank, at most 5 seconds longer than SALAMI
	#	- anything in top 10, by rank, at most 5 seconds shorter than SALAMI
	# 	- rest of the top 10, by rank, disregarding length
	# 	- rest of everything, in order of length deviation
	candidates["in_top_5"] = candidates.top_rank<5
	candidates["in_top_10"] = candidates.top_rank<10
	candidates["same_plus_5"] = (candidates.deviation<=0) & (candidates.deviation>=-5)
	candidates["same_less_5"] = (candidates.deviation>=0) & (candidates.deviation<=5)
	candidates["overall_score"] = candidates.in_top_5 + candidates.in_top_10 + 2*candidates.same_plus_5 + candidates.same_less_5
	candidates = candidates.sort_values(by = ['overall_score', 'n_hits', 'top_rank'], ascending=[False, False, True])
	save_candidates(salami_id, candidates)
	# Check results sorted as expected:
	# cands[['n_hits','in_top_10','same_plus_5','same_less_5','top_rank']]

def load_candidate_list(salami_id):
	filename = "./search_lists/" + str(salami_id) + ".csv"
	assert os.path.exists(filename)
	candidates = pd.read_csv(filename, header=0)
	candidates = candidates.fillna("")
	return candidates

def save_candidates(salami_id, candidates):
	filename = "./search_lists/" + str(salami_id) + ".csv"
	candidates.to_csv(filename, header=True, index=False, encoding="utf-8")

def process_candidates(salami_id, max_tries_per_video=10):
	candidates = load_candidate_list(salami_id)
	df = load_matchlist()
	for ind in candidates.index[:max_tries_per_video]:
		youtube_id = candidates.loc[ind]['youtube_id']
		decision = candidates.loc[ind]['decision']
		decisions = candidates['decision'].values.tolist()
		if ("match" not in decisions) and (np.sum(np.array(decisions)=="potential") < 3):
			if decision == "":
				download_status = download_and_report(youtube_id)
				if download_status == "downloaded":
					match_status = test_for_matching_audio(youtube_id, salami_id, redo=True)
					candidates.decision.loc[ind] = match_status
					if match_status == "potential":
						matched_song_id, matching_length, onset_in_youtube, onset_in_salami, hashes, total_hashes = read_match_report(salami_id)
						if matched_song_id == salami_id:
							candidates.matching_length.loc[ind] = matching_length
							candidates.onset_in_youtube.loc[ind] = onset_in_youtube
							candidates.onset_in_salami.loc[ind] = onset_in_salami
							candidates.hashes.loc[ind] = hashes
							candidates.total_hashes.loc[ind] = total_hashes
							salami_length = df.salami_length[df.salami_id==salami_id].values
							frac_match = candidates.matching_length.loc[ind] / salami_length
							if frac_match > 0.95:
								candidates.decision.loc[ind] = "match"
						else:
							print "Matched... but with a different SALAMI song!"
							candidates.decision.loc[ind] = "matched_"+str(matched_song_id)
					save_candidates(salami_id, candidates)

# Updated function to use readable, human-editable CSV instead of finnicky dataset:
def store_result_in_database(salami_id, youtube_id):
	global salami_matchlist_csv_filename
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
	df.to_csv(salami_matchlist_csv_filename, header=True, index=False)


# !!! WARNING !!!
# This overwrites the match list. So, only run it only once to initialize the file.
def create_matchlist_csv():
	global salami_matchlist_csv_filename
	global salami_public_audio_folder
	csv_header = ["salami_id", "salami_length", "youtube_id", "youtube_length", "matching_hashes", "total_hashes", "time_offset", "time_stretch", "pitch_shift", "candidate_youtube_ids", "rejected_youtube_ids"]
	df = pd.DataFrame(columns=csv_header)
	md = load_song_info()
	md.sort_index(inplace=True)
	# Populate with SALAMI IDs
	df.salami_id = md.salami_id
	# Populate with mp3 file lengths, taken from file since metadata doesn't have them all:
	print "Getting SALAMI song lengths..."
	for salid in md.index:
		mp3_path = salami_public_audio_folder + "/" + str(salid) + "/audio.mp3"
		song_length = librosa.core.get_duration(filename=mp3_path)
		df["salami_length"][salid] = song_length
	df.to_csv(salami_matchlist_csv_filename, header=True, index=False)
	# Note: salami files 1126, 1227, 1327 were flacs mistakenly labelled as mp3s.
	# Also, 1599 isn't a real entry! I deleted it from the metadata file.

# TODO: Redo create_matchlist_csv to have new format (no pitch shift or time stretch, yes new columns)
# def create_matchlists_csv():
# 	# Create
# 	global youtube_matchlist_csv_filename
# 	csv_header = ["youtube_id", "youtube_length", "salami_id", "salami_length", "matching_hashes", "total_hashes", "time_offset", "status"]
# 	df = pd.DataFrame(columns=csv_header)
# 	df.to_csv(salami_matchlist_csv_filename, header=True, index=False)
# 	global salami_matchlist_csv_filename
# 	global salami_public_audio_folder
# 	csv_header = ["salami_id", "salami_length", "youtube_id", "youtube_length", "matching_hashes", "total_hashes", "time_offset", "status", "candidate_youtube_ids"]
# 	df = pd.DataFrame(columns=csv_header)
# 	for salid in md.index:
# 		mp3_path = salami_public_audio_folder + "/" + str(salid) + "/audio.mp3"
# 		song_length = librosa.core.get_duration(filename=mp3_path)
# 		df["salami_length"][salid] = song_length
# 	df.to_csv(salami_matchlist_csv_filename, header=True, index=False)


def load_matchlist():
	global salami_matchlist_csv_filename
	df = pd.read_csv(salami_matchlist_csv_filename, header=0)
	df = df.fillna("")
	return df

def get_info_from_youtube(youtube_id):
	global ydl_opts
	try:
		with youtube_dl.YoutubeDL(ydl_opts) as ydl:
			x = ydl.extract_info('http://www.youtube.com/watch?v='+youtube_id, download=False)
			# video_length = x['duration']
			return x
	except (KeyboardInterrupt):
		raise
	except:
		# print "Video connection failed."
		return None

def download_and_report(youtube_id, redownload=False):
	global ydl_opts
	if (not os.path.exists(downloaded_audio_folder + "/" + youtube_id + ".mp3")) or (redownload):
		try:
			with youtube_dl.YoutubeDL(ydl_opts) as ydl:
				x = ydl.download(['http://www.youtube.com/watch?v='+youtube_id])
			print "Successfully downloaded ({0})".format(youtube_id)
			return "downloaded"
		except (KeyboardInterrupt):
			raise
		except:
			print "Error downloading video ({0})".format(youtube_id)
			return "error"
	else:
		return "downloaded"

def make_download_attempt(youtube_id, expected_length=None, max_abs_deviation=2, long_ok=False):
	if (expected_length > 60*9) and (not long_ok):
		print "Setting long_ok = True, because expected length is greater than 9 minutes."
		long_ok = True
	# If expected_length = None, don't bother checking length of video.
	global ydl_opts
	video_info = get_info_from_youtube(youtube_id)
	if video_info:
		video_length = video_info
	else:
		video_length = 0
	# max_ratio_deviation=0.05, 
	# if expected_length == 0:
	# 	ratio_deviation = 0
	# else:
	# 	ratio_deviation = np.abs(expected_length-video_length)*1.0/expected_length
	abs_deviation = np.abs(expected_length-video_length)
	if (abs_deviation > max_abs_deviation) and (expected_length is not None):
		print "Stopping -- unexpected length ({0})".format(youtube_id)
		return "stopped", video_length
	if (video_length > 60*10) and (expected_length<60*10-10) and (not long_ok):
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
	match_item = df["youtube_id"][index]
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
			if youtube_id not in candidate_list + rejects_list + [match_item]:
				store_result_in_database(salami_id, youtube_id)
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
		return "forget"
	elif not os.path.exists(filename) and download_on_demand:
		print "Corresponding audio not downloaded. Attempting to download now."
		outcome, video_length = make_download_attempt(youtube_id,0)
		if outcome not in ["downloaded"]:
			print "Download attempt failed."
			return "error"
	output_filename = "./match_reports/match_report_" + str(salami_id) + ".txt"
	if (not os.path.exists(output_filename)) or (redo):
		subcall = ["python", "./audfprint/audfprint.py", "match", "--dbase", fingerprint_public_filename, filename, "-N", "10", "-x", "1", "-D", "1300", "-w", "10", "--find-time-range", "--time-quantile", "0", "-o", output_filename]
		# Since default options were used to create database, I'm removing these: "-F", "10", "-n", "36",
		os.system(" ".join(subcall))
	text = open(output_filename, 'r').readlines()
	if text[1].split(" ")[0] == "NOMATCH":
		return "reject"
	else:
		return "potential"

def read_match_report(salami_id):
	output_filename = "./match_reports/match_report_" + str(salami_id) + ".txt"
	if not os.path.exists(output_filename):
		print "Match report not yet computed"
	text = open(output_filename, 'r').readlines()
	if text[1].split(" ")[0] == "NOMATCH":
		print "No match"
		return None, None, None, None, None, None
	else:
		line_info = text[1].split()
		matched_song_id = int(line_info[14].split("/")[-2])
		matching_length, onset_in_youtube, onset_in_salami, hashes, total_hashes = [float(line_info[i]) for i in [1, 5, 11, 16, 18]]
		return matched_song_id, matching_length, onset_in_youtube, onset_in_salami, hashes, total_hashes

def handle_candidate(salami_id, youtube_id, operation, onset=0, hashes=0, total_hashes=0):
	global downloaded_audio_folder
	global salami_matchlist_csv_filename
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
		matched_song_id, matching_length, onset_in_youtube, onset_in_salami, hashes, total_hashes = read_match_report(salami_id)
		# Take youtube_id, move it from candidate list to match, and write corresponding info (onset, length) about match.
		df.loc[index,"youtube_id"] = youtube_id
		df.loc[index,"matching_length"] = matching_length
		df.loc[index,"onset_in_youtube"] = onset_in_youtube
		df.loc[index,"onset_in_salami"] = onset_in_salami
		df.loc[index,"matching_hashes"] = int(hashes)
		df.loc[index,"total_hashes"] = int(total_hashes)
		# Get youtube file length
		mp3_path = downloaded_audio_folder + "/" + youtube_id + ".mp3"
		song_length = librosa.core.get_duration(filename=mp3_path)
		df.loc[index,"youtube_length"] = song_length
		df.to_csv(salami_matchlist_csv_filename, header=True, index=False)
	if operation == "reject":
		# Take youtube_id, move it from candidate list to rejects.
		# Check if already in rejects list
		rejects_list = df["rejected_youtube_ids"][index].split(" ")
		if youtube_id not in rejects_list:
			rejects_list += [youtube_id]
		else:
			print "This youtube_id was already rejected before!"
		df.loc[index,"rejected_youtube_ids"] = " ".join(rejects_list).strip()
		df.to_csv(salami_matchlist_csv_filename, header=True, index=False)
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
	else:
		candidate_list = df["candidate_youtube_ids"][index].split(" ")
		for youtube_id in candidate_list:
			match_result = test_for_matching_audio(youtube_id, salami_id, download_on_demand=True)
			matched_song_id, matching_length, onset_in_youtube, onset_in_salami, hashes, total_hashes = read_match_report(salami_id)
			if match_result == "potential":
				if matched_song_id == salami_id:
					print "Success! Match found. Shifting {0} to match place for salami_id {1}.".format(youtube_id, salami_id)
					handle_candidate(salami_id, youtube_id, "match")
				else:
					# elif type(matched_song_id) is int:
					print "Match found for a different SALAMI ID... not sure what to do yet. Maybe handle manually."
					print "\nIntended SALAMI ID: {0}.\nMatched SALAMI ID: {1}.\nyoutube_id in question: {2}.\n\n".format(salami_id, matched_song_id, youtube_id)
			elif match_result == "reject":
				print "No match. Shifting {0} to rejects for salami_id {1}.".format(youtube_id, salami_id)
				handle_candidate(salami_id, youtube_id, "reject")
			elif match_result == "forget":
				print "Audio does not exist. Deleting {0} from list of youtube_ids.".format(youtube_id)
				handle_candidate(salami_id, youtube_id, "forget")
