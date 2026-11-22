# Contributing to CreatorOS

Thanks for helping! CreatorOS aims to be a content studio anyone can run on their own
machine, with any model.

## Getting started

```powershell
git clone https://github.com/<you>/CreatorOS
cd CreatorOS
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
python -m creatoros check
```

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) first: it explains how the pieces fit together.

## Good first contributions

- **New publisher**: Hashnode, Ghost, WordPress, Blogger, LinkedIn ([guide](docs/PUBLISHERS.md#writing-your-own-publisher))
- **New source**: GitHub Trending, Product Hunt, arXiv, Lobsters (add a function in `modules/blog/scout.py`)
- **New post type**: share good `blog.angles` presets ([guide](docs/CONFIGURATION.md#post-types-angles))
- **Social module**: turn each post into an X/Bluesky/LinkedIn thread
- **Video module**: see `creatoros/modules/video/README.md`
- Translations, cover images, better dashboard UX

## Guidelines

- Keep the core model-agnostic: anything model-specific belongs in `llm.py`.
- Never log or expose secrets; read them with `config.env()` from `.env`.
- New settings need a default in `config.yaml`, a check in `settings.py` if they can be
  wrong, and a line in `docs/CONFIGURATION.md`.
- Test without spending API money: `python tests/test_pipeline.py` runs the whole
  pipeline with a fake model. Add a test there for new behaviour.
- One feature per pull request, with a clear description and screenshots for UI changes.

## Versioning

[Semantic Versioning](https://semver.org): `MAJOR.MINOR.PATCH`. Update
`creatoros/__init__.py` and [CHANGELOG.md](CHANGELOG.md), then tag the release:

```powershell
git tag -a v0.2.0 -m "CreatorOS v0.2.0"
git push origin v0.2.0
```

## Responsible use

Contributions must not help with spam, impersonation, plagiarism, or bypassing platform
rules (e.g. auto-posting to communities that forbid it).
