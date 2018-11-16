import os
import pytube
import youtube_dl
import numpy as np
import pandas as pd
import json
import dataset
from apiclient.discovery import build
import time
import mutagen.mp3

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
salami_public_metadata_path = os.path.expanduser("~/Documents/repositories/") + "salami-data-public/metadata"
salami_public_metadata_file = salami_public_metadata_path + "/metadata.csv"
fingerprint_public_filename = os.getcwd() + "/salami_public_fpdb.pklz"
# matching_dataset_filename = os.getcwd() + "/match_list.db"
matchlist_csv_filename = os.getcwd() + "/match_list.csv"
salami_xml_filename = salami_public_metadata_path + "/SALAMI_iTunes_library.xml"
codaich_info_filename = salami_public_metadata_path + "/id_index_codaich.csv"

import plistlib
salxml = plistlib.readPlist(open(salami_xml_filename,'r'))
track_keys = salxml["Tracks"].keys()
track_to_persistent_id = {tk:salxml["Tracks"][tk]["Persistent ID"] for tk in track_keys}
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
def create_fingerprint_database(fingerprint_public_filename, salami_public_audio_folder):
	subcall = ["python","./audfprint/audfprint.py","new","--dbase",fingerprint_public_filename, salami_public_audio_folder+"/*/*.mp3"]
	os.system(" ".join(subcall))	

# Load local song metadata
def load_song_info(salami_public_metadata_file):
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
	# metadata = index: artist, title
	# metadata = {int(line[0]): [line[8], line[7]] for line in metadata_lines}
	return mddf


def get_true_artist(salami_id, salxml=salxml):
	codaich_info = open(codaich_info_filename,'r').readlines()
	[line.strip().split(",") for line in codaich_info]
	cod_df = pd.read_csv(codaich_info_filename)
	index = cod_df.index[cod_df["SONG_ID"]==salami_id]
	persistent_id = cod_df.loc[index]["PERSISTENT_ID"].tolist()[0]
	tk = persistent_id_to_track[persistent_id]
	info = salxml["Tracks"][tk]
	artist = info["Artist"]
	title = info["Name"]
	if "Composer" in info.keys():
		composer = info["Composer"]
	else:
		composer = ""
	return artist, title, composer

# Search for a song using the YouTube API client
def search_for_song(salami_id, metadata):
	# artist, songtitle = metadata.loc[salami_id]['artist'], metadata.loc[salami_id]['song_title']
	# artist = " ".join(artist.split("_"))
	# if artist == "Compilations":
	# songtitle = " ".join(songtitle.split("_"))
	developer_key = json.load(open(os.path.realpath("./keys.json"),'r'))["youtube_developer_key"]
	youtube_handle = build("youtube", "v3", developerKey=developer_key)
	artist, songtitle, composer = get_true_artist(salami_id)
	query_text = " ".join(["'"+artist+"'","'"+songtitle+"'","'"+composer+"'"])
	search_responses = youtube_handle.search().list(q=query_text, part="id,snippet", maxResults=50, type="video", pageToken="").execute()
	return search_responses

# def store_result_in_database(salami_id, youtube_id, outcome, expected_length, video_length, database=matching_dataset_filename):
# 	ds = dataset.connect('sqlite:///' + matching_dataset_filename)
# 	table = ds['songs']
# 	table.insert(dict(salami_id=salami_id, youtube_id=youtube_id, outcome=outcome, expected_length=expected_length, video_length=video_length))

# Updated function to use readable, human-editable CSV instead of finnicky dataset:
def store_result_in_database(salami_id, youtube_id, database=matchlist_csv_filename):
	df = load_matchlist(database)
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
	df.to_csv(database, header=False, index=False)

# !!! WARNING !!!
# This overwrites the match list. So, only run it only once to initialize the file.
def create_matchlist_csv(matchlist_csv_filename, salami_public_metadata_file, salami_public_audio_folder):
	csv_header = ["salami_id", "salami_length", "youtube_id", "youtube_length", "time_offset", "time_stretch", "pitch_shift", "candidate_youtube_ids", "rejected_youtube_ids"]
	df = pd.DataFrame(columns=csv_header)
	md = load_song_info(salami_public_metadata_file)
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
	df.to_csv(matchlist_csv_filename, header=False, index=False)
	# Note: salami files 1126, 1227, 1327 were flacs mistakenly labelled as mp3s.
	# Also, 1599 isn't a real entry! I deleted it from the metadata file.

# To check actual mp3 lengths against metadata lengths:
# for i in md.index:
# 	diff = df.loc[i]['salami_length'] - float(md.loc[i]["song_duration"])
# 	if ~np.isnan(diff) and diff>1:
# 		print i, diff

