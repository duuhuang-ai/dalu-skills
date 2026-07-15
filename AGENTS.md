# Repository Guidelines

## Structure

- Each skill lives in a top-level directory named by its skill slug.
- Each skill directory must contain `SKILL.md`.
- Shared repository documentation lives in `README.md`.
- Skill-specific helper files, when needed, should live under that skill directory, for example `scripts/`.

## Skill Format

- `SKILL.md` starts with YAML frontmatter containing at least `name` and `description`.
- The `name` value should match the directory name.
- Keep skill instructions self-contained so the directory can be installed directly.

## Verification

- After adding or changing a skill, verify:
  - every top-level skill directory contains `SKILL.md`;
  - frontmatter `name` matches its directory;
  - `README.md` lists the skill and its dependencies.

## Git Safety

- Do not push, publish, or deploy without explicit owner confirmation.
