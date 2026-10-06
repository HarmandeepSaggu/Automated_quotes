# Glimpse Of Thoughts

A production-oriented daily quote automation system for the **Glimpse Of Thoughts** brand. It creates a consistent editorial quote image, caption, and hashtag set, previews the result, asks for approval, and can publish to configured social platforms.

The default brand is intentionally quiet: a constant warm off-white canvas, an italic serif, large whitespace, left alignment, and a fixed signature. Only the quote content changes during a normal run.

## Quick start

Requires Python 3.10 or newer.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
copy .env.example .env       # Windows
# cp .env.example .env       # macOS/Linux
python main.py
```

The default run reads the next unused quote from `quotes/quotes.txt`, renders the image, opens a preview when a graphical image viewer is available, prints the content, and asks:

```text
Post this content? (Y/N)
```

Instagram Reels is enabled in `config/settings.yaml`. A fresh installation remains safe until you approve a post. To publish a Reel, configure Instagram credentials and Cloudinary video hosting in `.env`; the generated MP4 is uploaded automatically and its HTTPS URL is sent to Instagram.

## Generated files

For `2025-01-31`, the application writes:

- `output/2025-01-31.png` — 1080 x 1350 PNG
- `output/2025-01-31-reel.mp4` — 1080 x 1920 Reel video when Instagram Reels are enabled
- `output/2025-01-31.json` — quote, caption, hashtags, selected audio, status, and platform results
- `output/2025-01-31-caption.txt` — caption and hashtags
- `history/history.json` — durable quote and publication history
- `logs/app.log` — generation and posting events

The history file is written atomically and records quote, date, image, status, and each platform result. Used quote text is normalized so whitespace and case changes cannot bypass duplicate protection.

## Configuration

Edit `config/settings.yaml` to change brand and operational settings:

- `brand.name` and `brand.lock_mode`
- canvas size and colors
- font search order
- quote/signature positions, width, font sizes, and line height
- quote source (`auto`, `txt`, `csv`, or `ai`)
- hashtag count (must remain 15–25)
- enabled platforms
- network timeout/retry defaults
- preview behavior
- optional local analytics (`analytics.enabled` and `analytics.file`)
- Instagram Reel settings (`platform_settings.instagram.media_type`, `audio_directory`, and `video`)

When Instagram is configured with `media_type: reels`, the renderer places the existing 1080 x 1350 quote image on a 1080 x 1920 canvas, muxes the next audio file from `Audio/`, and repeats the five-file rotation after the last file. The rotation advances only after Instagram reports a successful Reel publish; cancelled, dry-run, and failed runs reuse the same audio. Files are selected alphabetically by filename.

Brand lock is a policy enforced by configuration: the renderer always uses the configured layout and does not apply random styles, decorations, gradients, icons, or emojis. Font fitting stays within the explicit bounds in `settings.yaml`.

### Editorial text layout

Quotes are written as natural prose, not short verse-like fragments. The default layout uses:

- An **880px-wide** text area with **100px side margins**, left aligned at y=450.
- A **36px** italic serif, with a bounded **34px minimum** if a longer paragraph needs fitting.
- **1.4× baseline spacing** (about 50px), rather than adding that amount as extra blank space.
- Normally **2–4 rendered lines**, never more than four or taller than **220px**. Very short quotes may remain one line rather than being artificially stretched.
- Pixel-measured line breaks that favor sentence/clause pauses, balanced lengths, and approximately 8–15 words where possible. Word counts are a preference, not a reason to force a break.
- Measured ink bounds, including italic overhang, and clearance before the signature. Text that cannot fit at the minimum size produces an actionable error instead of clipping, truncating, or shrinking indefinitely.

Set `image.quote.width`, `image.quote.max_lines`, `image.quote.max_height`, `image.font_size`, `image.min_font_size`, and `image.line_height` to adjust these bounds. The background, canvas, colors, and signature remain consistent.

### Fonts

The preferred fonts are Cormorant Garamond Italic, Playfair Display Italic, and Libre Baskerville Italic, with Georgia Italic as the fallback. Put licensed files in `fonts/` using the names in `config/settings.yaml`. The renderer also checks common system font paths and finally falls back to Pillow's default font so the pipeline remains runnable. A production deployment should install and verify a preferred font before publishing.

### Quote sources

**Plain text** (`quotes/quotes.txt`) contains 500 quotes as natural paragraphs. Separate quotes with a blank line. Ordinary newlines within a block are normalized to spaces, so older short-line content is also reflowed rather than rendered as poetry:

```text
Most people aren't tired from work. They're tired from carrying thoughts they never speak about.

