import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from urllib.error import URLError

import feishu_xhs_note_sync as sync


def make_note_html(note_data):
    state = {
        "noteData": {
            "routeQuery": {"xsec_token": "test"},
            "data": {"noteData": note_data},
        }
    }
    return "<script>window.__INITIAL_STATE__=" + json.dumps(
        state, ensure_ascii=False
    ) + "</script>"


class UrlAndTemplateTests(unittest.TestCase):
    def test_parse_feishu_base_url_requires_base_table_and_view(self):
        ref = sync.parse_feishu_base_url(
            "https://yulu-tech.feishu.cn/base/base_token?table=tbl1&view=vew1"
        )

        self.assertEqual(ref.base_token, "base_token")
        self.assertEqual(ref.table_id, "tbl1")
        self.assertEqual(ref.view_id, "vew1")

    def test_parse_feishu_base_url_rejects_missing_view(self):
        with self.assertRaises(sync.ConfigError):
            sync.parse_feishu_base_url(
                "https://yulu-tech.feishu.cn/base/base_token?table=tbl1"
            )

    def test_uses_confirmed_template_fields(self):
        self.assertEqual(sync.SOURCE_FIELD, "笔记信息")
        self.assertEqual(
            sync.TARGET_FIELDS,
            (
                "笔记标题",
                "笔记内容",
                "封面链接",
                "点赞数",
                "收藏数",
                "评论数",
                "账号",
            ),
        )

    def test_extracts_first_xhs_url_without_changing_query(self):
        text = "笔记 http://xhslink.com/o/abc123?foo=1&bar=2 更多"

        self.assertEqual(
            sync.extract_note_url(text),
            "http://xhslink.com/o/abc123?foo=1&bar=2",
        )


class ParseNoteTests(unittest.TestCase):
    def base_note(self):
        return {
            "title": "标题",
            "desc": "正文",
            "type": "normal",
            "user": {"nickName": "账号"},
            "interactInfo": {
                "likedCount": "3,989",
                "collectedCount": "4,836",
                "commentCount": "132",
            },
            "imageList": [{"url": "http://image.example/first.jpg"}],
        }

    def test_parses_note_fields_and_first_image_cover(self):
        result = sync.parse_note_html(make_note_html(self.base_note()))

        self.assertEqual(result.title, "标题")
        self.assertEqual(result.content, "正文")
        self.assertEqual(result.cover_url, "http://image.example/first.jpg")
        self.assertEqual((result.likes, result.collects, result.comments), (3989, 4836, 132))
        self.assertEqual(result.account_nickname, "账号")

    def test_video_prefers_video_cover(self):
        note = self.base_note()
        note["type"] = "video"
        note["video"] = {"cover": {"url": "http://image.example/video.jpg"}}

        result = sync.parse_note_html(make_note_html(note))

        self.assertEqual(result.cover_url, "http://image.example/video.jpg")

    def test_missing_counts_stay_none(self):
        note = self.base_note()
        note["interactInfo"] = {}

        result = sync.parse_note_html(make_note_html(note))

        self.assertIsNone(result.likes)
        self.assertIsNone(result.collects)
        self.assertIsNone(result.comments)

    def test_parses_display_unit_counts(self):
        note = self.base_note()
        note["interactInfo"] = {
            "likedCount": "1.2万+",
            "collectedCount": "3k",
            "commentCount": "4千",
        }

        result = sync.parse_note_html(make_note_html(note))

        self.assertEqual((result.likes, result.collects, result.comments), (12000, 3000, 4000))

    def test_extracts_desktop_og_cover_without_center_watermark(self):
        html = (
            '<meta property="og:image" content="'
            'http://sns-webpic-qc.xhscdn.com/202608142017/hash/'
            '1040g008323q1mgmgn4304012i815i6ir9sgdrs0!nd_dft_wlteh_jpg_3">'
        )

        self.assertEqual(
            sync._desktop_cover_url(html),
            "http://sns-webpic-qc.xhscdn.com/202608142017/hash/"
            "1040g008323q1mgmgn4304012i815i6ir9sgdrs0!nd_dft_wlteh_jpg_3",
        )

    def test_extracts_desktop_dom_cover_fallback(self):
        html = (
            '<img src="https://sns-webpic-qc.xhscdn.com/202608142013/hash/'
            'oss-sg/notes/1040g3l0323bpj5kr084g5qgu9c63ej016l2ku1o'
            '!nd_dft_wgth_webp_3">'
        )

        self.assertIn("!nd_dft_wgth_webp_3", sync._desktop_cover_url(html))

    def test_collect_note_prefers_desktop_cover(self):
        desktop_html = (
            '<meta property="og:image" content="'
            'http://sns-webpic-qc.xhscdn.com/hash/image!nd_dft_wlteh_jpg_3">'
        )

        def fetch(url, user_agent=sync.MOBILE_USER_AGENT):
            if user_agent == sync.DESKTOP_USER_AGENT:
                return desktop_html
            return make_note_html(self.base_note())

        with patch.object(sync, "fetch_note_html", side_effect=fetch):
            result = sync.collect_note("https://www.xiaohongshu.com/explore/1")

        self.assertEqual(
            result.cover_url,
            "http://sns-webpic-qc.xhscdn.com/hash/image!nd_dft_wlteh_jpg_3",
        )


