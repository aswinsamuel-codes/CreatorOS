# Video → post (YouTube, LinkedIn and more)

Give CreatorOS a finished video, or a folder of videos, and it writes everything needed to
publish it, then uploads after your approval.

## What the agent does with each video

```
video file
  → ffprobe: length, size, vertical/horizontal
  → 6 frames sampled evenly through the video
  → transcript with timestamps (optional, local and free with faster-whisper)
  → writer model (vision) writes:
       YouTube title · description · tags · chapters · best thumbnail frame
       LinkedIn caption + hashtags
  → Approval mode: thumbnail + texts on Telegram and in Posts (edit or rewrite them)
    Auto mode: published on schedule
  → YouTube upload (resumable, retries) + LinkedIn video post + any custom platform
```

- **Shorts:** vertical videos up to 3 minutes get `#Shorts` and are published as YouTube Shorts.
- **Chapters** are only added when the transcript supports them (YouTube's rules: start at 0:00,
  at least 3, at least 10 seconds apart).
- **Folders:** each video becomes its own post, spaced by *Hours between videos*.
- Your video files are never modified or copied; only small frame images go to `workspace/media/`.

## In the dashboard

**🎬 Video → post** tab:
1. Enter a video file or folder path and click **Check**. You'll see each video's length and format.
2. Describe the video, or pick an example: *Dev tutorial*, *Product demo*, *Short clip*, *Talk/vlog*.
   Mention links (GitHub repo, website) you want in the description.
3. Choose YouTube and/or LinkedIn (and any custom platforms), visibility and category.
4. Click **Inspect & write metadata**.

## From the command line

```powershell
python -m creatoros video D:\Videos\fastapi-aws.mp4 -i "Tutorial: deploy FastAPI to AWS, repo github.com/me/demo" --to youtube,linkedin
python -m creatoros video D:\Videos\shorts --to youtube --privacy unlisted --interval 12
```

## Transcripts (recommended)

```powershell
pip install faster-whisper
```

Runs on your own computer for free. The first run downloads a speech model (about 150 MB for
"base"). Without it, the agent writes from the frames only: titles are still good, but there
are no chapters.

## YouTube notes

- Connect YouTube on the **Connections** tab ([guide](CONNECTIONS.md)).
- **Uploads stay private until your Google project is audited.** Google locks videos uploaded
  through unaudited API projects to private. Open YouTube Studio and switch them to Public, or
  apply for the audit in the Google Cloud console.
- Custom thumbnails need a verified YouTube channel (phone verification in YouTube settings).
  If yours isn't verified, the upload still succeeds and YouTube picks the thumbnail itself.
- API uploads use your daily YouTube quota (each upload costs about 1,600 of the default 10,000 units).

## LinkedIn notes

- MP4, 3 seconds to 30 minutes, up to 500 MB.
- LinkedIn processes the video for up to a few minutes before the post goes live.

## Planned: the video editor

Cutting clips, auto-captions, music and voiceover are planned for the editor module; see
[`creatoros/modules/video/README.md`](../creatoros/modules/video/README.md).
