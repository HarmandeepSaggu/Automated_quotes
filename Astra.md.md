# ASTRA PROJECT: GLIMPSE OF THOUGHTS AUTOMATION

You are a Senior Python Architect, Automation Engineer, AI Content System Designer, and Social Media Infrastructure Engineer.

Build a COMPLETE production-ready project.

The objective is to create a daily quote-posting system that generates aesthetically consistent quote images in a fixed brand style and optionally publishes them to social media.

---

# PROJECT NAME

Glimpse Of Thoughts

---

# PRIMARY OBJECTIVE

Every morning I will manually run:

```bash
python main.py
```

The system should automatically:

1. Select or generate a quote.
2. Generate an image.
3. Generate a caption.
4. Generate hashtags.
5. Preview output.
6. Ask for confirmation.
7. Post to configured platforms.
8. Save logs.
9. Save generated content history.
10. Maintain a consistent visual identity.

---

# REFERENCE DESIGN SYSTEM

The visual style must remain extremely close to the provided reference.

STYLE CHARACTERISTICS:

- Minimalist
- Premium
- Editorial
- Calm
- Luxury
- Large whitespace
- No decorations
- No icons
- No gradients
- No borders
- No illustrations
- No emojis inside image

---

# BACKGROUND

Color:

#F5F3EF

Alternative allowed:

#F4F2EE
#F7F6F3

The background must remain constant.

---

# TYPOGRAPHY

Preferred fonts:

1. Cormorant Garamond Italic
2. Playfair Display Italic
3. Libre Baskerville Italic

Fallback:

Georgia Italic

Requirements:

- Elegant
- Thin
- Premium
- Editorial look

---

# LAYOUT RULES

Canvas Size:

1080 x 1350

Instagram Portrait

Quote Area:

Position:
X = 180
Y = 450

Width:
650px

Alignment:
Left

Font Size:
42

Line Height:
1.7

Color:
#2B2B2B

---

# SIGNATURE

Always display:

- Glimpse Of Thoughts

Position:

X = 180
Y = 1000

Font Size:
20

Color:
#555555

---

# NEGATIVE SPACE RULE

Very important.

Maintain large empty areas.

Do NOT center everything.

Do NOT fill empty space.

Do NOT create social-media-style clutter.

The design should feel like a luxury magazine page.

---

# DAILY QUOTE ENGINE

Support:

## Option A

quotes/quotes.txt

Read next unused quote.

---

## Option B

quotes/quotes.csv

Columns:

quote
author
category

---

## Option C

Generate quote using OpenAI API.

Categories:

- Life
- Self Growth
- Motivation
- Sikh Wisdom
- Discipline
- Success
- Relationships
- Stoicism
- Mindfulness

---

# CAPTION GENERATION

Generate:

1 short caption

Example:

Some memories fade.
Some feelings stay forever.

---

# HASHTAG ENGINE

Generate:

15–25 hashtags

Mix:

- niche
- medium
- broad

Avoid spam hashtags.

---

# OUTPUT STRUCTURE

project/

assets/

fonts/

output/

logs/

quotes/

templates/

social/

config/

main.py

requirements.txt

README.md

.env.example

---

# FILE NAMING

Save image:

output/YYYY-MM-DD.png

Save metadata:

output/YYYY-MM-DD.json

Save caption:

output/YYYY-MM-DD-caption.txt

---

# HISTORY SYSTEM

Prevent duplicate quotes.

Maintain:

history/history.json

Track:

- quote
- date
- image
- platform

---

# PREVIEW MODE

Before posting:

Show image preview.

Display:

Quote:
Caption:
Hashtags:

Prompt:

Post this content? (Y/N)

---

# SOCIAL MEDIA MODULES

Create separate modules:

social/

instagram.py

facebook.py

threads.py

twitter.py

pinterest.py

---

# ENV VARIABLES

Store:

OPENAI_API_KEY

INSTAGRAM_TOKEN

FACEBOOK_TOKEN

THREADS_TOKEN

TWITTER_TOKEN

PINTEREST_TOKEN

inside:

.env

---

# LOGGING

Create logs:

logs/app.log

Track:

- generation success
- generation failure
- posting success
- posting failure

---

# ERROR HANDLING

Handle:

- API failures
- network failures
- invalid quote data
- missing fonts
- duplicate quotes
- invalid credentials

---

# CONFIG SYSTEM

Create:

config/settings.yaml

Allow editing:

Brand Name

Fonts

Colors

Positions

Output Size

Hashtag Count

Platforms

---

# BRAND LOCK MODE

Extremely important.

The visual identity must remain consistent.

Only the quote text changes.

Everything else should remain identical unless manually edited in settings.yaml.

---

# ADVANCED MODE

Create optional support for:

- Windows Task Scheduler
- Linux Cron
- AI quote generation
- Multiple templates
- Analytics tracking

---

# DELIVERABLE

Generate:

1. Complete folder structure
2. Complete production-ready code
3. requirements.txt
4. README.md
5. .env.example
6. settings.yaml
7. All social modules
8. Image generation module
9. Quote engine
10. Posting engine

Do not provide partial code.

Generate every file completely.

The final result must be runnable after:

pip install -r requirements.txt

python main.py