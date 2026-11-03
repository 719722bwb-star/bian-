# bian-

边同学（@b666wb）的 AI 助手技能库。每个技能一个目录：`skills/<skill-id>/SKILL.md` 写给助手的步骤，同目录放它要用的脚本、示例和图片。

## 目录

- `skills/<skill-id>/SKILL.md`：技能说明。开头是 YAML frontmatter（`name`、`description`），后面是具体做法。
- 同目录的其他文件：转换脚本、示例稿、预览图等，跟着技能走，不散落到仓库外面。

## 技能

- **bian-wechat-article**：把边同学的 X 长文或 thread 改写成微信公众号文章（写法、标题摘要、封面、温暖手账风排版、发布前检查）。

把 Markdown 转成可粘贴进公众号的内联样式 HTML（需要先 `pip install markdown`）：

```bash
python3 skills/bian-wechat-article/md2wechat.py article.md --style B -o out.html
```

`--style B` 是温暖手账风。示例稿在 `skills/bian-wechat-article/examples/sample.md`。
