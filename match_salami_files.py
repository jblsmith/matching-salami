import os
import pytube
import numpy as np
import pandas as pd
import json
import dataset
from apiclient.discovery import build

# Handy functions

def ensure_dir(path):
	if not os.path.exists(path):
		os.makedirs(path)

def printjson(rawjson):
	print json.dumps(rawjson,sort_keys=True,indent=4)

# Point to folders and metadata files:
downloaded_audio_folder = os.getcwd() + "/downloaded_audio"
ensure_dir(downloaded_audio_folder)
salami_public_audio_folder = os.path.realpath("../../data/SALAMI/audio")
salami_public_metadata_path = os.path.realpath("../../data/SALAMI/SALAMI_data_v1.2")
salami_public_metadata_file = salami_public_metadata_path + "/metadata.csv"
fingerprint_public_filename = os.getcwd() + "/salami_public_fpdb.pklz"
matching_dataset_filename = os.getcwd() + "/match_list.db"

# Create the fingerprint database
# 		!! WARNING !!
# 		This command is designed to be run ONCE.
#		Do not overwrite the database unnecessarily.
def create_fingerprint_database(fingerprint_public_filename, salami_public_audio_folder):
	subcall = ["python","./audfprint/audfprint.py","new","--dbase",fingerprint_public_filename, salami_public_audio_folder+"/*/*.mp3"]
	os.system(" ".join(subcall))	

# Load local song metadata
def load_song_info(salami_public_metadata_path):
	with open(salami_public_metadata_file, 'r') as f:
		x = f.readlines()
	metadata_lines = [line.strip().split(",") for line in x]
	mddf = pd.DataFrame(metadata_lines)
	mddf.columns = ['salami_id', 'source', 'annotator1', 'annotator2', 'path',
					'length', 'blank', 'title', 'artist', 'audio_format',
					'ann1_time', 'ann2_time', 'ann1_filename', 'ann2_filename', 
					'class', 'genre', 'ann1_date', 'ann2_date',
					'trash1', 'trash2', 'xeqs1', 'xeqs2']
	mddf.index = mddf.salami_id.astype(int)
	# metadata = index: artist, title
	# metadata = {int(line[0]): [line[8], line[7]] for line in metadata_lines}
	return mddf

# Search for a song using the YouTube API client
def search_for_song(salami_id, metadata):
	artist, songtitle = metadata.loc[salami_id]['artist'], metadata.loc[salami_id]['title']
	artist = " ".join(artist.split("_"))
	songtitle = " ".join(songtitle.split("_"))
	developer_key = json.load(open(os.path.realpath("./keys.json"),'r'))["youtube_developer_key"]
	youtube_handle = build("youtube", "v3", developerKey=developer_key)
	query_text = " ".join(["'"+artist+"'","'"+songtitle+"'"])
	search_responses = youtube_handle.search().list(q=query_text, part="id,snippet", maxResults=50, type="video", pageToken="").execute()
	return search_responses

def store_result_in_database(salami_id, youtube_id, outcome, expected_length, video_length, database=matching_dataset_filename):
	ds = dataset.connect('sqlite:///' + matching_dataset_filename)
	table = ds['songs']
	table.insert(dict(salami_id=salami_id, youtube_id=youtube_id, outcome=outcome, expected_length=expected_length, video_length=video_length))

def make_download_attempt(youtube_id, expected_length, max_ratio_deviation=0.2, downloaded_audio_folder=downloaded_audio_folder):
	try:
		video_handle = pytube.YouTube('http://www.youtube.com/watch?v=' + youtube_id)
	except:
		print "Video connection failed."
		return "error", 0
	video_length = int(video_handle.length)
	download_title = video_handle.title
	if expected_length == 0:
		ratio_deviation = 0
	else:
		ratio_deviation = np.abs(expected_length-video_length)/expected_length
	if ratio_deviation > max_ratio_deviation:
		print "Stopping -- unexpected length ({0})".format(youtube_id)
		return "stopped", video_length
	if video_length > 60*10:
		print "Stopping -- longer than 10 minutes without reason ({0})".format(youtube_id)
		return "stopped", video_length
	try:
		video_handle.streams.first().download(output_path = downloaded_audio_folder, filename = youtube_id)
		print "Successfully downloaded ({0})".format(youtube_id)
		return "downloaded", video_length
	except:
		print "Error downloading video ({0})".format(youtube_id)
		return "error", video_length

# Download at least one video for a song (trying from the top of the search result list)
def download_at_least_one_video(salami_id, database_path, search_responses, downloaded_audio_folder, metadata, max_count=10, matching_dataset_filename=matching_dataset_filename):
	outcome = "empty"
	try_count = 0
	expected_length = metadata.loc[salami_id]["length"]
	try:
		expected_length = int(expected_length)
	except:
		expected_length = 0
	while (outcome != "downloaded") and (try_count<max_count) and (try_count<len(search_responses.get("items"))):
		youtube_id = search_responses.get("items", [])[try_count]['id']['videoId']
		outcome, video_length = make_download_attempt(youtube_id, expected_length)
		store_result_in_database(salami_id, youtube_id, outcome, expected_length, video_length, database=matching_dataset_filename)
		try_count += 1




metadata = load_song_info(salami_public_metadata_path)
for salami_id in metadata.index[:3]:
	search_responses = search_for_song(salami_id, metadata)
	download_at_least_one_video(salami_id, matching_dataset_filename, search_responses, downloaded_audio_folder, metadata)


# Query database, interpret result, make a decision and decide offset.
metadata = load_song_info(salami_public_metadata_path)
for salami_id in metadata.keys()[:3]:
	output_filename = "./match_report_" + str(salami_id) + ".txt"
	subcall = ["python", "./audfprint/audfprint.py", "match", "--dbase",fingerprint_public_filename, "./downloaded_audio/pTlllvUYVaI.mp4", "-N", "10", "-x", "3", "-D", "1300", "-w", "10", "-o",output_filename, "-F", "10", "-n", "36"]
	os.system(" ".join(subcall))




# TODO:
# 1. set up youtube api with key
# 2. load codaich metadata (or maybe all salami sources)
# 3. set up Dan Ellis fingerprinter and create DB with all SALAMI files (public and private)
# 4. for each file:
# 	a. look up artist / song / album on youtube
# 	b. Look for results with the same length (+/- 5 seconds)
# 	c. download top result, with the first official result taking priority
# 	d. make several queries to fingerprint DB
# 	5. if a song is a match, find offset and preserve youtube id and offset along with salami DB
# 5. when finished, or perhaps iteratively, publish list of youtube IDs to download SALAMI
