# Matching SALAMI audio to YouTube

The [SALAMI dataset](https://github.com/DDMAL/salami-data-public) contains structural annotations of a large amount of music information; over 2200 annotations of over 1300 unique tracks are now part of the public set.

However, the audio files for SALAMI have never been shareable. If we provided the audio directly, it would be considered piracy --- but what if we let YouTube share the audio for us?

The aim of this project was to identify YouTube videos containing audio that exactly matches tracks in the SALAMI dataset. After downloading audio using [youtube-dl](https://rg3.github.io/youtube-dl/), we use [Dan Ellis' audfprint package](https://github.com/dpwe/audfprint) to compare files using the default settings.

So far, we have found **about three-quarters** of the non-public SALAMI audio, including 619/833 tracks from [Codaich](http://jmir.sourceforge.net/index_Codaich.html), plus 42/49 tracks from [Isophonics](http://isophonics.net/datasets). (A large chunk of the database is already [free to download](https://github.com/DDMAL/SALAMI) from the Internet Archive.)

For every SALAMI file where we discovered a matching entry on YouTube, the pair is listed in [salami_youtube_pairings.csv](https://github.com/jblsmith/matching-salami/blob/master/salami_youtube_pairings.csv).

To download the audio from YouTube, check out [download_audio_from_youtube.py](https://github.com/jblsmith/matching-salami/blob/master/download_audio_from_youtube.py). It has functions to download the audio and then use [sox](https://pypi.org/project/sox/) to zero-pad and/or trim the audio in order to fit the SALAMI original. This means you can immediately trust the alignment between the SALAMI annotations and the audio you downloaded---at least to within a few tenths of a second, which seems to be the accuracy of the fingerprinter output.


## User note

- Do you have an audio file and want to confirm that it matches the version used by SALAMI? The audfprint [database of fingerprints for the public SALAMI audio](https://github.com/jblsmith/matching-salami/blob/master/salami_public_fpdb.pklz) is published openly as part of this repo; just use audfprint to query it.
- Do you know a YouTube video that matches one of the audio files? You can manually edit salami_youtube_pairings.csv and submit it as a pull request.