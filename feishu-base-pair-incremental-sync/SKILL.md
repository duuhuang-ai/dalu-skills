---
name: feishu-base-pair-incremental-sync
description: Use when the user provides one or more Feishu/Lark Base 原数据/新数据 table pairs and asks to 增量同步, 追平, 补数据, append new rows, or keep the new table consistent using a 核对字段. Use this for direct Base links, especially when each pair includes 数据名称, 原数据, 新数据, and 核对字段.
compatibility: Requires lark-cli authenticated with access to the source and target Feishu Base tables.
---

# Feishu Base Pair Incremental Sync

## Purpose

执行一组或多组飞书多维表格的「原数据表 → 新数据表」增量追加同步。每组任务用自己的「核对字段」计算断点，只把原数据表中新增的记录追加到新数据表。

这个 skill 只追加记录，不删除、不覆盖、不修改字段结构。

## Required tool policy

- 优先使用 `lark-cli` 操作飞书多维表格。
- 如果不确定 `lark-cli` 子命令参数，先运行 `lark-cli --help` 或对应子命令 `--help`。
- 写入前必须先 dry-run，向用户汇总“每张表将追加多少条”。
- dry-run 后必须等待用户明确回复「执行」「继续同步」或同等确认，再运行 `--execute`。
- 如果缺少数据名称、原数据、新数据、核对字段，先追问缺失项，不生成配置、不执行脚本。
- 如果字段缺失、字段语义明显错位、目标字段选项不兼容，停止该表并汇报，不要硬写脏数据。

## User input format

要求用户按这个格式提交：

```text
同步任务：

1. 数据名称：事业单位汇总
   原数据：https://xxx.feishu.cn/base/...?table=xxx&view=xxx
   新数据：https://xxx.feishu.cn/base/...?table=xxx&view=xxx
   核对字段：更新时间

2. 数据名称：国企招聘
   原数据：https://xxx.feishu.cn/base/...?table=xxx&view=xxx
   新数据：https://xxx.feishu.cn/base/...?table=xxx&view=xxx
   核对字段：发布时间
```

每组都必须有：

| 字段 | 作用 |
|---|---|
| 数据名称 | 汇报和排错 |
| 原数据 | 源 Base 表 URL |
| 新数据 | 目标 Base 表 URL |
| 核对字段 | 判断增量断点的日期/时间字段 |

如果用户只给链接，回复类似：

```text
这组同步任务还缺少「核对字段」。请补充用于判断新增数据的日期/时间字段名，例如：更新时间、发布时间、录入时间。
```

## Standard workflow

### 1. Parse and validate tasks

从用户文本整理出 JSON 配置。不要让脚本直接解析自然语言。

```json
{
  "tasks": [
    {
      "name": "事业单位汇总",
      "source_url": "https://xxx.feishu.cn/base/...?table=xxx&view=xxx",
      "target_url": "https://xxx.feishu.cn/base/...?table=xxx&view=xxx",
      "checkpoint_field": "更新时间"
    }
  ]
}
```

将配置写入临时 JSON 文件，例如：

```text
/tmp/feishu_sync_tasks.json
```

### 2. Dry-run first

运行：

```bash
python ~/.claude/skills/feishu-base-pair-incremental-sync/scripts/pair_incremental_sync.py \
  --config /tmp/feishu_sync_tasks.json \
  --dry-run
```

脚本会：

1. 从 URL 解析 base token、table id、view id。
2. 读取原表和新表字段。
3. 确认核对字段在两边都存在。
4. 读取新表核对字段，计算 `target_latest_date`。
5. 读取原表核对字段，计算 `source_latest_date`。
6. 筛选原表中 `checkpoint_field > target_latest_date` 且 `checkpoint_field <= today` 的记录。
7. 去重并统计待追加条数。

### 3. Ask for confirmation

Dry-run 后必须向用户汇报结果，并等待确认。不要在同一轮里直接执行写入。

```markdown
预检结果：预计追加 N 条。

| 数据名称 | 新表最新日期 | 原表最新日期 | 待追加条数 | 跳过条数 | 状态 |
|---|---:|---:|---:|---:|---|

请确认是否执行写入。回复「执行」后才会追加数据。
```

### 4. Execute only after confirmation

用户明确确认后运行：

```bash
python ~/.claude/skills/feishu-base-pair-incremental-sync/scripts/pair_incremental_sync.py \
  --config /tmp/feishu_sync_tasks.json \
  --execute
```

常用参数：

| 参数 | 作用 |
|---|---|
| `--today YYYY-MM-DD` | 指定今天日期，便于复盘或测试 |
| `--batch-size 50` | 批量写入条数 |
| `--no-sort` | 只写入，不设置视图排序 |
| `--output-json /tmp/result.json` | 输出机器可读结果 |
| `--verbose` | 输出详细错误信息 |

### 5. Verify and report

执行后脚本会重新读取原表和新表日期字段，确认新表是否追到原表最新日期；如果原表有未来日期，只确认追到今天范围内的最大日期。

```markdown
同步完成：已追加 N 条。

| 数据名称 | 追加条数 | 新表原最新日期 | 新表现最新日期 | 原表最新日期 | 复查结果 |
|---|---:|---:|---:|---:|---|

跳过/异常：
- 无
```

## Incremental rules

每组任务使用：

```text
原表记录日期 > 新表最新日期
原表记录日期 <= 今天
```

如果目标表为空，则同步原表中 `checkpoint_field <= today` 的全部可解析记录。

日期解析支持：

- `2026-06-10`
- `2026/06/10`
- `2026.6.10`
- `2026年6月10日`
- `6月10日`：默认使用当前年份

## De-duplication rules

追加前做两层去重：

1. 和目标表已有数据去重。
2. 待写入数据内部去重。

优先使用链接字段：

- `公告链接`
- `公告原链接`
- `原文链接`
- `来源链接`
- `投递链接`
- `链接`
- `网址`
- `URL`
- `url`

链接标准化：

- 从 Markdown 链接 `[文本](url)` 提取 `url`
- 去掉首尾空格
- 转小写
- 去掉末尾 `/`

没有链接字段时，使用组合键：

```text
单位/公司/标题/岗位 + 核对字段日期
```

候选字段：

- `单位名称`
- `招聘单位`
- `公司`
- `公司名称`
- `招聘公告标题`
- `公告标题`
- `标题`
- `岗位`
- `招聘岗位`

## Field mapping and cell coercion

默认只写入原表和新表共有字段。

| 目标字段类型 | 处理 |
|---|---|
| 文本/URL/电话/邮箱 | 数组或对象转文本 |
| 数字/金额/百分比 | 尝试转数字，失败则跳过该字段 |
| 日期/时间 | 保留飞书读出的值 |
| 单选 | 只写目标已有选项 |
| 多选 | 只写目标已有选项 |
| 人员/附件/公式/查找引用 | 第一版跳过 |

如果核心字段 `checkpoint_field` 缺失，该任务失败，不写入该表。

## Sorting

写入后默认把目标视图按核对字段倒序排序。排序失败不回滚写入；报告里标记“写入成功，排序失败”。

## Safety notes

- 不要删除新表已有记录。
- 不要覆盖旧记录。
- 不要清空目标表。
- 不要修改字段结构。
- 不要新增字段选项。
- 不要创建新表。
- 不要把 `--execute` 和 dry-run 放在同一轮未确认流程里。
- 不要猜核对字段；用户没给就追问。
