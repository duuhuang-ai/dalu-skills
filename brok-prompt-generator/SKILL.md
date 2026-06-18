---
name: brok-prompt-generator
description: Generate, rewrite, optimize, audit, and standardize prompts using the BROK framework. Use this skill whenever the user asks to create a prompt, optimize a prompt, rewrite a prompt, make a reusable prompt, design a role prompt, design a workflow prompt, convert a task into a prompt, improve prompt stability, or explicitly mentions BROK, 提示词生成, 提示词优化, 提示词改写, 可复用 prompt, 角色提示词, 工作流提示词, or 把任务变成提示词.
---

# BROK Prompt Generator

Use this skill to transform rough user requirements, existing prompts, or task descriptions into structured, reusable prompts using the BROK framework.

The skill supports three modes:

1. Generate a new reusable prompt from a task description.
2. Rewrite or optimize an existing prompt.
3. Audit an existing prompt for stability and completeness.

Do not execute the user's underlying task unless they explicitly ask for execution after the prompt is created. The primary deliverable is a prompt, not the task result.

## BROK Definition

BROK means:

- B = Background / 背景
- R = Role / 角色
- O = Objective / 目标
- K = Key Results & Constraints / 关键结果与约束

Use this definition by default. Only change it if the user explicitly provides another BROK definition.

K is the main stability layer. It should capture output format, quality standards, must-do rules, must-not-do rules, edge cases, and missing-information handling.

## When to Use

Use this skill when the user asks to:

- generate a prompt
- rewrite a prompt
- optimize a prompt
- audit a prompt
- standardize a prompt
- create a reusable prompt template
- convert a task into a prompt
- design a role prompt
- design a workflow prompt
- improve prompt stability
- apply BROK to a prompt

Use the skill for Chinese or English requests. Common trigger phrases include:

- BROK
- 提示词生成
- 提示词优化
- 提示词改写
- 审查 prompt
- 可复用 prompt
- 角色提示词
- 工作流提示词
- 把任务变成提示词
- 帮我写一个 prompt

Do not use this skill when the user simply wants the underlying task completed directly.

Examples:

- "帮我写一篇产品介绍" → complete the writing task directly.
- "帮我写一个用于生成产品介绍的提示词" → use this skill.
- "帮我分析这个项目" → complete the analysis directly.
- "帮我写一个用于分析项目的 prompt" → use this skill.

## Input Collection

Before generating the prompt, identify as many of these as possible from the user's request:

1. Task type: writing, coding, analysis, extraction, research, automation, sales, customer service, review, etc.
2. Target user or audience.
3. Input material or input format.
4. Desired output.
5. Output format.
6. Tone or style.
7. Constraints and forbidden behaviors.
8. Success criteria.
9. Reference examples, if any.
10. Usage environment: Claude, Claude Code, API, workflow, internal SOP, etc.

If missing information does not materially change the prompt, make a reasonable assumption and label it in the BROK breakdown or usage notes.

Ask follow-up questions only when the missing information would materially change the task type, audience, output format, or hard constraints. Ask no more than three questions at once.

## Workflow

### Step 1: Classify the request

Determine whether the user wants:

- new prompt generation
- prompt rewriting
- prompt auditing
- prompt standardization
- prompt compression
- prompt expansion
- Claude Code workflow prompt
- API/system prompt

If the user provides an existing prompt and asks whether it is stable, good, complete, or BROK-compliant, use audit mode.

If the user provides an existing prompt and asks to improve, rewrite, optimize, or standardize it, use optimization mode.

Otherwise, use generation mode.

### Step 2: Extract the real goal

Identify:

- what the user wants the prompt to accomplish
- who will use the prompt
- what input the prompt will receive
- what output it should produce
- what failure modes should be prevented

Do not preserve vague wording when it can be turned into observable criteria. Translate vague requirements into concrete standards.

Examples:

