---
name: article-exercise
description: Generate a personalised fillable exercise file from an article or transcript. Use this skill whenever the user wants to process, apply, or internalise ideas from an article — including when they say things like "turn this into an exercise", "make me a worksheet for this", "help me apply this article", "distil this into actionable steps for me", or "create an exercise from this". Also trigger when the user has just transcribed something with /media-transcribe and wants to work through it. The exercise mirrors the article's own structure, not a generic template.
---

# Article Exercise Generator

Turn any article or transcript into a personalised, fillable exercise — structured around the article's own frameworks, steps, and questions — saved to Obsidian.

**Output path:** `/Users/zhiyuling/Library/Mobile Documents/iCloud~md~obsidian/Documents/ZY Combined/exercises/`

---

## How to invoke

The user will either:
- Paste article text directly
- Give you a file path to a transcript (e.g. from `/media-transcribe`)
- Reference the most recently transcribed file

If given a file path, read it. If no path is given, check the most recent file in the media-gobbler subfolders.

---

## Step 1 — Read and analyse the article

Read the full content. Identify:

1. **The core problem** the article addresses — one sentence
2. **The frameworks, models, or techniques** it presents — list each by name
3. **The article's own structure** — does it have numbered steps? Sections? A before/after arc? Closing questions?
4. **Actionable outputs** it asks of the reader — e.g. "list your top 25", "fill in this compass", "design your week"

This analysis drives the exercise structure. The exercise must mirror what the article actually teaches, not a generic worksheet.

---

## Step 2 — Build the exercise

Write a Markdown exercise file with this structure:

### Header (always)
```
# {Article Title} — Exercise
*Based on: [{Article Title}]({source URL}) by {Author if known}*
*Article saved to: {file path}*
---
```

### One section per framework/technique
For each framework or technique in the article:

- Name the section after the technique (e.g. `## The 5/25 Rule`, not `## Step 1`)
- Open with a 1–2 sentence summary of what the technique is and why it matters
- Provide the specific prompts, tables, or blank fields the article calls for
  - If the article says "list 25 things" → create 25 numbered blank lines
  - If it describes a framework with tiers → make a table with those exact tier names
  - If it gives examples → include the example structure as a model, then blank fields for the user
- Close each section with a short `> Tip:` block quoting the key insight from the article

The goal: the user should be able to fill this in without re-reading the article. Every prompt should make sense on its own.

### Closing reflection (always)
Pull 3–5 questions directly from the article's conclusion or "questions to ask yourself" section. If the article doesn't have explicit closing questions, derive them from its thesis.

```
## Closing Reflection
1. {question from article}
2. {question from article}
...
```

---

## Step 3 — Save the file

Save to:
```
/Users/zhiyuling/Library/Mobile Documents/iCloud~md~obsidian/Documents/ZY Combined/exercises/YYYYMMDD_{Sanitised_Title}_Exercise.md
```

Sanitise the title: replace non-word characters with `_`, max 60 chars.

---

## Step 4 — Report to the user

Tell the user:
- The file path it was saved to
- The article's core problem in one sentence
- The techniques covered (list them)
- How many sections the exercise has
