#!/usr/bin/env python3
"""Collect Xiaohongshu note data from a Feishu Base view and write it back."""

import argparse
import html as html_lib
import json
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


SOURCE_FIELD = "笔记信息"
TARGET_FIELDS = (
    "笔记标题",
    "笔记内容",
    "封面链接",
    "点赞数",
    "收藏数",
    "评论数",
    "账号",
)

NOTE_URL_PATTERN = re.compile(
    r"https?://(?:xhslink\.com|www\.xiaohongshu\.com)/[^\s\])]+"
)
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
    "AppleWebKit/605.1.15 Mobile/15E148 xhsdiscover/8.0"
)
DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT_SECONDS = 30
REQUEST_INTERVAL_SECONDS = 1


class ConfigError(ValueError):
    """The Feishu URL or field template is not usable."""


class ParseError(ValueError):
    """The Xiaohongshu page cannot be parsed."""


class LarkError(RuntimeError):
    """lark-cli returned an error."""


@dataclass(frozen=True)
class BaseRef:
    base_token: str
    table_id: str
    view_id: str


@dataclass(frozen=True)
class NoteData:
    title: str
    content: str
    likes: Optional[int]
    collects: Optional[int]
    comments: Optional[int]
    account_nickname: str
    cover_url: str


@dataclass(frozen=True)
class Record:
    record_id: str
    fields: Dict[str, object]


@dataclass(frozen=True)
class CollectedRecord:
    record: Record
    source_url: str
    fields: Dict[str, object]


@dataclass(frozen=True)
class Failure:
    record_id: str
    reason: str


@dataclass
class CollectionResult:
    successes: List[CollectedRecord]
    skipped: List[str]
    failures: List[Failure]


def parse_feishu_base_url(url: str) -> BaseRef:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    try:
        base_index = parts.index("base")
        base_token = parts[base_index + 1]
    except (ValueError, IndexError) as exc:
        raise ConfigError("飞书链接缺少 base token") from exc

    query = parse_qs(parsed.query)
    table_id = (query.get("table") or [""])[0]
    view_id = (query.get("view") or [""])[0]
    if not table_id or not view_id:
        raise ConfigError("飞书链接必须包含 table 和 view 参数")
    return BaseRef(base_token=base_token, table_id=table_id, view_id=view_id)


def extract_note_url(text: str) -> Optional[str]:
    match = NOTE_URL_PATTERN.search(text or "")
    return match.group(0) if match else None


def has_existing_target(fields: Dict[str, object]) -> bool:
    return any(fields.get(name) not in (None, "") for name in TARGET_FIELDS)


def _extract_note_store(html: str) -> Dict[str, object]:
    marker = '"noteData":'
    decoder = json.JSONDecoder()
    start = 0
    while True:
        marker_index = html.find(marker, start)
        if marker_index < 0:
            break
        object_start = marker_index + len(marker)
        while object_start < len(html) and html[object_start].isspace():
            object_start += 1
        try:
            value, _ = decoder.raw_decode(html[object_start:])
        except json.JSONDecodeError:
            start = object_start
            continue
        if isinstance(value, dict) and "routeQuery" in value and "data" in value:
            return value
        start = object_start
    raise ParseError("页面中没有可用的 noteData")


def _optional_int(value: object) -> Optional[int]:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        normalized = value.strip().replace(",", "").replace("+", "")
        match = re.fullmatch(r"(\d+(?:\.\d+)?)([万wW千kK]?)", normalized)
        if not match:
            raise ParseError("互动数不是有效整数")
        number = float(match.group(1))
        unit = match.group(2)
        multiplier = 1
        if unit in ("万", "w", "W"):
            multiplier = 10000
        elif unit in ("千", "k", "K"):
            multiplier = 1000
        return int(number * multiplier)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ParseError("互动数不是有效整数") from exc


def _video_cover(video: object) -> Optional[str]:
    if not isinstance(video, dict):
        return None
    cover = video.get("cover")
    if isinstance(cover, str) and cover:
        return cover
    if isinstance(cover, dict):
        for key in ("url", "masterUrl", "defaultUrl"):
            value = cover.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _first_image_url(note: Dict[str, object]) -> str:
    image_list = note.get("imageList")
    if not isinstance(image_list, list) or not image_list:
        return ""
    first = image_list[0]
    if not isinstance(first, dict):
        return ""
    url = first.get("url")
    if isinstance(url, str) and url:
        return url
    info_list = first.get("infoList")
    if isinstance(info_list, list):
        for item in info_list:
            if isinstance(item, dict) and item.get("imageScene") == "H5_DTL":
                detail_url = item.get("url")
                if isinstance(detail_url, str):
                    return detail_url
    return ""