- "高质量" → "包含明确结论、可执行步骤、关键风险和验证方式"
- "专业" → "使用准确术语，结论有依据，不堆砌概念"
- "自然" → "使用短句和口语化表达，避免总结腔、排比句和过度连接词"
- "稳定" → "输出结构固定，缺失信息有处理规则，禁止编造"

### Step 3: Fill the BROK structure

Create a compact BROK breakdown:

| BROK | Content |
|---|---|
| B Background | Context, audience, source material, use case, known assumptions |
| R Role | Model role, expertise, tone, working style, decision style |
| O Objective | Main task, final deliverable, success criteria |
| K Key Results & Constraints | Output format, quality bar, must-do rules, must-not-do rules, edge cases, missing-information handling |

### Step 4: Generate the reusable prompt

The generated prompt should include:

- role definition
- task background
- objective
- input placeholders
- step-by-step workflow
- output format
- constraints
- quality checklist
- missing-information rule

Prefer reusable placeholders over one-off details, for example:

- `{{任务背景}}`
- `{{目标用户}}`
- `{{输入材料}}`
- `{{输出格式}}`
- `{{语气风格}}`
- `{{限制条件}}`
- `{{参考样例}}`
- `{{禁止事项}}`

### Step 5: Provide usage notes

Explain:

- which placeholders to replace
- how to adapt the prompt
- how to make it stricter or looser
- how to use it in Claude Code, Claude, API, or workflow systems when relevant

## Output Formats

### Generation or optimization mode

Use this structure:

```markdown
## BROK 拆解

| BROK | 内容 |
|---|---|
| B 背景 | ... |
| R 角色 | ... |
| O 目标 | ... |
| K 关键结果与约束 | ... |

## 可复用提示词

```text
...
```

## 使用说明

1. ...
2. ...
3. ...

## 可选调整项

- ...
- ...
- ...
```

For optimization mode, add a short section before the BROK breakdown:

```markdown
## 原提示词主要问题

- ...
- ...
- ...
```

### Audit mode

Use this structure:

```markdown
## BROK 评分

| 维度 | 分数 | 问题 |
|---|---:|---|
| B 背景 | x/5 | ... |
| R 角色 | x/5 | ... |
| O 目标 | x/5 | ... |
| K 关键结果与约束 | x/5 | ... |
| 复用性 | x/5 | ... |
| 稳定性 | x/5 | ... |

## 主要问题

- ...
- ...
- ...

## 修改建议

- ...
- ...
- ...

## 优化版提示词

```text
...
```
```

## Quality Checklist

Before finalizing, check:

- Background is specific enough.
- Role affects behavior, not just decoration.
- Objective has a concrete deliverable.
- Output format is explicit.
- Quality standard is observable.
- Constraints are actionable.
- Must-do and must-not-do rules are included.
- The prompt contains reusable placeholders.
- Missing information handling is defined.
- The final prompt separates workflow from output format.
- The answer does not directly execute the user's underlying task unless asked.

## Mode-Specific Guidance

### Writing prompts

For writing tasks, include audience, platform, tone, length, structure, forbidden style patterns, and examples when available.

### Coding or Claude Code prompts

For coding tasks, include repository rules, file-change boundaries, root-cause analysis, validation commands, reporting format, and a prohibition against bypassing errors without understanding the cause.

### Analysis prompts

For analysis tasks, include decision criteria, evidence requirements, counterarguments, risks, assumptions, and conclusion-first output.

### Extraction prompts

For extraction tasks, include field definitions, missing-value handling, no-guessing rules, output schema, and validation rules.

### Automation prompts

For automation tasks, include input source, processing steps, allowed fields to modify, failure handling, idempotency concerns, and final run report.

## Common Mistakes to Avoid

- Do not turn the skill into a generic prompt collection.
- Do not ask many questions when reasonable assumptions are enough.
- Do not output only the final prompt without BROK breakdown.
- Do not let K become weak or vague.
- Do not use decorative roles such as "你是专家" unless the role changes behavior.
- Do not keep vague standards such as "高质量" without defining what they mean.
