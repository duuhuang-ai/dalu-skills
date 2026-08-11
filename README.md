# dalu-skills

大路的 Claude Code Skills 合集。

## 安装

在 Claude Code 中运行：

```
/install-skill https://github.com/duuhuang-ai/dalu-skills/tree/master/{skill名}
```

例如：

```
/install-skill https://github.com/duuhuang-ai/dalu-skills/tree/master/xhs-virtual-selection-assistant
```

## Skills 一览

### 小红书虚拟选品

**xhs-virtual-selection-assistant** — 小红书虚拟产品选品分析助手

根据小红书虚拟商品链接或手动商品信息，判断商品是否值得跟进、如何改造成自己的产品，以及上架前需要规避的风险。

- 支持商品链接和手动商品信息两种输入方式
- 输出 推荐做 / 改造后再做 / 不建议做 的商家决策
- 拆解需求、价格、销量、差异化空间、交付难度和违规风险
- 给出 3 个可落地的改造方向和上架包装建议
- 默认生成可直接打开的独立 HTML 选品分析报告

### 文案提纯

**copywriting-purification** — 视频/音频文案提纯为"分享式提纯版原文"

将抖音/小红书视频链接、本地视频或原始文字稿一键转化为结构化原文并自动交付飞书文档。

- 三种输入模式：平台链接自动提取+转写、本地视频批量转写、纯文本提纯
- 通过 TikHub 提取平台视频，百炼 Paraformer-v2 进行 ASR 转写
- 按"分享式提纯版原文"规则去除噪音、修正同音词、结构化输出
- 自动交付为飞书文档

## 依赖

| Skill | 依赖 |
|-------|------|
| xhs-virtual-selection-assistant | 无 |
| copywriting-purification | TikHub API, 百炼 DashScope, 阿里云 OSS, 飞书 lark-doc |
