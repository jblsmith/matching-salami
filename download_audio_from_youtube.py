import os
import youtube_dl
import pandas as pd
import time
import sox

matchlist_csv_filename = os.getcwd() + "/salami_youtube_pairings.csv"
downloaded_audio_folder = os.getcwd() + "/downloaded_audio"
transformed_audio_folder = os.getcwd() + "/transformed_audio"
match_data = pd.read_csv(matchlist_csv_filename, header=0)
match_data = match_data.fillna("")

# Specify download location

downloaded_audio_folder = os.getcwd() + "/downloaded_audio"
if not os.path.exists(downloaded_audio_folder):
	os.makedirs(downloaded_audio_folder)

if not os.path.exists(transformed_audio_folder):
	os.makedirs(transformed_audio_folder)

# Specify post-processing
# Current options look for best quality audio and convert to 192kbps mp3 format.
ydl_opts = {
	'outtmpl': os.path.join(downloaded_audio_folder, u'%(id)s.%(ext)s'),
	'format': 'bestaudio/best',
	'postprocessors': [{
		'key': 'FFmpegExtractAudio',
		'preferredcodec': 'mp3',
		'preferredquality': '192',
	}],
}

def download_youtube_id(youtube_id):
	global ydl_opts
	try:
		with youtube_dl.YoutubeDL(ydl_opts) as ydl:
			x = ydl.download(['http://www.youtube.com/watch?v='+youtube_id])
		print "Successfully downloaded ({0})".format(youtube_id)
	except:
		print "Error downloading ({0})".format(youtube_id)

def reshape_audio(salami_id):
	global match_data
	row = {colname: match_data[colname][match_data.salami_id==salami_id].values[0]  for colname in match_data.columns}
	input_filename = downloaded_audio_folder + "/" + str(row["youtube_id"]) + ".mp3"
	output_filename = transformed_audio_folder + "/" + str(row["salami_id"]) + ".mp3"
	start_time_in_yt = row["onset_in_youtube"] - row["onset_in_salami"]
	# = - row["time_offset"]
	end_time_in_yt = start_time_in_yt + row["salami_length"]
	tfm = sox.Transformer()
	if end_time_in_yt > row["youtube_length"]:
		tfm.pad(end_duration=end_time_in_yt - row["youtube_length"])
	if start_time_in_yt < 0:
		tfm.pad(start_duration=-start_time_in_yt)
		start_time_in_yt = 0
	# Select portion of youtube file to match salami
	tfm.trim(start_time_in_yt, start_time_in_yt+row["salami_length"])
	tfm.build(input_filename, output_filename)

