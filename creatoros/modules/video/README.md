# Video module

## Available now: video → post

`videoinfo.py` (ffprobe, frames, optional faster-whisper transcript) and `posting.py`
(AI-written YouTube/LinkedIn metadata, one post per video). Publishing lives in
`creatoros/publishers/youtube.py` and `linkedin.py`. See [docs/VIDEO_POSTS.md](../../../docs/VIDEO_POSTS.md).

## Planned: the editor

Folders it will use:

| Folder | What goes there |
|---|---|
| `workspace/clips/` | Raw clips to edit. |
| `workspace/references/` | Reference videos: "edit it like this" (style only). |
| `workspace/music/` | Background music you have the rights to. |
| `workspace/voices/` | Your own voice recordings, or samples for a third-party TTS. |

Pipeline: analyse clips (transcript, scene cuts, silence removal) → style profile from the
reference (cut pacing, caption style, framing) → the LLM writes a JSON edit plan → FFmpeg
renders it (captions, music ducking, voiceover, 9:16 or 16:9) → hands the result to video → post.
