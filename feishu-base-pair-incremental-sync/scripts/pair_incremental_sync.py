#!/usr/bin/env python3
"""Append-only incremental sync for direct Feishu Base source/target pairs."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

LINK_FIELDS = ["公告链接", "公告原链接", "原文链接", "来源链接", "投递链接", "链接", "网址", "URL", "url"]
TITLE_FIELDS = [
    "单位名称",
    "招聘单位",
    "公司",
    "公司名称",
    "招聘公告标题",
    "公告标题",
    "标题",
    "岗位",
    "招聘岗位",
]
UNSUPPORTED_FIELD_TYPES = {"attachment", "formula", "lookup", "duplex_link", "user"}


@dataclass
class BaseRef:
    base_token: str
    table_id: str
    view_id: str


@dataclass
class SyncTask:
    name: str
    source: BaseRef
    target: BaseRef
    checkpoint_field: str


@dataclass
class SyncResult:
    name: str
    status: str
    planned: int = 0
    written: int = 0
    skipped: int = 0
    target_latest_before: Optional[dt.date] = None
    source_latest: Optional[dt.date] = None
    target_latest_after: Optional[dt.date] = None
    message: str = ""


@dataclass
class SyncPlan:
    fields: List[str]
    rows: List[List[Any]]
    result: SyncResult
    target_fields: Dict[str, Dict[str, Any]]


def parse_base_url(url: str) -> BaseRef:
    parsed = urlparse(url.strip())
    match = re.search(r"/base/([^/?#]+)", parsed.path)
    if not match:
        raise ValueError("Base URL missing /base/<base-token>")
    query = parse_qs(parsed.query)
    table_id = (query.get("table") or [""])[0]
    view_id = (query.get("view") or [""])[0]
    if not table_id:
        raise ValueError("Base URL missing table query parameter")
    if not view_id:
        raise ValueError("Base URL missing view query parameter")
    return BaseRef(base_token=match.group(1), table_id=table_id, view_id=view_id)


def load_config(path: str) -> List[SyncTask]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    tasks_data = data.get("tasks")
    if not isinstance(tasks_data, list) or not tasks_data:
        raise ValueError("config must contain a non-empty tasks array")

    required = ["name", "source_url", "target_url", "checkpoint_field"]
    tasks: List[SyncTask] = []
    for index, item in enumerate(tasks_data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"task {index} must be an object")
        for field in required:
            if not str(item.get(field, "")).strip():
                raise ValueError(f"task {index} missing required field: {field}")
        tasks.append(
            SyncTask(
                name=str(item["name"]).strip(),
                source=parse_base_url(str(item["source_url"])),
                target=parse_base_url(str(item["target_url"])),
                checkpoint_field=str(item["checkpoint_field"]).strip(),
            )
        )
    return tasks


def parse_date(value: Any, today: dt.date) -> Optional[dt.date]:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, (int, float)):
        number = int(value)
        if number > 10_000_000_000:
            number //= 1000
        try:
            return dt.datetime.fromtimestamp(number).date()
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(value, list):
        for item in value:
            parsed = parse_date(item, today)
            if parsed:
                return parsed
        return None

    text = str(value).strip()
    if not text:
        return None

    match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if match:
        try:
            return dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None

    match = re.search(r"(\d{1,2})月(\d{1,2})", text)
    if match:
        try:
            return dt.date(today.year, int(match.group(1)), int(match.group(2)))
        except ValueError:
            return None

    return None


def value_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "｜".join(part for item in value if (part := value_text(item)))
    if isinstance(value, dict):
        for key in ("text", "name", "url", "link"):
            if key in value:
                return value_text(value[key])
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def normalize_link(value: Any) -> str:
    text = value_text(value)
    match = re.search(r"\]\(([^)]+)\)", text)
    if match:
        text = match.group(1)
    return text.strip().lower().rstrip("/")


def record_key(row: Dict[str, Any], checkpoint_field: str, today: dt.date) -> str:
    for field in LINK_FIELDS:
        if field in row:
            link = normalize_link(row.get(field))
            if link:
                return "link:" + link

    parts: List[str] = []
    for field in TITLE_FIELDS:
        if field in row:
            text = value_text(row.get(field))
            if text:
                parts.append(text)
    parsed = parse_date(row.get(checkpoint_field), today)
    if parsed:
        parts.append(str(parsed))
    return "combo:" + "|".join(parts).lower()


def max_date(records: List[Tuple[str, Dict[str, Any]]], checkpoint_field: str, today: dt.date) -> Optional[dt.date]:
    dates = [parse_date(row.get(checkpoint_field), today) for _, row in records]
    dates = [date for date in dates if date and date <= today]
    return max(dates) if dates else None


def coerce_cell(value: Any, target_field: Dict[str, Any]) -> Any:
    field_type = str(target_field.get("type", ""))
    if field_type in UNSUPPORTED_FIELD_TYPES:
        return None

    options = {option.get("name") for option in target_field.get("options") or [] if isinstance(option, dict)}
    multiple = bool(target_field.get("multiple"))

    if field_type in {"text", "url", "phone", "email"}:
        return value_text(value) if isinstance(value, (list, dict)) else value

    if field_type in {"number", "currency", "percent"}:
        if value in (None, ""):
            return None
        try:
            number = float(str(value).replace(",", ""))
            return int(number) if number.is_integer() else number
        except (TypeError, ValueError):
            return None

    if field_type in {"datetime", "date"}:
        return value

    if field_type in {"select", "single_select", "multi_select"}:
        raw_values = value if isinstance(value, list) else ([] if value in (None, "") else [value])
        normalized = [value_text(item) for item in raw_values if value_text(item)]
        if options:
            normalized = [item for item in normalized if item in options]
        if multiple or field_type == "multi_select":
            return normalized
        return normalized[0] if normalized else None

    return value


def build_plan_from_records(
    task: SyncTask,
    source_fields: Dict[str, Dict[str, Any]],
    target_fields: Dict[str, Dict[str, Any]],
    source_records: List[Tuple[str, Dict[str, Any]]],
    target_records: List[Tuple[str, Dict[str, Any]]],
    today: dt.date,
) -> SyncPlan:
    if task.checkpoint_field not in source_fields or task.checkpoint_field not in target_fields:
        return SyncPlan(
            fields=[],
            rows=[],
            target_fields=target_fields,
            result=SyncResult(task.name, "skip", message=f"缺少核对字段「{task.checkpoint_field}」"),
        )

    common_fields = [name for name in target_fields if name in source_fields]
    target_latest = max_date(target_records, task.checkpoint_field, today)
    source_latest = max_date(source_records, task.checkpoint_field, today)
    target_keys = {
        key
        for _, row in target_records
        for key in [record_key(row, task.checkpoint_field, today)]
        if key != "combo:"
    }

    rows: List[List[Any]] = []
    seen: set = set()
    skipped = 0
    for _, row in source_records:
        parsed = parse_date(row.get(task.checkpoint_field), today)
        if not parsed or parsed > today:
            skipped += 1
            continue
        if target_latest and parsed <= target_latest:
            continue
        key = record_key(row, task.checkpoint_field, today)
        if key == "combo:" or key in target_keys or key in seen:
            skipped += 1
            continue
        seen.add(key)
        rows.append([coerce_cell(row.get(field), target_fields[field]) for field in common_fields])

    status = "planned" if rows else "ok"
    message = "已追平" if not rows else "可同步"
    return SyncPlan(
        fields=common_fields,
        rows=rows,
        target_fields=target_fields,
        result=SyncResult(
            name=task.name,
            status=status,
            planned=len(rows),
            skipped=skipped,
            target_latest_before=target_latest,
            source_latest=source_latest,
            message=message,
        ),
    )


def run_lark(args: List[str], retries: int = 3) -> Any:
    command = ["lark-cli", *args]
    for attempt in range(retries):
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0:
            try:
                return json.loads(proc.stdout)
            except json.JSONDecodeError:
                return proc.stdout
        if attempt < retries - 1:
            time.sleep(1.5 * (attempt + 1))
            continue
        raise RuntimeError(
            "Command failed: "
            + " ".join(command)
            + "\nSTDERR: "
            + proc.stderr[:2000]
            + "\nSTDOUT: "
            + proc.stdout[:2000]
        )
    raise AssertionError("unreachable")


def field_map(base_token: str, table_id: str) -> Dict[str, Dict[str, Any]]:
    data = run_lark(["base", "+field-list", "--base-token", base_token, "--table-id", table_id, "--limit", "100"])
    if not isinstance(data, dict):
        raise RuntimeError("field-list did not return JSON")
    return {field["name"]: field for field in data["data"]["fields"]}


def list_records(base_token: str, table_id: str, view_id: str, fields: Optional[List[str]]) -> List[Tuple[str, Dict[str, Any]]]:
    offset = 0
    records: List[Tuple[str, Dict[str, Any]]] = []
    while True:
        args = [
            "base",
            "+record-list",
            "--base-token",
            base_token,
            "--table-id",
            table_id,
            "--view-id",
            view_id,
            "--limit",
            "200",
            "--offset",
            str(offset),
            "--format",
            "json",
        ]
        if fields:
            for field in fields:
                args.extend(["--field-id", field])
        data = run_lark(args)
        if not isinstance(data, dict):
            raise RuntimeError("record-list did not return JSON")
        payload = data["data"]
        rows = payload.get("data") or []
        ids = payload.get("record_id_list") or []
        names = payload.get("fields") or []
        for record_id, row in zip(ids, rows):
            records.append((record_id, dict(zip(names, row))))
        if not payload.get("has_more"):
            break
        offset += len(rows) or 200
    return records


def build_live_plan(task: SyncTask, today: dt.date) -> SyncPlan:
    source_fields = field_map(task.source.base_token, task.source.table_id)
    target_fields = field_map(task.target.base_token, task.target.table_id)
    if task.checkpoint_field not in source_fields or task.checkpoint_field not in target_fields:
        return build_plan_from_records(task, source_fields, target_fields, [], [], today)
    common_fields = [name for name in target_fields if name in source_fields]
    source_records = list_records(task.source.base_token, task.source.table_id, task.source.view_id, common_fields)
    target_records = list_records(task.target.base_token, task.target.table_id, task.target.view_id, common_fields)
    return build_plan_from_records(task, source_fields, target_fields, source_records, target_records, today)


def write_rows(task: SyncTask, fields: List[str], rows: List[List[Any]], batch_size: int) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        payload = {"fields": fields, "rows": batch}
        run_lark(
            [
                "base",
                "+record-batch-create",
                "--base-token",
                task.target.base_token,
                "--table-id",
                task.target.table_id,
                "--json",
                json.dumps(payload, ensure_ascii=False),
            ]
        )
        written += len(batch)
        time.sleep(0.4)
    return written


def sort_view(task: SyncTask, target_fields: Dict[str, Dict[str, Any]]) -> str:
    field = target_fields.get(task.checkpoint_field)
    if not field:
        return "missing checkpoint field"
    for field_ref in (field.get("id"), task.checkpoint_field):
        if not field_ref:
            continue
        payload = {"sort_config": [{"field": field_ref, "desc": True}]}
        try:
            run_lark(
                [
                    "base",
                    "+view-set-sort",
                    "--base-token",
                    task.target.base_token,
                    "--table-id",
                    task.target.table_id,
                    "--view-id",
                    task.target.view_id,
                    "--json",
                    json.dumps(payload, ensure_ascii=False),
                ]
            )
            return "sorted"
        except Exception as exc:
            last_error = str(exc).splitlines()[0]
    return "sort failed: " + last_error


def verify_task(task: SyncTask, today: dt.date) -> Tuple[Optional[dt.date], Optional[dt.date]]:
    source_records = list_records(task.source.base_token, task.source.table_id, task.source.view_id, [task.checkpoint_field])
    target_records = list_records(task.target.base_token, task.target.table_id, task.target.view_id, [task.checkpoint_field])
    return max_date(target_records, task.checkpoint_field, today), max_date(source_records, task.checkpoint_field, today)


def date_or_dash(value: Optional[dt.date]) -> str:
    return value.isoformat() if value else "-"


def result_to_jsonable(result: SyncResult) -> Dict[str, Any]:
    data = asdict(result)
    for key in ("target_latest_before", "source_latest", "target_latest_after"):
        if data[key] is not None:
            data[key] = data[key].isoformat()
    return data


def write_output_json(path: str, results: List[SyncResult], executed: bool) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(
            {"executed": executed, "results": [result_to_jsonable(result) for result in results]},
            fh,
            ensure_ascii=False,
            indent=2,
        )


def print_results(results: List[SyncResult], executed: bool) -> None:
    if executed:
        total = sum(result.written for result in results)
        print(f"同步完成：已追加 {total} 条。")
        print("| 数据名称 | 追加条数 | 新表原最新日期 | 新表现最新日期 | 原表最新日期 | 复查结果 |")
        print("|---|---:|---:|---:|---:|---|")
        for result in results:
            print(
                f"| {result.name} | {result.written} | {date_or_dash(result.target_latest_before)} | "
                f"{date_or_dash(result.target_latest_after)} | {date_or_dash(result.source_latest)} | {result.message or result.status} |"
            )
    else:
        total = sum(result.planned for result in results)
        print(f"预检结果：预计追加 {total} 条。")
        print("| 数据名称 | 新表最新日期 | 原表最新日期 | 待追加条数 | 跳过条数 | 状态 |")
        print("|---|---:|---:|---:|---:|---|")
        for result in results:
            print(
                f"| {result.name} | {date_or_dash(result.target_latest_before)} | {date_or_dash(result.source_latest)} | "
                f"{result.planned} | {result.skipped} | {result.message or result.status} |"
            )
        print("\n未写入任何数据。请确认是否执行写入；确认后使用 --execute。")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Incrementally sync direct Feishu Base source/target table pairs.")
    parser.add_argument("--config", required=True, help="JSON config containing tasks with name/source_url/target_url/checkpoint_field")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview only. This is the default when --execute is absent.")
    mode.add_argument("--execute", action="store_true", help="Append planned rows to target tables.")
    parser.add_argument("--today", default=dt.date.today().isoformat(), help="Date boundary, default: local today")
    parser.add_argument("--batch-size", type=int, default=50, help="Rows per write batch")
    parser.add_argument("--no-sort", action="store_true", help="Do not set target view sort after writing")
    parser.add_argument("--output-json", help="Write machine-readable result JSON to this path")
    parser.add_argument("--verbose", action="store_true", help="Print detailed errors")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    today = dt.date.fromisoformat(args.today)
    tasks = load_config(args.config)
    executed = bool(args.execute)
    results: List[SyncResult] = []

    for task in tasks:
        try:
            plan = build_live_plan(task, today)
            result = plan.result
            if executed and plan.rows:
                result.written = write_rows(task, plan.fields, plan.rows, args.batch_size)
                if not args.no_sort:
                    sort_status = sort_view(task, plan.target_fields)
                    if sort_status != "sorted":
                        result.message = f"写入成功，排序失败：{sort_status}"
                after, source_latest = verify_task(task, today)
                result.target_latest_after = after
                result.source_latest = source_latest
                if after == source_latest:
                    result.status = "ok"
                    if not result.message:
                        result.message = "已追平"
                else:
                    result.status = "check"
                    if not result.message:
                        result.message = "写入后未追平，请人工复查"
            elif executed:
                result.written = 0
                result.status = "ok" if result.status != "skip" else result.status
                after, source_latest = verify_task(task, today) if result.status != "skip" else (None, result.source_latest)
                result.target_latest_after = after
                result.source_latest = source_latest
                if not result.message:
                    result.message = "无需追加"
            results.append(result)
        except Exception as exc:
            message = str(exc) if args.verbose else str(exc).splitlines()[0]
            results.append(SyncResult(task.name, "error", message=message))

    print_results(results, executed)
    if args.output_json:
        write_output_json(args.output_json, results, executed)
    return 1 if any(result.status == "error" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
