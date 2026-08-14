---
name: feishu-xhs-note-sync
description: Use when a user provides a Feishu/Lark Base link and asks to read Xiaohongshu note links from a Base template, collect note title/content/engagement/account/cover data, and write results back to the same visible Base view records.
---

# Feishu XHS Note Sync

Use this skill for the fixed Feishu Base template that stores Xiaohongshu note links in `笔记信息` and needs collection results written back to the same rows.

## Required Inputs

- A Feishu Base URL that includes `/base/<base_token>?table=<table_id>&view=<view_id>`.
- The table must already contain the template fields. Read `references/template.md` when checking field names or behavior.
- `lark-cli` must already be authenticated in the local environment.

## Workflow

1. Parse the user-provided Base URL. Do not guess missing `table` or `view`.
2. Run a dry-run first:

```bash
python3 /Users/huangdalu/.codex/skills/feishu-xhs-note-sync/scripts/feishu_xhs_note_sync.py \
  --base-url '<FEISHU_BASE_URL>' \
  --dry-run
```

3. Review the dry-run output for record IDs, source URLs, and outgoing field values.
4. If the user's task authorizes writeback, run write mode:

```bash
python3 /Users/huangdalu/.codex/skills/feishu-xhs-note-sync/scripts/feishu_xhs_note_sync.py \
  --base-url '<FEISHU_BASE_URL>' \
  --write
```

5. Confirm the command's verification output. Write mode re-reads written records and reports mismatches.

## Hard Rules

- Process only records visible in the URL's `view`.
- Use `lark-cli` for Feishu Base reads and writes.
- Do not add, delete, rename, or change field types in the Base.
- Do not clean or normalize Xiaohongshu short-link parameters; use the first raw Xiaohongshu URL found in `笔记信息`.
- Skip a record when any target field already has a value.
- Leave unknown interaction counts blank; never write `0` for unknown counts.
- Keep per-record failures isolated. Successful records can still be written when other rows fail.
- Do not log tokens, secrets, cookies, or `.env` values.

## Script Behavior

The script uses Python 3 standard library only. It collects public Xiaohongshu pages with a mobile user agent, parses `noteData`, then checks the desktop detail page `og:image` / rendered image markup for an `!nd_dft...` cover URL before falling back to mobile image data. It writes via the Feishu bitable batch update API and verifies values by record ID.

For image or LivePhoto notes, `封面链接` prefers the desktop no-center-watermark cover URL when publicly exposed. For video notes, `封面链接` is the explicit video cover when present, otherwise the first image fallback.

Run maintenance tests after editing the script:

```bash
python3 -m unittest /Users/huangdalu/.codex/skills/feishu-xhs-note-sync/scripts/test_feishu_xhs_note_sync.py -v
```
