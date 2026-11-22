# Video module (planned for v0.3)

Folders it will use:

| Folder | What goes there |
|---|---|
| `workspace/clips/` | Your raw clips (mp4, mov...). New files are picked up automatically. |
| `workspace/references/` | Reference videos: "edit it like this" (used for style only). |
| `workspace/music/` | Optional background music you have the rights to. |
| `workspace/voices/` | Your own voice recordings, or voice samples for a third-party TTS. |
| `workspace/output/video/` | Finished videos. |

Example prompt:

```
python -m creatoros video "30s tech-news reel from my clips, style like @references/style.mp4"
```

Pipeline: analyse clips (Whisper transcript, PySceneDetect cuts, silence removal) → build a style
profile from the reference (cut pacing, caption style, framing, sampled frames described by a
vision model) → the LLM writes a JSON edit plan → FFmpeg renders it (captions, music ducking,
voiceover, 9:16 or 16:9) → preview on Telegram for approval → upload.

Voiceover options: your own recorded voice, or a third-party TTS API that you configure
(ElevenLabs, a cloned voice, Piper/Coqui running locally).
