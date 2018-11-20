# Matching SALAMI audio to YouTube

The [SALAMI dataset](https://github.com/DDMAL/salami-data-public) contains structural annotations of a large amount of music information; over 2200 annotations of over 1300 unique tracks are now part of the public set.

However, the audio files for SALAMI have never been shareable. If we provided the audio directly, it would be considered piracy --- but what if we let YouTube share the audio for us?

The aim of this project was to identify YouTube videos containing audio that exactly matches tracks in the SALAMI dataset. After downloading audio using [youtube-dl](https://rg3.github.io/youtube-dl/), we use [Dan Ellis' audfprint package](https://github.com/dpwe/audfprint) to compare files using the default settings.

We managed to find more than half of the non-public SALAMI audio, including 452/833 tracks from [Codaich](http://jmir.sourceforge.net/index_Codaich.html). (A large chunk of the database is already [free to download](https://github.com/DDMAL/SALAMI) from the Internet Archive.)

The matching audio files for each SALAMI entry are listed in match_list.csv.

## Coming soon

- Convenience function to download the matched audio from YouTube and to use ffmpeg to crop and zero-pad as required to match the annotations.
- More matched IDs after more thorough searching.

## User note

- Do you have an audio file and want to confirm that it matches the version used by SALAMI? The audfprint [database of fingerprints for the public SALAMI audio](https://github.com/jblsmith/matching-salami/blob/master/salami_public_fpdb.pklz) is published openly as part of this repo; just use audfprint to query it.
- Do you know a YouTube video that matches one of the audio files? You can manually edit match_list.csv and submit it as a pull request.