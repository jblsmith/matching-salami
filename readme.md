# Matching SALAMI audio to YouTube

The [SALAMI dataset](https://github.com/DDMAL/salami-data-public) contains Structural Annotations of a Large Amount of Music Information: the public portion contains over 2200 annotations of over 1300 unique tracks.

However, the audio files for SALAMI have never been shareable. Even for research purposes, sharing audio would be piracy. But we can let YouTube share the audio for us!

To match SALAMI audio to YouTube, we query YouTube with the titles and artists, and then confirm which results match the database using [Dan Ellis' audfprint package](https://github.com/dpwe/audfprint) with the default settings.

So far, we have found **about three-quarters** of the non-public SALAMI audio, including 619/833 tracks from [Codaich](http://jmir.sourceforge.net/index_Codaich.html), plus 42/49 tracks from [Isophonics](http://isophonics.net/datasets). (A large chunk of the database is already [free to download](https://github.com/DDMAL/SALAMI) from the Internet Archive.)

## Resources

1. A list of matches between SALAMI and YouTube videos: [salami_youtube_pairings.csv](https://github.com/jblsmith/matching-salami/blob/master/salami_youtube_pairings.csv).

2. A script to align YouTube version of audio to SALAMI version: [align_audio.py](https://github.com/jblsmith/matching-salami/blob/master/align_audio.py).
  If uses [sox](https://pypi.org/project/sox/) to zero-pad and/or trim the audio in order to fit the SALAMI original. (This should ensure a match to the SALAMI annotations to within 0.1 seconds, which seems to be the accuracy of the fingerprinter output.) Obtaining the audio files is left as an exercise for the reader.

3. A [database of fingerprints for the public SALAMI audio files](https://github.com/jblsmith/matching-salami/blob/master/salami_public_fpdb.pklz) so you can check a match for an audio file you possess.

## User notes

Please feel free to manually edit salami_youtube_pairings.csv and submit it as a pull request if you:
- know a YouTube video that matches one of the unmatched audio files, or
- one of the matched YouTube videos is no longer available.

If you manage an MIR dataset that you think would benefit from a similar matching to YouTube, check out [match_audio.py](https://github.com/jblsmith/matching-salami/blob/master/match_audio.py). It is a more general function with simple usage:

```
python3 match_audio.py 'Madonna \'Like A Prayer\'' ./Madonna_-_Like_A_Prayer.mp3 10
```

The above code will:
- create a fingerprint database that indexes one song (your local file Madonna\_-\_Like\_A\_Prayer.mp3)
- search YouTube with the query 'Madonna \'Like A Prayer\''
- check up to 10 matches before aborting
- list the candidate videos and describe the matches in ./match_info/Madonna\_-\_Like\_A\_Prayer.csv
