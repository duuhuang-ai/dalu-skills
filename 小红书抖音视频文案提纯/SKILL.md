---
name: 小红书抖音视频文案提纯
description: 将抖音/小红书视频链接、本地视频或原始文字稿一键提取文案并转写、提纯整理成可直接分享的干净原文，自动交付飞书文档。覆盖三类输入：平台链接自动提取+转写、本地视频/音频批量转写、纯文字稿直提纯。触发词：视频文案提纯、小红书抖音视频文案提纯、文案提纯、整理文字稿、结构化逐字稿、直播文字稿、短视频文字稿、播客文字稿、录音转写稿，或直接发送平台链接/本地视频。
---

# 小红书抖音视频文案提纯

## Prerequisites

Before use, ensure the following are configured. The skill reads credentials from environment variables; never hardcode them.

```bash
# TikHub (platform video extraction)
export TIKHUB_API_KEY="your-key"
# API domain: use api.tikhub.dev for mainland China, api.tikhub.io for overseas

# Alibaba Bailian / DashScope (Paraformer-v2 ASR)
export DASHSCOPE_API_KEY="sk-your-key"

# Alibaba OSS (local video upload)
export OSS_ACCESS_KEY_ID="your-key"
export OSS_ACCESS_KEY_SECRET="your-secret"
export OSS_BUCKET_NAME="hermes-videos"
export OSS_ENDPOINT="oss-cn-hangzhou.aliyuncs.com"
```

> **关于 Workspace ID**：百炼控制台"默认业务空间"下拉里的 ID 仅在调用百炼"应用 API"时使用（应用编排、智能体、工作流等）。本 skill 用的是 DashScope SDK 直接调用 Paraformer-v2 模型，**不需要 Workspace ID**。

If any credential is missing when needed, pause and ask the user.

### Network routing notes

| Service | Network path | Notes |
|---|---|---|
| TikHub API | Requires proxy/VPN (Cloudflare-backed, blocked in mainland China direct) | Use `curl` via Bash tool if Python `requests` hits proxy timeouts |
| Alibaba OSS | Direct connection (domestic) | Set `NO_PROXY=*` in Python scripts to bypass proxy |
| DashScope (Paraformer-v2) | Direct connection (domestic) | Set `NO_PROXY=*` in Python scripts to bypass proxy |

When running Python scripts that only touch OSS + DashScope, prefix with `NO_PROXY=*` to avoid unnecessary proxy hops that may cause timeouts.

## Input Modes & Routing

On receiving a user request, inspect the input and route to one of three modes:

### Mode A: Platform Link → Video → ASR → Purify

**Trigger**: The user sends a Douyin (`v.douyin.com`, `douyin.com/video/...`) or Xiaohongshu (`xiaohongshu.com/explore/...`, `xhslink.cn/`) share link.

**Step 1 — Extract video URL via TikHub**

Douyin:
```
GET https://api.tikhub.dev/api/v1/douyin/app/v3/fetch_one_video_by_share_url?share_url={url_encoded}
Authorization: Bearer {TIKHUB_API_KEY}
```
Response shape (key fields only):
```
data.aweme_detail.aweme_id
data.aweme_detail.desc                      # source title
data.aweme_detail.duration                  # milliseconds
data.aweme_detail.video.play_addr.url_list  # video CDN URLs (may be short-lived)
data.aweme_detail.video.bit_rate[*].gear_name + play_addr.url_list  # multi-bitrate options
```
Take `url_list[0]` from `play_addr` (standard quality is sufficient for ASR).

Xiaohongshu:
```
GET https://api.tikhub.dev/api/v1/xiaohongshu/app_v2/get_video_note_detail?share_text={url_encoded}
Authorization: Bearer {TIKHUB_API_KEY}
```
Extract the video URL from the response data. Look for `video_url` / `video` / play address fields.

Both platforms use the same base domain. Replace with `api.tikhub.io` when user is overseas.

**Step 2 — Download video**

TikHub-extracted CDN URLs are **short-lived** (may expire within minutes). Download immediately after extraction. Route through proxy if TikTok API calls require it; video download can go direct.

```bash
# TikTok API calls: route through proxy (TikHub is Cloudflare-backed, blocked in mainland China)
curl -s --max-time 30 -G "https://api.tikhub.dev/api/v1/douyin/app/v3/fetch_one_video_by_share_url" \
  --data-urlencode "share_url={link}" \
  -H "Authorization: Bearer $TIKHUB_API_KEY" \
  -o /tmp/structured_transcript/tikhub.json

# Video download: add Referer header to bypass anti-leech
curl -s -L --max-time 120 \
  -H "User-Agent: Mozilla/5.0" \
  -H "Referer: https://www.douyin.com" \
  -o "/tmp/structured_transcript/{aweme_id}.mp4" \
  "{video_url}"
```

Create `/tmp/structured_transcript/` if it does not exist. Clean up downloaded files after the doc is delivered.

**Step 3 — Transcribe via Bailian Paraformer-v2**

