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
