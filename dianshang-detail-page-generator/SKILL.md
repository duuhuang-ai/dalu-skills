---
name: dianshang-detail-page-generator
description: Generate ecommerce product detail-page images from user-provided product photos, especially Chinese ecommerce/Xiaohongshu/Taobao-style apparel detail pages. Use when the user asks to analyze product style, audience, scenes, selling points, create 商品详情图/电商详情页/长图, follow MY105 or another reference style, split detail pages into separate module images for review, revise a single page, stitch approved pages into one long detail image, or output a 2x high-resolution version.
---

# 电商详情图分段生成

## Core Rule

Default to a split-first workflow: analyze the product, align on style, generate separate `900px`-wide module images, let the user review individual pages, then stitch the approved pages into a final long image. Do not start by generating one very long detail page unless the user explicitly asks for a single image immediately.

Follow the current workspace `AGENTS.md` first. Preserve source images, save deliverables into `outputs/`, and use lowercase English filenames with page numbers.

## Workflow

1. **Read workspace rules**
   - Read `AGENTS.md` in the current project if present.
   - Confirm expected folders such as `outputs/`, `prompts/`, and `references/`.
   - Do not overwrite source images. Do not overwrite existing finished images unless the user explicitly asks.

2. **Inspect product images**
   - Identify product category, style, target audience, use scenarios, and strongest selling points.
   - For apparel, inspect neckline, sleeve shape, waistline, silhouette, length, pattern, fabric feel, body-shaping effect, and photo scenarios.
   - Summarize in Chinese by default before generating images when the user has not already approved the positioning.

3. **Align style and content**
   - Ask for or infer the brand name, reference style, size-table source, and output strategy.
   - If the user says MY105, use MY105 as one default style option, not a hard-coded requirement.
   - If the user provides another reference detail page, extract its visual language first, then apply the same split-first workflow.
   - If no reference is provided, use a clean, restrained ecommerce detail-page style with white space, readable modules, and product-photo priority.

4. **Generate split pages first**
   - Generate separate `900px`-wide PNG files. Use one finished image per page.
   - Keep text outside product bodies whenever possible.
   - Prefer real product photos supplied by the user over AI-redrawn products.
   - For text-heavy pages, allocate extra height instead of shrinking text until it becomes unreadable.

5. **Create a contact-sheet preview**
   - After generating or revising pages, create a contact sheet showing all pages.
   - Inspect for text overlap, missing text, font fallback squares, English overflow, image cropping problems, and page height truncation.
   - If a defect is obvious, fix it before reporting completion.

6. **Revise only the affected page**
   - When the user points to a page problem, modify only that page unless the fix requires a shared style change.
   - Recreate the affected page and update the contact sheet.
   - Do not regenerate the entire set just to fix one text overlap.

7. **Stitch only after approval**
   - When the user says the split pages are fine, concatenate them in page-number order into one final long image.
   - Produce a final contact-sheet preview for the stitched image.
   - If requested, create a `2x` high-resolution version from the final approved image.

## Default Page Set

Use these names and purposes unless the user requests another structure:

- `page-01-brand-hero.png`: top brand strip, brand title, primary product hero image, basic feature icons.
- `page-02-core-selling.png`: Chinese core selling title, short selling copy, large product image, side labels.
- `page-03-design-collage.png`: magazine-style staggered collage, usually one large image plus two right-side images.
- `page-04-detail-points.png`: detail-point text such as neckline, sleeves, waist, hem, pattern, fabric.
- `page-05-service-info.png`: after-sales promise and product index information.
- `page-06-attention-size.png`: care instructions, size table, washing icons.
- `page-07-model-display-01.png`: model-display photo flow, first group.
- `page-08-model-display-02.png`: model-display photo flow, second group and footer.

After approval, stitch into a final file such as `<brand>-detail-final.png`.

## MY105 Style Option

Use MY105 when the user asks for it or when a saved MY105 reference exists and fits the product.

MY105 style cues:

- White background with black, gray, and pale beige accents.
- Restrained, clean, magazine-like layout with ample white space.
- Large serif English title or brand wordmark; Chinese titles use a Songti/serif-like look.
- Upper section includes brand area, selling copy, design collage, after-sales, index, care, and size modules.
- Lower section prioritizes model-display photo flow with minimal repeated text.
- Do not use loud promotional colors, heavy badges, dense stickers, or crowded text blocks.

Treat MY105 as a reusable style preset. If the user supplies a different reference, extract and follow that reference instead.

## Text and Layout Checks

Always check these before saying a page is done:

- Chinese characters render correctly and do not become square placeholders.
- Mixed Chinese/English headings use a font that supports the characters.
- English captions stay inside their intended column and do not run under photos.
- Bottom titles have a dedicated white-space band and are not covered by collage images.
- Feature icons have enough room for their captions.
- Model photo pages are tall enough; no final image is cut off.
- Product body is not covered by text labels.
- The contact-sheet preview matches the intended page order.

## Common User Commands

- "使用 dianshang-detail-page-generator，参考 MY105 风格，先分段生成。"
- "只修改第 3 张，底部英文不要被遮挡。"
- "这些分段图没问题，拼接成完整详情图。"
- "把最终详情图输出 2 倍高清版。"

## Output Discipline

Report the saved paths for generated pages, contact sheets, final stitched images, and HD versions. Keep the response concise and in Chinese unless the user asks otherwise.
