---
name: copywriting-purification
description: 将抖音/小红书视频链接、本地视频或原始文字稿一键转化为"分享式提纯版原文"并自动交付飞书文档。Trigger: 文案提纯、整理文字稿、结构化逐字稿、分享式提纯版原文、直播文字稿、短视频文字稿、播客文字稿、录音转写稿，或直接发送平台链接/本地视频。
---

# 文案提纯

## Overview

Convert video links, local videos, or raw transcripts into a structured "分享式提纯版原文" and deliver as a Feishu doc. Three input modes: platform link (auto-extract + transcribe), local video (upload + transcribe), and raw text (purify directly).

## Prerequisites

Environment variables required. The skill reads credentials from env; never hardcode them.

```bash
# TikHub — platform video extraction
export TIKHUB_API_KEY="your-key"

# Alibaba Bailian / DashScope — Paraformer-v2 ASR
export DASHSCOPE_API_KEY="sk-your-key"

# Alibaba OSS — local video upload
export OSS_ACCESS_KEY_ID="your-key"
export OSS_ACCESS_KEY_SECRET="your-secret"
export OSS_BUCKET_NAME="hermes-videos"
export OSS_ENDPOINT="oss-cn-hangzhou.aliyuncs.com"
```

DashScope Paraformer-v2 does NOT need a Bailian Workspace ID. If any credential is missing, pause and ask.

### Network routing

| Service | Network path | Notes |
|---|---|---|
| TikHub API | Requires proxy/VPN (Cloudflare-backed) | Use `curl` via Bash tool |
| Alibaba OSS | Direct connection (domestic) | Set `NO_PROXY=*` in Python scripts |
| DashScope | Direct connection (domestic) | Set `NO_PROXY=*` in Python scripts |

## Input Modes

On receiving a request, inspect the input and route to one of three modes:

### Mode A: Platform Link → Video → ASR → Purify

Trigger: Douyin (`v.douyin.com`, `douyin.com/video/...`) or Xiaohongshu (`xiaohongshu.com/explore/...`, `xhslink.cn/`) share link.

**Step 1 — Extract video URL via TikHub**

Douyin:
```
GET https://api.tikhub.dev/api/v1/douyin/app/v3/fetch_one_video_by_share_url?share_url={url_encoded}
Authorization: Bearer {TIKHUB_API_KEY}
```
Extract `data.aweme_detail.video.play_addr.url_list[0]`.

Xiaohongshu:
```
GET https://api.tikhub.dev/api/v1/xiaohongshu/app_v2/get_video_note_detail?share_text={url_encoded}
Authorization: Bearer {TIKHUB_API_KEY}
```
Extract video URL from `data.data[0].video_info_v2.media.stream` — prefer h264 HD stream for ASR. The response has `stream.h265`, `stream.h264`, `stream.h266`, `stream.av1` — each contains `master_url` and `backup_urls`.

**Step 2 — Download video**

TikHub CDN URLs are short-lived. Download immediately.

```bash
curl -s -L --max-time 120 \
  -H "User-Agent: Mozilla/5.0" \
  -H "Referer: https://www.xiaohongshu.com" \
  -o "/tmp/structured_transcript/{note_id}.mp4" \
  "{video_url}"
```

Create `/tmp/structured_transcript/` if it does not exist. Clean up after delivery.

**Step 3 — Transcribe via Paraformer-v2**

Upload video to OSS first (TikHub CDN URLs are too short-lived):

```python
import os, oss2

auth = oss2.Auth(os.environ["OSS_ACCESS_KEY_ID"], os.environ["OSS_ACCESS_KEY_SECRET"])
bucket = oss2.Bucket(auth, os.environ["OSS_ENDPOINT"], os.environ["OSS_BUCKET_NAME"])
object_name = f"transcripts/{aweme_id}.mp4"
bucket.put_object_from_file(object_name, local_video_path)
oss_url = f"https://{os.environ['OSS_BUCKET_NAME']}.{os.environ['OSS_ENDPOINT']}/{object_name}"
```

Transcribe:

