import os
import pytube
import numpy as np
import json
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

# Create the fingerprint database
# 		!! WARNING !!
# 		This command is designed to be run ONCE.
#		Do not overwrite the database unnecessarily.
def createFingerprintDB(fingerprint_public_filename, salami_public_audio_folder):
	subcall = ["python","./audfprint/audfprint.py","new","--dbase",fingerprint_public_filename, salami_public_audio_folder+"/*/*.mp3"]
	os.system(" ".join(subcall))

# Load local song metadata
def load_song_info(salami_public_metadata_path):
	with open(salami_public_metadata_file, 'r') as f:
		x = f.readlines()
	metadata_lines = [line.split(",") for line in x]
	# metadata = index: artist, title
	metadata = {int(line[0]): [line[8], line[7]] for line in metadata_lines}
	return metadata

# Search for a song using the YouTube API client
def search_for_song(salami_id, metadata):
	artist, songtitle = metadata[salami_id]
	artist = " ".join(artist.split("_"))
	songtitle = " ".join(songtitle.split("_"))
	developer_key = json.load(open(os.path.realpath("./keys.json"),'r'))["youtube_developer_key"]
	youtube_handle = build("youtube", "v3", developerKey=developer_key)
	query_text = " ".join(["'"+artist+"'","'"+songtitle+"'"])
	search_responses = youtube_handle.search().list(q=query_text, part="id,snippet", maxResults=50, type="video", pageToken="").execute()
	return search_responses

# Download at least one video for a song (trying from the top of the search result list)
def download_at_least_one_video(search_responses, downloaded_audio_folder, max_count=10):
	downloaded = False
	try_count = 0
	while (not downloaded) or (try_count<max_count) or (try_count<len(search_responses.get("items"))):
		youtube_id = search_responses.get("items", [])[try_count]['id']['videoId']
		try:
			video_handle = pytube.YouTube('http://youtube.com/watch?v=' + youtube_id)
			download_title = video_handle.title
			video_handle.streams.first().download(output_path = downloaded_audio_folder, filename = youtube_id)
			downloaded = True
			return try_count, download_title
		except:
			print "Error downloading video on attempt " + str(try_count)
		try_count += 1


metadata = load_song_info(salami_public_metadata_path)
for salami_id in metadata.keys()[:5]:
	search_responses = search_for_song(salami_id, metadata)
	try_count, download_title = download_at_least_one_video(search_responses, downloaded_audio_folder)
	print try_count, download_title




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
