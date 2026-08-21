#!/usr/bin/env python3
"""Mode B robust batch ASR pipeline for 小红书抖音视频文案提纯 skill.

Extract audio -> OSS (24h signed URL) -> Bailian Paraformer-v2 -> raw transcript.

Hardened lessons (learned from a 71-video batch that failed twice):
- oss2.Bucket does NOT accept read_timeout kwarg; set bucket.timeout after init.
- OSS default 60s timeout is too short on slow networks -> bump to 900 + retries.
- Flat folders with (1) / ( chuhai5.net ) duplicate copies must be deduped.
- Sort by numeric N.NN so merged doc keeps natural chapter order (10.x after 9.x).
- Per-video try/except so one failure does not kill the whole batch.

Usage:
  XHS_SOURCE_DIR="/path/to/videos" \
  XHS_WORK_DIR="/tmp/xhs3" \
  OSS_ACCESS_KEY_ID=... OSS_ACCESS_KEY_SECRET=... OSS_BUCKET_NAME=... OSS_ENDPOINT=... \
  DASHSCOPE_API_KEY=... \
  python batch_asr_pipeline.py [rebuild]

Outputs:
  <WORK>/raw/<NN>.txt + <NN>.json   (raw transcripts)
  <WORK>/manifest.json              (idx -> path/title/chapter/tag)
  <WORK>/audio/<NN>.mp3             (temp audio, safe to delete)
"""
import os, re, sys, json, glob, time, logging

BASE = os.environ.get("XHS_SOURCE_DIR", "")
WORK = os.environ.get("XHS_WORK_DIR", "/tmp/xhs_asr")
AUDIO_DIR = os.path.join(WORK, "audio")
RAW_DIR = os.path.join(WORK, "raw")
MANIFEST = os.path.join(WORK, "manifest.json")
LOG = os.path.join(WORK, "pipeline.log")
OSS_PREFIX = os.environ.get("XHS_OSS_PREFIX", "transcripts/xhs_batch")

os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

logging.basicConfig(filename=LOG, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pipeline")

if not BASE:
    sys.exit("XHS_SOURCE_DIR env var required")

FF = subprocess_check = subprocess.check_output if False else None
import subprocess
FF = subprocess.check_output(
    ["/Users/huangdalu/.workbuddy/binaries/python/envs/default/bin/python",
     "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"]
).decode().strip()

import oss2
auth = oss2.Auth(os.environ["OSS_ACCESS_KEY_ID"], os.environ["OSS_ACCESS_KEY_SECRET"])
bucket = oss2.Bucket(auth, os.environ["OSS_ENDPOINT"], os.environ["OSS_BUCKET_NAME"],
                     connect_timeout=120)
bucket.timeout = 900  # also extends read timeout (oss2 uses a single timeout value)

import dashscope
from dashscope.audio.asr import Transcription
dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
_http = requests.Session()
_retry = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
_http.mount("https://", HTTPAdapter(max_retries=_retry))
_http.mount("http://", HTTPAdapter(max_retries=_retry))


def _retry_call(func, *args, attempts=3, **kwargs):
    last = None
    for i in range(attempts):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last = e
            log.warning("attempt %d/%d failed: %s", i + 1, attempts, e)
            time.sleep(5 * (i + 1))
    raise last


def base_name(path: str) -> str:
    n = os.path.basename(path).replace("(1)", "").replace("( chuhai5.net )", "").replace(" ", "")
    return n[:-4] if n.endswith(".mp4") else n


def derive_meta(path: str):
    name = os.path.basename(path).replace("(1)", "").replace("( chuhai5.net )", "")
    m = re.match(r"^(\d+)\.(\d+)-【(.+?)】(.*)$", name)
    if m:
        tag = "【" + m.group(3) + "】"
        desc = m.group(4).replace(".mp4", "").strip()
        return int(m.group(1)), int(m.group(2)), tag, (f"{tag}{desc}" if desc else tag)
    return 0, 0, "【未分类】", name.replace(".mp4", "")


def build_manifest():
    vids = glob.glob(BASE + "/*.mp4")
    seen = {}; uniq = []
    for v in vids:
        b = base_name(v)
        if b in seen:
            log.info("dedupe skip %s", os.path.basename(v)); continue
        seen[b] = v; uniq.append(v)
    uniq.sort(key=lambda v: (derive_meta(v)[0], derive_meta(v)[1]))
    man = []
    for i, v in enumerate(uniq, 1):
        c, s, tag, title = derive_meta(v)
        man.append({"idx": f"{i:02d}", "num": f"{c}.{s:02d}", "chapter": c,
                    "tag": tag, "title": title, "path": v})
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    log.info("manifest built: %d unique (from %d files)", len(man), len(vids))
    return man


def extract_audio(video_path, out_mp3):
    if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 0:
        return True
    r = subprocess.run([FF, "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000",
                        "-b:a", "64k", out_mp3], capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        log.error("ffmpeg failed %s: %s", video_path, r.stderr[-500:]); return False
    return True


def upload_and_transcribe(mp3_path, idx):
    obj = f"{OSS_PREFIX}_{idx}.mp3"
    _retry_call(lambda: bucket.put_object_from_file(obj, mp3_path), attempts=3)
    url = bucket.sign_url("GET", obj, 24 * 3600)
    task = _retry_call(lambda: Transcription.async_call(
        model="paraformer-v2", file_urls=[url], language_hints=["zh", "en"]), attempts=3)
    result = _retry_call(lambda: Transcription.wait(task=task.output.task_id, timeout=3600), attempts=3)
    if result.status_code != 200:
        log.error("asr failed %s: %s", idx, result.message); return None
    res_url = result.output["results"][0]["transcription_url"]
    asr = _http.get(res_url, timeout=120).json()
    text = asr["transcripts"][0]["text"]
    sentences = asr["transcripts"][0].get("sentences", [])
    log.info("asr done %s chars=%d", idx, len(text))
    return text, sentences


def main():
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "rebuild" or not os.path.exists(MANIFEST):
        man = build_manifest()
    else:
        man = json.load(open(MANIFEST, encoding="utf-8"))
    done = 0; failed = []
    for item in man:
        idx = item["idx"]
        rt = os.path.join(RAW_DIR, f"{idx}.txt")
        if os.path.exists(rt) and os.path.getsize(rt) > 0:
            done += 1; continue
        try:
            mp3 = os.path.join(AUDIO_DIR, f"{idx}.mp3")
            if not extract_audio(item["path"], mp3):
                failed.append(idx); continue
            res = upload_and_transcribe(mp3, idx)
            if res is None:
                failed.append(idx); continue
            text, sentences = res
            open(rt, "w", encoding="utf-8").write(text)
            open(os.path.join(RAW_DIR, f"{idx}.json"), "w", encoding="utf-8").write(
                json.dumps(sentences, ensure_ascii=False))
            done += 1
            log.info("saved %s (%d/%d)", idx, done, len(man))
        except Exception as e:
            log.error("FATAL %s: %s", idx, e); failed.append(idx)
    log.info("PIPELINE COMPLETE %d/%d failed=%s", done, len(man), failed)


if __name__ == "__main__":
    main()