class CollectionTests(unittest.TestCase):
    def make_record(self, record_id, text="链接 http://xhslink.com/o/abc", **values):
        fields = {sync.SOURCE_FIELD: text}
        fields.update({name: None for name in sync.TARGET_FIELDS})
        fields.update(values)
        return sync.Record(record_id=record_id, fields=fields)

    def test_collect_skips_existing_target_and_builds_template_fields(self):
        records = [
            self.make_record("rec_skip", 评论数=1),
            self.make_record("rec_ok"),
        ]
        note = sync.NoteData("标题", "正文", 1, None, 3, "账号", "封面")

        result = sync.collect_records(records, collector=lambda _: note, sleep=lambda _: None)

        self.assertEqual(result.skipped, ["rec_skip"])
        self.assertEqual(result.successes[0].fields, {
            "笔记标题": "标题",
            "笔记内容": "正文",
            "封面链接": "封面",
            "点赞数": 1,
            "评论数": 3,
            "账号": "账号",
        })

    def test_collect_continues_after_one_record_fails(self):
        records = [self.make_record("rec_bad"), self.make_record("rec_good")]

        def collector(url):
            if collector.calls == 0:
                collector.calls += 1
                raise sync.ParseError("坏页面")
            return sync.NoteData("标题", "正文", 1, 2, 3, "账号", "封面")

        collector.calls = 0
        result = sync.collect_records(records, collector=collector, sleep=lambda _: None)

        self.assertEqual([item.record.record_id for item in result.successes], ["rec_good"])
        self.assertEqual(result.failures[0].record_id, "rec_bad")


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.body.encode("utf-8")


class FetchTests(unittest.TestCase):
    def test_fetch_uses_mobile_user_agent_and_retries(self):
        attempts = []

        def opener(request, timeout):
            attempts.append((request, timeout))
            if len(attempts) < 2:
                raise URLError("temporary")
            return FakeResponse("页面")

        result = sync.fetch_note_html(
            "http://xhslink.com/o/abc", opener=opener, sleep=lambda _: None
        )

        self.assertEqual(result, "页面")
        self.assertEqual(len(attempts), 2)
        self.assertIn("iPhone", attempts[0][0].get_header("User-agent"))


class LarkTests(unittest.TestCase):
    def setUp(self):
        self.ref = sync.BaseRef("base1", "tbl1", "vew1")

    def fake_completed(self, payload=None, returncode=0, stderr=""):
        class Completed:
            pass

        completed = Completed()
        completed.stdout = json.dumps(payload or {}, ensure_ascii=False)
        completed.stderr = stderr
        completed.returncode = returncode
        return completed

    def test_read_view_records_uses_url_ref_and_template_fields(self):
        calls = []
        payload = {
            "ok": True,
            "data": {
                "fields": [sync.SOURCE_FIELD, "笔记标题"],
                "data": [["分享", None]],
                "record_id_list": ["rec_1"],
                "has_more": False,
            },
        }

        def runner(args, **kwargs):
            calls.append(args)
            return self.fake_completed(payload)

        records = sync.read_view_records(self.ref, runner=runner)

        self.assertEqual(records[0].record_id, "rec_1")
        command = calls[0]
        self.assertIn("base1", command)
        self.assertIn("tbl1", command)
        self.assertIn("vew1", command)
        for field in (sync.SOURCE_FIELD,) + sync.TARGET_FIELDS:
            self.assertIn(field, command)

    def test_write_records_calls_batch_update_for_ref(self):
        calls = []
        collected = sync.CollectedRecord(
            sync.Record("rec_1", {}),
            "http://xhslink.com/o/a",
            {"笔记标题": "标题"},
        )

        def runner(args, **kwargs):
            calls.append(args)
            return self.fake_completed({"code": 0})

        sync.write_records(self.ref, [collected], runner=runner)

        command = calls[0]
        self.assertEqual(command[:3], ["lark-cli", "api", "POST"])
        self.assertIn("/apps/base1/tables/tbl1/records/batch_update", command[3])
        sent = json.loads(command[command.index("--data") + 1])
        self.assertEqual(sent["records"][0]["record_id"], "rec_1")


class MainTests(unittest.TestCase):
    def test_main_defaults_to_dry_run_and_does_not_write(self):
        ref = sync.BaseRef("base1", "tbl1", "vew1")
        record = sync.Record("rec_1", {sync.SOURCE_FIELD: "http://xhslink.com/o/a"})
        result = sync.CollectionResult([
            sync.CollectedRecord(record, "http://xhslink.com/o/a", {"笔记标题": "标题"})
        ], [], [])
        output = io.StringIO()

        with patch.object(sync, "parse_feishu_base_url", return_value=ref), \
             patch.object(sync, "read_view_records", return_value=[record]), \
             patch.object(sync, "collect_records", return_value=result), \
             patch.object(sync, "write_records") as write, \
             redirect_stdout(output):
            code = sync.main(["--base-url", "https://x/base/b?table=t&view=v"])

        self.assertEqual(code, 0)
        write.assert_not_called()
        self.assertIn("DRY RUN", output.getvalue())


if __name__ == "__main__":
    unittest.main()