```python
from dashscope.audio.asr import Transcription
from http import HTTPStatus
import dashscope, requests

dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]

task_response = Transcription.async_call(
    model='paraformer-v2',
    file_urls=['{OSS_URL}'],
    language_hints=['zh', 'en']
)

transcribe_response = Transcription.wait(task=task_response.output.task_id)
if transcribe_response.status_code == HTTPStatus.OK:
    result_url = transcribe_response.output['results'][0]['transcription_url']
    asr_data = requests.get(result_url, timeout=30).json()
    transcript_text = asr_data['transcripts'][0]['text']
```

Paraformer-v2 may misrecognize homophones. Common fixes: 小红书电商←小魔书店商, 低粉←一份, 爆款←报款. The purification step handles these.

**Step 4 — Purify** → Mode C.

### Mode B: Local Video → OSS → ASR → Purify

Trigger: local video file path(s) or folder of videos.

1. Validate files (mp4, mov, avi, mkv, wav, mp3, flv, webm).
2. Upload to OSS, transcribe via Paraformer-v2 (same as Mode A Step 3).
3. Purify → Mode C.

Batch handling: process serially, merge transcripts by video, purify as one document.

### Mode C: Raw Text → Purify

Trigger: raw transcript text, text file, or tidy existing transcription.

## Purification Rules

Default output: **分享式提纯版原文** — not a summary, not a raw transcript.

### Document structure

1. Source line (Mode A/B only): `> **来源**：[title]（link）` for platform, or `> **来源**：本地视频路径` for local.
2. `# 标题` — from video title, topic, or source name.
3. Optional one-line notes when useful: ASR corrections (e.g. "修正同音词：报文→爆款").
4. A small number of `##` themes (2–5).
5. `###` subheadings under each theme.
6. Cleaned paragraphs under each heading.

Forbidden sections: `一句话总结`, `核心要点`, `启发`, `结论`, `重点摘要`, `其他有效观点`, `补充内容`, `杂项`.

### What to remove

- Timestamps, speaker labels, greetings, waiting-room chatter, screen-sharing talk.
- Repeated audience checks, off-topic banter.
- Filler words, stutters, duplicated phrases, sentence fragments.
- Obvious live-room noise and ASR artifacts.

### What to keep

- Original meaning, tone, key judgments.
- Cases, examples, numbers, analogies.
- The full argument chain.
- Important original wording and signature phrases.
- For short videos: hooks, punchlines, rhythm, transitions, call-to-action.
- For podcasts: conversational flow, disagreements, topic transitions.

### What NOT to do

- Do NOT add facts, external information, or interpretation.
- Do NOT rewrite into a new article — it should still read like the speaker.
- Do NOT bold every paragraph — only bold important judgments, strong quotes, and concrete principles.
- Do NOT invent timestamps or speaker labels.

### Heading rules

- Use concrete headings describing actual content.
- Use a few large themes (2–5 `##` sections), not dozens of fragments.
- No garbage-bin headings.

### ASR cleanup

- Fix obvious speech-recognition errors only with high confidence.
- Standardize recurring product/tool names when clear.
- Add punctuation and paragraph breaks naturally.

## Delivery: Feishu Doc

Use the `lark-doc` skill to create a Feishu doc with the purified Markdown content. Doc title = `# 标题`.

User-facing reply:
1. Feishu doc URL (clickable link).
2. One line: "已交付飞书文档——《标题》，约 N 字".
3. If ASR cleanup was significant, mention briefly.

Do NOT dump the full transcript in chat.

## Quality Bar

- Source line present (Mode A/B).
- Source meaning and argument order preserved.
- Not a summary, checklist, or commentary.
- Greetings, filler, repetition, timestamps, speaker labels, fragments removed.
- Key judgments, examples, numbers, analogies, phrases remain.
- Headings specific and limited to real themes.
- Bold text highlights high-value content without over-marking.
- Chat reply is one-liner only.

## Local Scripts

- `scripts/build_structured_transcript.py` — builds Markdown skeleton from a raw transcript with section headings and cleanup rules.