def load_matchlist(matchlist_csv_filename):
	csv_header = ["salami_id", "salami_length", "youtube_id", "youtube_length", "time_offset", "time_stretch", "pitch_shift", "candidate_youtube_ids", "rejected_youtube_ids"]
	df = pd.read_csv(matchlist_csv_filename, header=None)
	df.columns = csv_header
	df = df.fillna("")
	return df

def make_download_attempt(youtube_id, expected_length, max_ratio_deviation=0.2, downloaded_audio_folder=downloaded_audio_folder, ydl_opts=ydl_opts, min_sleep_interval=120):
	try:
		with youtube_dl.YoutubeDL(ydl_opts) as ydl:
			x = ydl.extract_info('http://www.youtube.com/watch?v='+youtube_id, download=False)
			video_length = x['duration']
			download_title = x['title']
		# video_handle = pytube.YouTube('http://www.youtube.com/watch?v=' + youtube_id)
		# video_length = int(video_handle.length)
		# download_title = video_handle.title
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
			time.sleep(min_sleep_interval)
		# video_handle.streams.first().download(output_path = downloaded_audio_folder, filename = youtube_id)
		print "Successfully downloaded ({0})".format(youtube_id)
		return "downloaded", video_length
	except:
		print "Error downloading video ({0})".format(youtube_id)
		return "error", video_length

# Download at least one video for a song (trying from the top of the search result list)
def download_at_least_one_video(salami_id, search_responses, downloaded_audio_folder, metadata, max_count=10):
	# , matching_dataset_filename=matching_dataset_filename):
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
		if os.path.exists(downloaded_audio_folder + "/" + youtube_id + ".mp3"):
			print "Already downloaded!"
			store_result_in_database(salami_id, youtube_id)
			return youtube_id, "downloaded"
		else:
			outcome, video_length = make_download_attempt(youtube_id, expected_length)
			# store_result_in_database(salami_id, youtube_id, outcome, expected_length, video_length, database=matching_dataset_filename)
			store_result_in_database(salami_id, youtube_id)
			try_count += 1
	return youtube_id, outcome

# def fetch_downloaded_youtube_id(salami_id, matching_dataset_filename=matching_dataset_filename):
# 	ds = dataset.connect('sqlite:///' + matching_dataset_filename)
# 	table = ds['songs'].all()
# 	rows = list(table.find(salami_id=salami_id, outcome="downloaded"))
# 	if len(rows)>0:
# 		return rows[0]['youtube_id']

def test_for_matching_audio(youtube_id):
	filename = downloaded_audio_folder + "/" + youtube_id + ".mp3"
	output_filename = "./match_report_" + str(salami_id) + ".txt"
	subcall = ["python", "./audfprint/audfprint.py", "match", "--dbase",fingerprint_public_filename, filename, "-N", "10", "-x", "3", "-D", "1300", "-w", "10", "-o",output_filename, "-F", "10", "-n", "36"]
	os.system(" ".join(subcall))
	text = open(output_filename, 'r').readlines()
	if text[1].split(" ")[0] == "NOMATCH":
		return None, None, None, None
	else:
		line_info = text[1].split()
		matched_song_id = int(line_info[8].split("/")[-2])
		onset, hashes, total_hashes = [float(line_info[i]) for i in [10, 13, 15]]
		return matched_song_id, onset, hashes, total_hashes




metadata = load_song_info(salami_public_metadata_file)
salami_pop = metadata.index[metadata["class"]=="popular"]
for salami_id in salami_pop[112:]:
	try:
		print "\n\n\n\n\n" + str(salami_id) + "\n\n\n"
		search_responses = search_for_song(salami_id, metadata)
		youtube_id, outcome = download_at_least_one_video(salami_id, search_responses, downloaded_audio_folder, metadata)
		if outcome is "downloaded":
			matched_song_id, onset, hashes, total_hashes = test_for_matching_audio(youtube_id)
			if salami_id == matched_song_id:
				print "\n\nSuccess!\nDownloaded audio matches intended SALAMI song."
				print "I.e., video {0} matches salami song {1}, with {2} out of {3} matching hashes.\n\n".format(youtube_id, salami_id, hashes, total_hashes)
			else:
				print "\n\nVideo {0} does not match SALAMI file.".format(youtube_id)
				if matched_song_id is not None:
					print "...but it did match something: {0}".format(matched_song_id)
	except (KeyboardInterrupt, SystemExit):
		raise
	except:
		print "Failed for " + str(salami_id)

# TODO:
# turn "get_true_artist" into a "generate query" function that does all the logic about what fields exist.
# get fingerprint matching to communicate with CSV file
# update fingerprint DB with 5 mod 8 audio
# include fingerprint DB in repo so that others can test whether they match!