def _desktop_cover_url(html: str) -> str:
    """Extract the desktop detail page cover, which is usually not center-watermarked."""
    meta_pattern = re.compile(
        r'<meta\s+[^>]*(?:property|name)=["\']og:image["\'][^>]*>',
        re.IGNORECASE,
    )
    content_pattern = re.compile(r'\bcontent=(["\'])(.*?)\1', re.IGNORECASE)
    for tag in meta_pattern.findall(html):
        match = content_pattern.search(tag)
        if not match:
            continue
        url = html_lib.unescape(match.group(2))
        if "sns-webpic" in url and "!nd_" in url:
            return url

    img_pattern = re.compile(
        r'<img\s+[^>]*\bsrc=(["\'])(https?://[^"\']*sns-webpic[^"\']*!nd_[^"\']*)\1',
        re.IGNORECASE,
    )
    match = img_pattern.search(html)
    return html_lib.unescape(match.group(2)) if match else ""


def parse_note_html(html: str) -> NoteData:
    store = _extract_note_store(html)
    data = store.get("data")
    note = data.get("noteData") if isinstance(data, dict) else None
    if not isinstance(note, dict):
        raise ParseError("noteData 结构缺失")

    interaction = note.get("interactInfo")
    if not isinstance(interaction, dict):
        interaction = {}
    user = note.get("user")
    if not isinstance(user, dict):
        user = {}

    cover_url = ""
    if note.get("type") == "video":
        cover_url = _video_cover(note.get("video")) or ""
    if not cover_url:
        cover_url = _first_image_url(note)

    return NoteData(
        title=str(note.get("title") or ""),
        content=str(note.get("desc") or ""),
        likes=_optional_int(interaction.get("likedCount")),
        collects=_optional_int(interaction.get("collectedCount")),
        comments=_optional_int(interaction.get("commentCount")),
        account_nickname=str(user.get("nickName") or user.get("nickname") or ""),
        cover_url=cover_url,
    )