Some goals stay attractive because you only visit them in your imagination. A real commitment includes the ordinary afternoons you never put in the picture.
```

Source paragraphs do not dictate screen line counts; the renderer measures the selected font and text area. Formatting-only changes do not bypass normalized quote-history checks.

Legacy one-line pipe-separated records are still supported:

```text
Quote text | Author | Category
```

**CSV** (`quotes/quotes.csv`) requires these columns:

```csv
quote,author,category
A quote.,Author,Life
```

**OpenAI** uses `OPENAI_API_KEY` and creates an original quote as JSON. The prompt asks for a compact 20–35-word prose paragraph with complete sentences and no manual line breaks, generic motivation, or poetic fragments. Returned whitespace is normalized, the 20–60-word content envelope is validated, and the renderer separately enforces its width/line/height limits. It is only used when `quotes.source: ai`, or in `auto` mode after local sources are exhausted. AI output is duplicate-checked. Never use AI-generated text as an attributed quotation without editorial review.

### Tests

```bash
python -m unittest discover -s tests -v
```

Layout tests check all 500 paragraphs, natural-pause wrapping, source-newline normalization, baseline spacing, fallback font sizing, configuration bounds, and failure on content that cannot fit.

### Environment variables

Copy `.env.example` to `.env`. Never commit `.env`.

- `OPENAI_API_KEY`
- `INSTAGRAM_TOKEN`, `INSTAGRAM_ACCOUNT_ID`
- `INSTAGRAM_API_HOST` — optional; leave blank to use `graph.instagram.com` for `IG...` tokens and `graph.facebook.com` for Facebook user tokens
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` — signed video uploads
- `CLOUDINARY_UPLOAD_PRESET` — optional alternative to signed uploads
- `CLOUDINARY_FOLDER` — optional Cloudinary folder for generated Reels
- `FACEBOOK_TOKEN`, `FACEBOOK_PAGE_ID`
- `THREADS_TOKEN`, `THREADS_USER_ID`
- `TWITTER_TOKEN`, `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_TOKEN_SECRET`
- `PINTEREST_TOKEN`, `PINTEREST_BOARD_ID`
- `PUBLIC_IMAGE_BASE_URL`
- `PUBLIC_VIDEO_BASE_URL` — optional fallback public HTTPS base URL serving generated Reel MP4 files when Cloudinary is not configured

## Social publishing setup

Set platform names in `config/settings.yaml`:

```yaml
platforms:
  - instagram
  # - facebook
```

Each enabled adapter validates credentials at publish time and logs failures independently. Credentials alone are not enough for every API:

- **Instagram image posts** and **Threads** require a professional account/API setup and a publicly reachable HTTPS image URL.
- **Instagram Reels** require a professional account/API setup and a publicly reachable HTTPS video URL. The publisher supports Instagram Login tokens (`graph.instagram.com`) and Facebook Login user tokens (`graph.facebook.com`), selecting the host automatically unless `INSTAGRAM_API_HOST` or `platform_settings.instagram.api_host` is set. The Reel video includes the selected local audio file; Instagram's Saved audio library is not used by the API.
- **Facebook** publishes a photo to the configured Page and needs a Page access token.
- **X/Twitter** requires OAuth 1.0a keys/secrets for media upload; `TWITTER_TOKEN` is accepted as an access-token fallback.
- **Pinterest** requires a board ID and a publicly reachable HTTPS image URL.

The application never treats a local filesystem path as a public URL. For Reels, Cloudinary is preferred when its environment variables are configured; otherwise configure `PUBLIC_VIDEO_BASE_URL` or an explicit `platform_settings.instagram.public_video_url`. A successful post on one platform does not hide failures on another; inspect the JSON metadata and `logs/app.log`.

### Instagram Reels with local audio

The supplied files in `Audio/` are used in alphabetical order, one per Reel, then the rotation starts again. The default Reel configuration is already enabled:

```yaml
platforms:
  - instagram
platform_settings:
  instagram:
    media_type: reels
    audio_directory: Audio
    public_video_url: ""
```

Configure Cloudinary in `.env` and the application uploads the generated MP4 before creating the Instagram media container. It sends Cloudinary's returned HTTPS URL to Instagram. If Cloudinary is not configured, set `public_video_url` to the public URL of the generated MP4, or set `PUBLIC_VIDEO_BASE_URL` in `.env` to the public directory URL serving `output/`. Instagram's Content Publishing API requires the video URL to be publicly reachable over HTTPS. The local audio is encoded into the Reel as original audio; an Instagram Saved-audio track cannot be attached or selected through this API.

## Command-line modes

```bash
python main.py                  # interactive preview and approval
python main.py --no-preview     # terminal content, still asks approval
python main.py --yes             # approve without prompt (controlled automation)
python main.py --dry-run         # generate and save, never publish
python main.py --source csv      # choose CSV for this run
python main.py --source ai       # generate with OpenAI
python main.py --force           # replace today's output intentionally
python main.py --date 2026-01-31 # deterministic date for a scheduled run
```

`--yes` should only be used in an environment where the generated content is reviewed or the workflow is intentionally unattended. `--dry-run` is suitable for testing credentials and scheduled generation without publishing.

## Scheduling

Example helpers are provided in `scripts/`:

- Windows Task Scheduler: `scripts/run_daily.bat`
- Linux/macOS cron: `scripts/run_daily.sh`

Use an absolute project path in the scheduler, run from the project directory, and choose `--yes` only for a reviewed automated workflow. Keep secrets in a protected `.env` file.

## Operational notes

- Output names are date-based by specification. A second run for the same date requires `--force` to prevent accidental replacement.
- If a platform partially succeeds, the metadata records every platform result. Resolve the failed platform and decide whether to retry rather than blindly rerunning all platforms.
- API/network errors, missing fonts, malformed CSV rows, invalid settings, duplicate quotes, and missing credentials are surfaced with safe messages and written to `logs/app.log`.
- Optional analytics writes append-only local event data to the configured JSON path without allowing analytics failures to interrupt publishing.
- The default local workflow needs no API key and can be tested offline.
