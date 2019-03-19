from __future__ import print_function, division
import argparse
import librosa
import numpy as np
import os
import pandas as pd
import sys
from match_salami_files import create_fingerprint_database, download_and_report, get_info_from_youtube, search_for_song, query_db_with_audio

# Usage example:
# 
# python3 match_audio.py 'Madonna \'Like A Prayer\'' ./Madonna_-_Like_A_Prayer.mp3 10
# 
# This will:
# 1. look up videos on YouTube related to 'Madonna 'Like A Prayer''
# 2. use audio fingerprinting to test whether each result matches the local file 'Madonna_-_Like_A_Prayer.mp3'
# 3. look at up to 10 results before giving up.
# 
# WARNING: you must use single quotes around the inputs, especially the filename! Otherwise, some characters (like '!') will cause all sorts of errors.

def parse_args():
	parser = argparse.ArgumentParser(description='Match a given local audio file to content on YouTube.')
	parser.add_argument('query', type=str, nargs=1, help='Complete query. E.g., \'Madonna \\\'Like A Prayer\\\'')
	parser.add_argument('input_audio_filename', type=str, nargs=1, help="Local audio file that one wants to discover a match for online.")
	parser.add_argument('max_results', type=int, nargs=1, help="Maximum number of search results to consider (default is 10).", default=10)
	args = parser.parse_args()
	return args

def search_response_to_df(search_responses):
	df = pd.DataFrame(columns=['vid','rank','duration'])
	for i,item in enumerate(search_responses['items']):
		try:
			vid = item['id']['videoId']
			rank = item['rank']
			more_info = get_info_from_youtube(vid)
			duration = more_info['duration']
			df.loc[i] = [vid,rank,duration]
		except (KeyboardInterrupt):
			raise
		except:
			print("Video connection failed.")
			df.loc[i][:2] = [vid,rank]
	final_df = df.reindex(columns = df.columns.tolist() + ['video_longer', 'duration_diff', 'matching_length', 'onset_in_youtube', 'onset_in_local', 'hashes', 'total_hashes'])
	final_df = final_df.fillna('')
	return final_df

def read_match_report(report_filename, input_audio_filename, test_audio_path):
	text = open(report_filename, 'r').readlines()
	line_info = text[1].replace(input_audio_filename,"INPUTAUDIOFILENAME")
	line_info = line_info.replace(test_audio_path,"QUERYAUDIOFILENAME")
	line_info = line_info.split()
	if line_info[0] == "NOMATCH":
		print("No match")
		return None, None, None, None, None
	elif ("INPUTAUDIOFILENAME" in line_info) and ("QUERYAUDIOFILENAME" in line_info):
		matching_length, onset_in_youtube, onset_in_local, hashes, total_hashes = [float(line_info[i]) for i in [1, 5, 11, 16, 18]]
		return matching_length, onset_in_youtube, onset_in_local, hashes, total_hashes

# def sanitize_string(input_str):
# 	output_str = re.sub("[^a-zA-Z0-9_ -]","_",basename)
# 	return output_str

def main(argv):
	# Define output dirs
	output_dir = os.getcwd() + "/"
	audio_dir = output_dir + "downloaded_audio/"
	saved_data_dir = output_dir + "match_info/"
	if not os.path.exists(audio_dir):
		os.makedirs(audio_dir)
	if not os.path.exists(saved_data_dir):
		os.makedirs(saved_data_dir)
	
	# Parse arguments, define local filenames
	args = parse_args()
	query = args.query[0]
	input_audio_filename = args.input_audio_filename[0]
	max_results = args.max_results[0]
	basename = os.path.splitext(os.path.basename(input_audio_filename))[0]
	print("\n\nSearching for \'{0}\' to match audio file \'{1}\'; searching for at most {2} results".format(query, basename,  max_results))
	# basename = sanitize_string(basename)  # If there are special characters in the basename, like !, it leads to all sorts of trouble.
	fingerprint_db_filename = saved_data_dir + basename + ".pklz"  # Fingerprint database for original audio file alone
	match_info_filename = saved_data_dir + basename + ".csv" # Will contain list of youtube files and all info related to match to input mp3
	match_report_filename = saved_data_dir + basename + ".txt" # Will contain the match report output of audfprint. This is a temporary file that will get overwritten whenever the fingerprint database for the song is queried.
	
	# Create local fingerprint database
	print("\n\nCreating fingerprint database...")
	create_fingerprint_database(fingerprint_db_filename, input_audio_filename)
	
	# Query Youtube for song; save and rank queries
	print("\n\nSearching Youtube and getting duration of each hit...")
	search_responses = search_for_song(query, maxResults=max_results)
	df = search_response_to_df(search_responses)
	input_duration = librosa.core.get_duration(filename=input_audio_filename)
	df.loc[:,'video_longer'] = (df.duration > input_duration).astype(int)
	df.loc[:,"duration_diff"] = pd.Series(np.abs(df.duration - input_duration))
	df["duration_diff"] = df["duration_diff"].apply(pd.to_numeric, downcast='float').fillna(0)
	df = df.sort_values(["video_longer","rank"],ascending=[False,True])
	df.to_csv(match_info_filename, float_format='%.2f')
	print("Saved search results to {0}.".format(match_info_filename))
	
	# Download options and check as you go;
	match_found = False
	counter = 0
	print("\n\nStarting to download and check files one by one... will halt if a match is found.")
	while (not match_found) & (counter < max_results):
		youtube_id = df.iloc[counter]['vid']
		download_status = download_and_report(youtube_id, redownload=False, sleep=0, downloaded_audio_folder=audio_dir)
		if download_status=="downloaded":
			test_audio_path = audio_dir + youtube_id + ".mp3"
			query_db_with_audio(fingerprint_db_filename, test_audio_path, match_report_filename)
			matching_length, onset_in_youtube, onset_in_local, hashes, total_hashes = read_match_report(match_report_filename, input_audio_filename, test_audio_path)
			if matching_length is None:
				df.at[counter,"matching_length"] = 0
				df.to_csv(match_info_filename, float_format='%.2f')
			else:
				# A match has been found!
				match_found = True
				df.at[counter,'matching_length'] = matching_length
				df.at[counter,'onset_in_youtube'] = onset_in_youtube
				df.at[counter,'onset_in_local'] = onset_in_local
				df.at[counter,'hashes'] = hashes
				df.at[counter,'total_hashes'] = total_hashes
				df.to_csv(match_info_filename, float_format='%.2f')
		counter += 1
	if match_found:
		print("\n\nSuccess! The YouTube video https://www.youtube.com/watch?v={0} seems to match your input.".format(youtube_id))
	else:
		print("\n\nNo match found for the search \'{0}\' and audio file \'{1}\'.".format(query,basename))

if __name__ == "__main__":
	main(sys.argv)


