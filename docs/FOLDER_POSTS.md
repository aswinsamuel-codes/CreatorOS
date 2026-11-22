# Folder → post (certificates, projects, events)

Have a pile of certificates you never got around to posting? Point CreatorOS at the folder.

## How it works

```
Your folder (JPG, PNG, WEBP, PDF)
  → every file is converted to an image (PDFs: first page)
  → a vision model reads it: type, title, issuer, date, skills, alt text
  → the writer composes the post(s) in your agent role, following your instruction
  → Approval mode: preview with images on Telegram + Posts tab
    Auto mode: published on schedule
  → LinkedIn post with 1 image or a multi-image post (up to 20)
```

Your original files are never changed. Converted copies are stored in `workspace/media/`
(ignored by git).

## In the dashboard

**📁 Folder → post** tab:

1. Enter the folder path (e.g. `D:\Certificates`) and click **Check folder**.
2. Write what you want, or click an example:
   - *All certificates, one post*
   - *One certificate a day*
   - *Project showcase*
   - *Event recap*
3. Choose where to post (LinkedIn), the mode, and optionally a role for this job.
4. Click **Inspect & write posts**. Each file takes about 10-30 seconds.

## Modes

| Mode | Result |
|---|---|
| **Combined** | One post with all images. More than 20 files are split into several posts ("part 1 of 2"). |
| **Series** | One post per file, spaced by *Hours between posts*, starting at *Start at*. Approve them all at once and they'll go out one by one. |

Approving a post whose time hasn't come yet marks it `scheduled`; it's published
automatically when due (checked every 2 minutes while CreatorOS runs). **⚡ Publish now**
skips the wait.

## From the command line

```powershell
python -m creatoros folder D:\Certificates -i "Share all my certificates in one post, grouped by skill" --to linkedin
python -m creatoros folder D:\Certificates -i "One a day, say what I learned" --mode series --interval 24 --role personal_brand
```

## Accuracy and privacy

- The writer only states what's visible on the files or in your profile and documents.
  Check names and dates in the preview before approving.
- Certificate IDs, serial numbers, emails and phone numbers are never put into posts.
- Alt text is generated for every image (better accessibility and reach).

## Models

Reading images needs a **vision-capable** scout model. Claude models all support images.
For local models use a vision model such as `gemma3`, `llava` or `qwen2.5vl` in Ollama.