def fetch_note_html(
    url: str,
    opener: Callable[..., object] = urlopen,
    sleep: Callable[[float], None] = time.sleep,
    user_agent: str = MOBILE_USER_AGENT,
) -> str:
    request = Request(url, headers={"User-Agent": user_agent})
    last_error = None
    for attempt in range(3):
        try:
            with opener(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                sleep(attempt + 1)
    raise last_error if last_error else RuntimeError("请求未执行")


def collect_note(url: str) -> NoteData:
    mobile_html = fetch_note_html(url)
    note = parse_note_html(mobile_html)
    try:
        desktop_cover = _desktop_cover_url(
            fetch_note_html(url, user_agent=DESKTOP_USER_AGENT)
        )
    except Exception:
        desktop_cover = ""
    if not desktop_cover:
        return note
    return NoteData(
        title=note.title,
        content=note.content,
        likes=note.likes,
        collects=note.collects,
        comments=note.comments,
        account_nickname=note.account_nickname,
        cover_url=desktop_cover,
    )



def _note_fields(note: NoteData) -> Dict[str, object]:
    fields = {
        "笔记标题": note.title,
        "笔记内容": note.content,
        "封面链接": note.cover_url,
        "点赞数": note.likes,
        "收藏数": note.collects,
        "评论数": note.comments,
        "账号": note.account_nickname,
    }
    return {name: value for name, value in fields.items() if value is not None}


def collect_records(
    records: List[Record],
    collector: Callable[[str], NoteData] = collect_note,
    sleep: Callable[[float], None] = time.sleep,
) -> CollectionResult:
    result = CollectionResult(successes=[], skipped=[], failures=[])
    attempted = 0
    for record in records:
        if has_existing_target(record.fields):
            result.skipped.append(record.record_id)
            continue
        url = extract_note_url(str(record.fields.get(SOURCE_FIELD) or ""))
        if not url:
            result.failures.append(Failure(record.record_id, "笔记信息中没有小红书链接"))
            continue
        if attempted:
            sleep(REQUEST_INTERVAL_SECONDS)
        attempted += 1
        try:
            note = collector(url)
        except Exception as exc:
            result.failures.append(Failure(record.record_id, str(exc)))
            continue
        result.successes.append(
            CollectedRecord(record=record, source_url=url, fields=_note_fields(note))
        )
    return result


def run_lark(
    args: List[str],
    runner: Callable[..., object] = subprocess.run,
) -> Dict[str, object]:
    completed = runner(
        ["lark-cli"] + args,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise LarkError((completed.stderr or "lark-cli 执行失败").strip())
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise LarkError("lark-cli 返回了无效 JSON") from exc
    if payload.get("ok") is False:
        raise LarkError(str(payload.get("error") or payload.get("msg") or "Lark 失败"))
    if "code" in payload and payload.get("code") != 0:
        raise LarkError(str(payload.get("msg") or "Lark API 调用失败"))
    return payload


def _records_from_envelope(payload: Dict[str, object]) -> List[Record]:
    envelope = payload.get("data")
    if not isinstance(envelope, dict):
        raise LarkError("Lark 返回缺少 data")
    fields = envelope.get("fields")
    rows = envelope.get("data")
    record_ids = envelope.get("record_id_list")
    if not isinstance(fields, list) or not isinstance(rows, list) or not isinstance(record_ids, list):
        raise LarkError("Lark 记录结构不完整")
    if len(rows) != len(record_ids):
        raise LarkError("Lark 记录 ID 与数据行数量不一致")
    records = []
    for record_id, row in zip(record_ids, rows):
        if not isinstance(row, list):
            raise LarkError("Lark 数据行格式错误")
        records.append(Record(str(record_id), dict(zip(fields, row))))
    return records


def read_view_records(
    ref: BaseRef,
    runner: Callable[..., object] = subprocess.run,
) -> List[Record]:
    base_args = [
        "base", "+record-list",
        "--base-token", ref.base_token,
        "--table-id", ref.table_id,
        "--view-id", ref.view_id,
        "--limit", "200",
        "--format", "json",
    ]
    for field in (SOURCE_FIELD,) + TARGET_FIELDS:
        base_args.extend(["--field-id", field])

    records = []
    offset = 0
    while True:
        payload = run_lark(base_args + ["--offset", str(offset)], runner=runner)
        page = _records_from_envelope(payload)
        records.extend(page)
        envelope = payload.get("data")
        has_more = isinstance(envelope, dict) and envelope.get("has_more") is True
        if not has_more:
            return records
        if not page:
            raise LarkError("Lark 分页返回空页，无法继续")
        offset += len(page)


def build_batch_payload(successes: List[CollectedRecord]) -> Dict[str, object]:
    return {
        "records": [
            {"record_id": item.record.record_id, "fields": item.fields}
            for item in successes
        ]
    }


def write_records(
    ref: BaseRef,
    successes: List[CollectedRecord],
    runner: Callable[..., object] = subprocess.run,
) -> None:
    if not successes:
        return
    path = (
        f"/open-apis/bitable/v1/apps/{ref.base_token}"
        f"/tables/{ref.table_id}/records/batch_update"
    )
    run_lark(
        ["api", "POST", path, "--data", json.dumps(build_batch_payload(successes), ensure_ascii=False)],
        runner=runner,
    )


def verify_records(
    ref: BaseRef,
    successes: List[CollectedRecord],
    runner: Callable[..., object] = subprocess.run,
) -> List[str]:
    if not successes:
        return []
    args = [
        "base", "+record-get",
        "--base-token", ref.base_token,
        "--table-id", ref.table_id,
        "--format", "json",
    ]
    for item in successes:
        args.extend(["--record-id", item.record.record_id])
    for field in TARGET_FIELDS:
        args.extend(["--field-id", field])
    actual_records = _records_from_envelope(run_lark(args, runner=runner))
    actual_by_id = {record.record_id: record.fields for record in actual_records}

    mismatches = []
    for item in successes:
        actual = actual_by_id.get(item.record.record_id)
        if actual is None:
            mismatches.append(item.record.record_id + ": 写回后找不到记录")
            continue
        for field, expected in item.fields.items():
            actual_value = actual.get(field)
            both_empty = expected in (None, "") and actual_value in (None, "")
            if not both_empty and actual_value != expected:
                mismatches.append(
                    "{}: {} 预期 {!r}，实际 {!r}".format(
                        item.record.record_id, field, expected, actual_value
                    )
                )
    return mismatches


def print_dry_run(result: CollectionResult) -> None:
    print("DRY RUN：以下内容不会写回飞书")
    for item in result.successes:
        print(json.dumps({
            "record_id": item.record.record_id,
            "source_url": item.source_url,
            "fields": item.fields,
        }, ensure_ascii=False))


def print_summary(result: CollectionResult) -> None:
    print(
        "处理完成：成功 {}，跳过 {}，失败 {}".format(
            len(result.successes), len(result.skipped), len(result.failures)
        )
    )
    for failure in result.failures:
        print("失败 {}：{}".format(failure.record_id, failure.reason))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="从飞书多维表格视图采集小红书笔记数据并写回同一行"
    )
    parser.add_argument("--base-url", required=True, help="包含 table 和 view 的飞书多维表格链接")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只预览，不写回；默认行为")
    mode.add_argument("--write", action="store_true", help="写回飞书并验证")
    args = parser.parse_args(argv)

    try:
        ref = parse_feishu_base_url(args.base_url)
        records = read_view_records(ref)
        if not records:
            print_summary(CollectionResult([], [], []))
            return 0
        result = collect_records(records)
        if not args.write:
            print_dry_run(result)
            print_summary(result)
            return 1 if result.failures else 0

        write_records(ref, result.successes)
        mismatches = verify_records(ref, result.successes)
        for mismatch in mismatches:
            print("验证失败：" + mismatch)
        print_summary(result)
        return 1 if result.failures or mismatches else 0
    except (ConfigError, LarkError, OSError, ParseError) as exc:
        print("执行失败：" + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
