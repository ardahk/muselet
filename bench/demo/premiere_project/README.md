# Premiere demo footage

`make_clips.sh` creates four deterministic, 10-second, 1920×1080, 30 fps H.264
clips with AAC sine audio and a centered `SHOT n` label. Re-running it replaces
only those four named files:

```sh
bench/demo/premiere_project/make_clips.sh
```

By default, `shot1.mp4` is written to `~/Movies/Muselet Demo/`; `shot2.mp4`
through `shot4.mp4` go to `~/Desktop/Footage/`. Optional first and second
arguments override the footage and project directories. Install FFmpeg first
(`brew install ffmpeg`). The script expects the macOS Arial TTF; set
`MUSELET_DEMO_FONT` to another local TTF if needed.

The synthetic patterns make the four shots easy to distinguish and keep the
demo fully offline. For a public-facing stage video, replace them with properly
licensed B-roll from sources such as Pexels or Mixkit. Review the license and
attribution terms for each asset; do not assume every clip on a free-media site
has identical reuse rights.