Use the `dashscope` Python SDK. The video must first be uploaded to OSS for a stable public URL (TikHub CDN URLs are too short-lived for Paraformer's async processing).

```python
import os
import oss2

# Upload downloaded video to OSS
auth = oss2.Auth(os.environ["OSS_ACCESS_KEY_ID"], os.environ["OSS_ACCESS_KEY_SECRET"])
bucket = oss2.Bucket(auth, os.environ["OSS_ENDPOINT"], os.environ["OSS_BUCKET_NAME"])
object_name = f"transcripts/{aweme_id}.mp4"
bucket.put_object_from_file(object_name, local_video_path)
oss_url = f"https://{os.environ['OSS_BUCKET_NAME']}.{os.environ['OSS_ENDPOINT']}/{object_name}"
```

Then transcribe via Paraformer-v2:

```python
from dashscope.audio.asr import Transcription
from http import HTTPStatus
import dashscope
import requests
import json

dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]

task_response = Transcription.async_call(
    model='paraformer-v2',
    file_urls=['{OSS_URL}'],
    language_hints=['zh', 'en']
)

transcribe_response = Transcription.wait(task=task_response.output.task_id)
if transcribe_response.status_code == HTTPStatus.OK:
    # Step 1: fetch the transcription JSON from the result URL
    result_url = transcribe_response.output['results'][0]['transcription_url']
    asr_data = requests.get(result_url, timeout=30).json()

    # Step 2: extract text from transcripts[0].text
    transcript_text = asr_data['transcripts'][0]['text']

    # Optional: get sentence-level timestamps from asr_data['transcripts'][0]['sentences']
```

**Important**: Paraformer-v2 may misrecognize homophones (e.g. "AI" → "爱", "Excel" → "excel", "爆款" → "报款", "低粉" → "一份"). The purification step (Mode C) includes ASR cleanup rules to fix high-confidence recognition errors. Common fixes observed: 小红书电商←小魔书店商, 低粉←一份, 爆款←报款.

**Step 4 — Purify**

Proceed to Mode C with the raw ASR text.

---

### Mode B: Local Video → OSS → ASR → Purify

**Trigger**: User provides local video file path(s), or points to a folder of videos.

**Step 1 — Validate files**

Check that file(s) exist and are in a supported format (mp4, mov, avi, mkv, wav, mp3, flv, webm).

**Step 2 — Upload to OSS for public URL**

Bailian Paraformer-v2 requires a public HTTP URL. Upload each local video to OSS:

```python
import oss2

auth = oss2.Auth(os.environ["OSS_ACCESS_KEY_ID"], os.environ["OSS_ACCESS_KEY_SECRET"])
bucket = oss2.Bucket(auth, os.environ["OSS_ENDPOINT"], os.environ["OSS_BUCKET_NAME"])

object_name = f"transcripts/{filename}"
bucket.put_object_from_file(object_name, local_path)
public_url = f"https://{os.environ['OSS_BUCKET_NAME']}.{os.environ['OSS_ENDPOINT']}/{object_name}"
```

Set the OSS bucket to public-read, or generate a signed URL with long expiry. If the bucket is not public-read, use `bucket.sign_url('GET', object_name, 86400)` for a 24-hour signed URL.

> **⚠️ oss2 超时坑（实测踩过）**：`oss2.Bucket(...)` **不接受** `read_timeout` 关键字参数（只认 `connect_timeout`）。默认超时仅 60s，慢网络下上传会 `ReadTimeout` 崩溃。正确做法：`oss2.Bucket(auth, endpoint, bucket, connect_timeout=120)` 之后**再设 `bucket.timeout = 900`**（oss2 内部只用单一 timeout 值，这同时放大读写超时）。上传/转写务必加 3 次重试 + 退避，主循环包 per-video try/except，单视频失败记日志继续而非整批中断。

> **可选优化（实测有效）**：本机若没有系统级 `ffmpeg`，不必安装——在受管 venv 里 `pip install imageio-ffmpeg`，用 `imageio_ffmpeg.get_ffmpeg_exe()` 拿二进制即可。用 ffmpeg 先把视频抽成 mono 16k 的 mp3（`-vn -ac 1 -ar 16000 -b:a 64k`）再上传，能大幅缩小上传体积；**百炼 Paraformer-v2 直接吃压缩 mp3 没问题**，无需视频格式。注意 `dashscope` / `imageio-ffmpeg` 都要装进受管 venv（路径 `/Users/huangdalu/.workbuddy/binaries/python/envs/default`）；脚本涉及 OSS+DashScope 时设 `NO_PROXY=*` 绕开代理。

> **🔧 现成批量流水线脚本**：`scripts/batch_asr_pipeline.py` 已封装上述全部要点（去重 `(1)`/`( chuhai5.net )` 副本、按 `N.NN` 数字排序、oss2 超时加固、上传/转写重试、per-video 容错、24h 签名 URL、Paraformer-v2 异步转写）。用法：
> ```bash
> XHS_SOURCE_DIR="/path/to/videos" XHS_WORK_DIR="/tmp/xhs3" \
> OSS_ACCESS_KEY_ID=... OSS_ACCESS_KEY_SECRET=... OSS_BUCKET_NAME=... OSS_ENDPOINT=... \
> DASHSCOPE_API_KEY=... \
> /Users/huangdalu/.workbuddy/binaries/python/envs/default/bin/python \
>   /Users/huangdalu/.workbuddy/skills/小红书抖音视频文案提纯/scripts/batch_asr_pipeline.py [rebuild]
> ```
> 输出 `<WORK>/raw/<NN>.txt`（原始稿）、`<WORK>/manifest.json`（idx→path/title/chapter/tag）、`<WORK>/audio/<NN>.mp3`（临时音频，可删）。加 `rebuild` 强制重建清单；重跑会自动跳过已完成的视频。

**Step 3 — Transcribe via Bailian Paraformer-v2**

Same as Mode A Step 3, using the OSS public URL.

**Step 4 — Purify**

Proceed to Mode C with the raw ASR text.

**Batch handling**: For multiple videos in a folder, process serially (one at a time, due to Bailian QPS limits). After all are transcribed, merge transcripts into a single document organized by video, then purify as one document.

---

### Mode C: Raw Text → Purify

**Trigger**: User provides raw transcript text, a text file, or asks to tidy an existing transcription.

This is the original skill workflow. Follow the purification rules below directly.

---

## Purification Rules

Default output: **提纯版原文** — not a summary, not a raw transcript.

The document structure:
1. **来源行（仅 Mode A/B）**：对平台链接或本地视频，文档顶部先附来源——平台视频用 `> **来源**：[原标题]（原链接）`，本地视频用 `> **来源**：本地视频路径`。方便跳转核对原文。
2. `# 标题` — derived from the video title, topic, or source name
3. Optional one-line 整理说明 only when useful（如"原始 ASR 转写已去噪，修正同音词：低粉→一份、小魔书店商→小红书电商"）
4. A small number of large `##` themes
5. Specific `###` subheadings under each theme
6. Cleaned original-style paragraphs under each subheading

Forbidden sections: `一句话总结`, `核心要点`, `启发`, `结论`, `重点摘要`, `其他有效观点`, `补充内容`, `杂项`.

### What to remove
- Timestamps, speaker labels, greetings, waiting-room chatter, screen-sharing talk
- Repeated audience checks, off-topic banter
- Filler words, stutters, duplicated phrases, sentence fragments
- Obvious live-room noise and ASR artifacts

### What to keep
- Original meaning, tone, key judgments
- Cases, examples, numbers, analogies
- The full argument chain
- Important original wording and signature phrases
- For short videos: hooks, punchlines, rhythm, transitions, call-to-action
- For podcasts: conversational flow, disagreements, topic transitions

### What NOT to do
- Do NOT add facts, external information, or interpretation
- Do NOT rewrite into a new article — it should still read like the speaker
- Do NOT bold every paragraph — only bold important judgments, strong quotes, and concrete principles
- Do NOT invent timestamps or speaker labels

### Heading rules
- Use concrete headings describing the actual content discussed
- Use a few large themes (typically 2–5 `##` sections), not dozens of fragments
- No garbage-bin headings

### ASR cleanup
- Fix obvious speech-recognition errors only with high confidence
- Standardize recurring product/tool names only when the intended name is clear
- Add punctuation and paragraph breaks naturally

---

## Delivery: Feishu Doc

**All purified transcripts are delivered as Feishu documents.** Do NOT dump the full transcript in the chat — only post the Feishu doc link and a brief one-line summary (title + word count).

Use the `lark-doc` skill to create a new Feishu doc with the purified Markdown content. The doc title should be the same as the `# 标题`.

In the user-facing reply:
1. Post only the Feishu doc URL (as a clickable link)
2. One line: "已交付飞书文档——《标题》，约 N 字"
3. If ASR cleanup was significant (homophone fixes, noise removal), mention briefly in the same line

> **改文档标题（常见后续操作）**：`lark-doc` 的 `docs +update` 只能改正文，**改不了文档标题**。改标题走 Drive 文件接口：
> ```bash
> lark-cli api PATCH /open-apis/drive/v1/files/{doc_id} \
>   --params '{"type":"docx"}' --data '{"new_title":"新标题"}'
> ```
> `doc_id` 即文档 token（URL 里 `docx/` 后的那段）。改完用 `lark-cli api GET /open-apis/docx/v1/documents/{doc_id}` 回查 `document.title` 确认。`docx/v1/documents` 的 PATCH 接口会报 `invalid param`，别走那条路。

---

## Quality Bar

Before finalizing, confirm:
- **来源行已附在文档顶部**（Mode A: 标题+原链接；Mode B: 本地路径）
- Source meaning and argument order are preserved
- Output is not a summary, checklist, or commentary
- Greetings, filler, repetition, timestamps, speaker labels, and fragments are removed
- Key judgments, examples, numbers, analogies, and important original phrases remain
- Headings are specific and limited to real themes
- Bold text highlights high-value content without over-marking
- Feishu doc has been created (or local fallback is clearly noted)
- **Chat reply** is one-liner only: doc link + title + word count, no full text dump
