from match_salami_files import *
df = load_matchlist()
for salami_id in df.salami_id[12:20]:
	# for salami_id in [2,3,4,5,6,7,8]:
	output_list = multiple_searches_for_song(salami_id)
	define_candidates_from_searches(salami_id, output_list)
	prioritize_candidates(salami_id)
	process_candidates(salami_id)


# It still misses Q5u1ZbIaNps for 14! So I still need to add a manual suggestion method.
manually_suggest_and_process(salami_id,youtube_id)


salami_id = 3
youtube_id="Y6zAT15vaFk"
test_for_matching_audio(youtube_id, salami_id, redo=True, download_on_demand=False)

test_for_matching_audio("mbJ9D_p3p24", 4)



def grade_match(salami_id):
	matched_song_id, matching_length, raw_hashes, onset, hashes, total_hashes = test_for_matching_audio(youtube_id, salami_id, redo=False)
	index = df.index[df['salami_id'] == salami_id].tolist()[0]
	salami_length = df["salami_length"][index]
	

df = load_matchlist()
df.columns = df.columns.tolist()[:7] + ['matching_length','raw_hashes'] + df.columns.tolist()[9:]
for salami_id in df.salami_id:
	index = df.index[df['salami_id'] == salami_id].tolist()[0]
	youtube_id = df.loc[index,"youtube_id"]
	if youtube_id != "":
		matched_song_id, matching_length, raw_hashes, onset, hashes, total_hashes = test_for_matching_audio(youtube_id, salami_id, redo=False)
		df.loc[index,"matching_length"] = matching_length
		df.loc[index,"raw_hashes"] = raw_hashes

df.to_csv(salami_matchlist_csv_filename, header=True, index=False)





# Download youtube files for all the genres
md = load_song_info()
salami_pop = md.index[md["class"]=="popular"]
salami_jazz = md.index[md["class"]=="jazz"]
salami_world = md.index[md["class"]=="world"]
salami_classical = md.index[md["class"]=="classical"]
all_salami = list(salami_pop) + list(salami_jazz) + list(salami_world) + list(salami_classical)
all_salami.sort()
# download_for_salami_ids(salami_pop, min_sleep_interval=10)

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
# Find the rest of the audio
import matplotlib.pyplot as plt
plt.ion()

next_ids = list(set.difference(set(unresolved_ids),set(ia_rwc_ids)))
for id in next_ids[1:]:
	if (id >= 300):
		print id
		download_for_salami_ids([id],min_sleep_interval=60)
		test_fingerprints_for_salami_id(id)


"RW9A8oJKx7s", 4   --> previous matching song had wrong length!
StgAsIxCP6A, 1620


# TODO:
# Figure out a good threshold to judge match quality --- and maybe fingerprint multiple chunks of each youtube file instead of its entirety.

tmp_df = df[df.youtube_id != ""]
qual_percent = (tmp_df.matching_hashes / tmp_df.total_hashes).values
qual_abs = (tmp_df.matching_hashes).values
qual_frac = (tmp_df.matching_length / tmp_df.salami_length).values
np.where(qual_frac>2)
np.where(qual_frac>1.1)
tmp_df.iloc[np.where(qual_frac>2)]


plt.scatter(qual_percent,qual_abs)
len_diff = tmp_df.salami_length - tmp_df.youtube_length
you_short_by = np.abs(len_diff) * (len_diff > 0)
sal_short_by = np.abs(len_diff) * (len_diff < 0)
plt.scatter(qual_percent,you_short_by)

tmp_df[len_diff > 5]

# "Over You" by Bif Naked:
# 14,248.26775,Q5u1ZbIaNps,255.8955102040816,830.0,19732.0,-0.7,0.0,0.0,,BdpJh_zc6k8
# Seems like a poor match (830/19732 hashes) but is actually spot-on --- the youtube audio is filtered though!
# On the other hand:
# "I Close My Eyes" by Shivaree:
# 4,236.09466666666665,mbJ9D_p3p24,217.056,825.0,4326.0,0.5,0.0,0.0,,
# In an absolute sense, is just as good (825 hashes) and is relatively better (825/4326), but in fact this version is a radio edit that is missing 20 seconds, which, for the purposes of SALAMI, is a much poorer match.
# So perhaps the final check I want to run is an alignment cost step... Computationally expensive (it will require loading all the audio!)... so perhaps only warranted for cases flagged as borderline.

# Searching for all info (artist, composer, album, title) leads to poor search results.
# I should write a script that iteratively tests candidates until it finds a match. It could do multiple searches (all possible combinations of search terms but must include title), and then consider its options among all of them, sorting by length similarity.
# Then it would fingerprint them, and once it found a match, stop downloading new ones.
