# Feishu XHS Note Sync Template

Use this reference when the field contract or writeback behavior needs checking.

## Fields

Source field:

- `笔记信息`

Target fields:

- `笔记标题`
- `笔记内容`
- `封面链接`
- `点赞数`
- `收藏数`
- `评论数`
- `账号`

## Record Selection

- Only process records visible in the `view` from the provided Feishu Base URL.
- The URL must provide `base_token`, `table`, and `view`.
- Target fields must already exist.
- If any target field is already populated, skip the row.

## Xiaohongshu Data Mapping

- `title` -> `笔记标题`
- `desc` -> `笔记内容`
- `interactInfo.likedCount` -> `点赞数`
- `interactInfo.collectedCount` -> `收藏数`
- `interactInfo.commentCount` -> `评论数`
- `user.nickName` or `user.nickname` -> `账号`
- Desktop no-center-watermark cover URL when publicly exposed, otherwise image note first image or video cover -> `封面链接`

Unknown counts stay blank. Do not replace missing counts with `0`.
