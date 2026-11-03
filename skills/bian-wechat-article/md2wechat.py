#!/usr/bin/env python3
"""把 Markdown 转成微信公众号内联样式 HTML。

用法：
    python3 md2wechat.py 文章.md --style B -o out.html

风格 B 是温暖手账：15px / 行距 1.9 / 字距 1px / #4A4039，
小标题为浅橙胶囊，加粗为 #FFD8B8 荧光笔下划，外链收进文末「参考链接」。
下一段以「图：」开头会排成灰色小号图注。
"""

from __future__ import annotations

import argparse
import sys
from html import escape
from pathlib import Path
from xml.etree import ElementTree as ET

import markdown


THEMES = {
    "A": {
        "name": "红线",
        "text": "#1A1A1A",
        "accent": "#B81C1C",
        "paper": "#FFFFFF",
        "mark": "#F8D0D0",
        "muted": "#888888",
        "quote_text": "#1A1A1A",
        "font_size": "16px",
        "line_height": "1.85",
        "letter_spacing": "0.5px",
        "padding": "16px",
        "heading": "underline",
        "quote": "rules",
        "strong": "color",
        "code_bg": "#FDECEC",
        "code_color": "#B81C1C",
        "hr": "#D0D0D0",
        "quote_bg": "#FFFFFF",
    },
    "B": {
        "name": "温暖手账",
        "text": "#4A4039",
        "accent": "#E07A3F",
        "paper": "#FFF4EA",
        "mark": "#FFD8B8",
        "muted": "#888888",
        "quote_text": "#4A4039",
        "font_size": "15px",
        "line_height": "1.9",
        "letter_spacing": "1px",
        "padding": "12px",
        "heading": "badge",
        "quote": "card",
        "strong": "marker",
        "code_bg": "#FFF4EA",
        "code_color": "#B4542A",
        "hr": "#E8C8AC",
        "quote_bg": "#FFF4EA",
    },
    "C": {
        "name": "蓝条",
        "text": "#303030",
        "accent": "#2460E8",
        "paper": "#ECF4FC",
        "mark": "#D6E4FF",
        "muted": "#888888",
        "quote_text": "#303030",
        "font_size": "16px",
        "line_height": "1.85",
        "letter_spacing": "0.3px",
        "padding": "16px",
        "heading": "bar",
        "quote": "side",
        "strong": "color",
        "code_bg": "#FDE8EE",
        "code_color": "#D4537E",
        "hr": "#C8D4E0",
        "quote_bg": "#ECF4FC",
    },
}


class Refs:
    def __init__(self, start: int) -> None:
        self.n = start
        self.links: list[tuple[int, str, str]] = []
        self.seen: dict[str, int] = {}

    def add(self, label: str, href: str) -> int:
        if href in self.seen:
            return self.seen[href]
        self.n += 1
        self.seen[href] = self.n
        self.links.append((self.n, label, href))
        return self.n


def local(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def classes(el: ET.Element) -> list[str]:
    return (el.get("class") or "").split()


def plain(el: ET.Element) -> str:
    return "".join(el.itertext()).strip()


def clean_footnote(el: ET.Element) -> str:
    parts: list[str] = []

    def walk(node: ET.Element) -> None:
        if node.text:
            parts.append(node.text)
        for child in list(node):
            if "footnote-backref" in classes(child):
                if child.tail:
                    parts.append(child.tail)
                continue
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(el)
    return " ".join("".join(parts).replace("\xa0", " ").split())


def harvest_footnotes(root: ET.Element) -> list[tuple[int, str]]:
    items: list[tuple[int, str]] = []
    for div in root.iter("div"):
        if "footnote" not in classes(div):
            continue
        index = 0
        for li in div.iter("li"):
            index += 1
            raw = li.get("id") or ""
            num = index
            if raw.startswith("fn:"):
                try:
                    num = int(raw.split(":", 1)[1])
                except ValueError:
                    num = index
            text = clean_footnote(li)
            if text:
                items.append((num, text))
    return items


def is_external(href: str) -> bool:
    return href.startswith("http://") or href.startswith("https://")


def link_label(el: ET.Element, href: str) -> str:
    label = "".join(el.itertext()).strip()
    if label:
        return label
    img = el.find(".//img")
    if img is not None and img.get("alt"):
        return img.get("alt") or href
    return href


def marker_style(theme: dict) -> str:
    return (
        f"font-weight:700;color:{theme['text']};"
        f"background-image:linear-gradient(transparent 58%, {theme['mark']} 58%);"
        "-webkit-box-decoration-break:clone;box-decoration-break:clone;"
    )


def text_style(theme: dict, *, margin: str, color: str | None = None) -> str:
    return (
        f"margin:{margin};text-indent:0;"
        f"font-size:{theme['font_size']};"
        f"line-height:{theme['line_height']};"
        f"letter-spacing:{theme['letter_spacing']};"
        f"color:{color or theme['text']};"
    )


def sup_html(num: int, theme: dict) -> str:
    return (
        f'<sup style="color:{theme["accent"]};font-size:12px;'
        f'letter-spacing:0;line-height:0;">[{num}]</sup>'
    )


def render_children(el: ET.Element, theme: dict, refs: Refs, parent: str | None) -> str:
    parts: list[str] = []
    if el.text:
        parts.append(escape(el.text))
    for child in list(el):
        parts.append(render(child, theme, refs, parent))
        if child.tail:
            parts.append(escape(child.tail))
    return "".join(parts)


def render_heading(el: ET.Element, level: int, theme: dict, refs: Refs) -> str:
    content = render_children(el, theme, refs, f"h{level}")
    text = theme["text"]
    accent = theme["accent"]
    mode = theme["heading"]
    tag = f"h{level}"

    if mode == "badge" and level >= 2:
        pad = "6px 18px" if level == 2 else "4px 14px"
        size = theme["font_size"] if level == 2 else "14px"
        wrap = (
            f"text-align:center;font-size:{size};font-weight:700;"
            f"line-height:1.5;margin:20px 0 14px;color:{text};"
            f"letter-spacing:{theme['letter_spacing']};"
        )
        badge = (
            "display:inline-block;padding:"
            f"{pad};background:{theme['paper']};"
            f"border:1.5px dashed {accent};border-radius:999px;"
        )
        return f'<{tag} style="{wrap}"><span style="{badge}">{content}</span></{tag}>'

    if mode == "underline" and level == 2:
        style = (
            f"font-size:18px;font-weight:700;color:{text};"
            f"margin:26px 0 12px;padding-bottom:6px;"
            f"border-bottom:4px double {accent};letter-spacing:0.5px;"
        )
        return f'<{tag} style="{style}">{content}</{tag}>'

    if mode == "bar" and level == 2:
        style = (
            f"font-size:18px;font-weight:700;color:{accent};"
            f"margin:26px 0 12px;padding-left:10px;"
            f"border-left:4px solid {accent};letter-spacing:0.3px;"
        )
        return f'<{tag} style="{style}">{content}</{tag}>'

    size = {1: "22px", 2: "18px", 3: "16px"}.get(level, "15px")
    align = "center" if level == 1 else "left"
    style = (
        f"font-size:{size};font-weight:700;color:{text};"
        f"margin:18px 0 10px;text-align:{align};line-height:1.4;"
    )
    return f'<{tag} style="{style}">{content}</{tag}>'


def render_quote(el: ET.Element, theme: dict, refs: Refs) -> str:
    body = render_children(el, theme, refs, "blockquote")
    mode = theme["quote"]
    if mode == "card":
        style = (
            f"background:{theme['quote_bg']};border-radius:16px;"
            "padding:14px 16px;margin:16px 0;"
        )
    elif mode == "rules":
        style = (
            f"margin:16px 0;padding:12px 0;"
            f"border-top:3px double {theme['accent']};"
            f"border-bottom:3px double {theme['accent']};"
        )
    else:
        style = (
            f"background:{theme['quote_bg']};"
            f"border-left:4px solid {theme['accent']};"
            "border-radius:4px;padding:10px 14px;margin:16px 0;"
        )
    return f'<section style="{style}">{body}</section>'


def paragraph_style(el: ET.Element, theme: dict, parent: str | None) -> str:
    text = plain(el)
    if text.startswith("图：") or text.startswith("图:"):
        return (
            "margin:-4px 0 16px;text-indent:0;font-size:12px;"
            "line-height:1.6;letter-spacing:0;color:#888888;"
        )
    if text == "" and el.find(".//img") is not None:
        return "margin:12px 0;text-indent:0;"
    if parent == "blockquote":
        return text_style(theme, margin="0 0 8px", color=theme["quote_text"])
    if parent == "li":
        return text_style(theme, margin="0")
    return text_style(theme, margin="0 0 12px")


def render_link(el: ET.Element, theme: dict, refs: Refs) -> str:
    href = el.get("href") or ""
    cls = classes(el)
    if "footnote-backref" in cls:
        return ""
    if "footnote-ref" in cls:
        num = "".join(el.itertext()).strip() or "1"
        try:
            shown = int(num)
        except ValueError:
            shown = num
        return sup_html(shown, theme) if isinstance(shown, int) else (
            f'<sup style="color:{theme["accent"]};font-size:12px;letter-spacing:0;">'
            f"[{escape(num)}]</sup>"
        )
    content = render_children(el, theme, refs, "a")
    if is_external(href):
        label = link_label(el, href)
        num = refs.add(label, href)
        return f"{content}{sup_html(num, theme)}"
    if content:
        return content
    return escape(plain(el))


def render(el: ET.Element, theme: dict, refs: Refs, parent: str | None) -> str:
    tag = local(el.tag)
    if tag == "div" and "footnote" in classes(el):
        return ""
    if tag in {"script", "style", "iframe", "object", "embed"}:
        return ""
    if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return render_heading(el, int(tag[1]), theme, refs)
    if tag == "p":
        style = paragraph_style(el, theme, parent)
        return f'<p style="{style}">{render_children(el, theme, refs, "p")}</p>'
    if tag == "blockquote":
        return render_quote(el, theme, refs)
    if tag in {"strong", "b"}:
        content = render_children(el, theme, refs, tag)
        if theme["strong"] == "marker":
            return f'<strong style="{marker_style(theme)}">{content}</strong>'
        style = f"font-weight:700;color:{theme['accent']};"
        return f"<strong style=\"{style}\">{content}</strong>"
    if tag == "mark":
        return f'<strong style="{marker_style(theme)}">{render_children(el, theme, refs, tag)}</strong>'
    if tag == "em" or tag == "i":
        content = render_children(el, theme, refs, tag)
        return f'<em style="font-style:italic;">{content}</em>'
    if tag == "del":
        content = render_children(el, theme, refs, tag)
        return f'<del style="color:{theme["muted"]};">{content}</del>'
    if tag == "code" and parent == "pre":
        content = render_children(el, theme, refs, "code")
        return (
            '<code style="font-family:ui-monospace,Menlo,Consolas,monospace;'
            f'font-size:13px;letter-spacing:0;background:transparent;color:{theme["text"]};">'
            f"{content}</code>"
        )
    if tag == "code":
        content = render_children(el, theme, refs, "code")
        style = (
            f"background:{theme['code_bg']};color:{theme['code_color']};"
            "padding:1px 6px;border-radius:4px;font-size:0.92em;"
            "letter-spacing:0;font-family:inherit;font-style:normal;"
        )
        return f'<code style="{style}">{content}</code>'
    if tag == "pre":
        content = render_children(el, theme, refs, "pre")
        style = (
            f"background:{theme['paper']};color:{theme['text']};"
            "padding:12px 14px;border-radius:8px;overflow:auto;"
            "font-size:13px;line-height:1.6;letter-spacing:0;margin:12px 0;"
        )
        return f'<pre style="{style}">{content}</pre>'
    if tag == "a":
        return render_link(el, theme, refs)
    if tag == "sup":
        return render_children(el, theme, refs, "sup")
    if tag == "img":
        src = escape(el.get("src") or "", quote=True)
        alt = escape(el.get("alt") or "", quote=True)
        return (
            f'<img src="{src}" alt="{alt}" style="display:block;width:100%;'
            'max-width:100%;height:auto;margin:8px 0;border:0;"/>'
        )
    if tag == "hr":
        return (
            f'<section style="border:none;border-top:2px dotted {theme["hr"]};'
            'margin:22px 0;height:0;font-size:0;line-height:0;">&#8203;</section>'
        )
    if tag in {"ul", "ol"}:
        content = render_children(el, theme, refs, tag)
        kind = "disc" if tag == "ul" else "decimal"
        style = (
            "margin:8px 0 12px;padding-left:1.3em;"
            f"list-style-type:{kind};color:{theme['text']};"
        )
        return f'<{tag} style="{style}">{content}</{tag}>'
    if tag == "li":
        content = render_children(el, theme, refs, "li")
        style = (
            f"margin:4px 0;line-height:{theme['line_height']};"
            f"font-size:{theme['font_size']};letter-spacing:{theme['letter_spacing']};"
            f"color:{theme['text']};"
        )
        return f'<li style="{style}">{content}</li>'
    if tag == "br":
        return "<br/>"
    if tag == "table":
        content = render_children(el, theme, refs, "table")
        return (
            '<table style="border-collapse:collapse;width:100%;'
            f'margin:12px 0;font-size:14px;color:{theme["text"]};">{content}</table>'
        )
    if tag in {"thead", "tbody", "tr"}:
        return f"<{tag}>{render_children(el, theme, refs, tag)}</{tag}>"
    if tag in {"th", "td"}:
        content = render_children(el, theme, refs, tag)
        weight = "700" if tag == "th" else "400"
        bg = theme["paper"] if tag == "th" else "transparent"
        style = (
            f"border:1px solid {theme['hr']};padding:6px 8px;"
            f"font-weight:{weight};background:{bg};text-align:left;"
        )
        return f'<{tag} style="{style}">{content}</{tag}>'
    if tag == "span" and el.get("style"):
        style = escape(el.get("style") or "", quote=True)
        return f'<span style="{style}">{render_children(el, theme, refs, "span")}</span>'
    return render_children(el, theme, refs, tag)


def format_ref(num: int, label: str, href: str) -> str:
    if not label or label == href or href in label:
        body = label or href
    else:
        body = f"{label}：{href}"
    return f"[{num}] {body}"


def references_html(
    theme: dict,
    footnotes: list[tuple[int, str]],
    links: list[tuple[int, str, str]],
) -> str:
    if not footnotes and not links:
        return ""
    label_style = (
        f"margin:28px 0 6px;font-size:13px;line-height:1.6;"
        f"letter-spacing:0;color:{theme['muted']};"
    )
    item_style = (
        f"margin:2px 0;font-size:13px;line-height:1.6;"
        f"letter-spacing:0;color:{theme['muted']};word-break:break-all;"
    )
    parts = [f'<p style="{label_style}">参考链接</p>']
    for num, text in footnotes:
        parts.append(f'<p style="{item_style}">[{num}] {escape(text)}</p>')
    for num, label, href in links:
        parts.append(f'<p style="{item_style}">{escape(format_ref(num, label, href))}</p>')
    return "".join(parts)


def section_style(theme: dict) -> str:
    return (
        f"padding:{theme['padding']};background:#ffffff;color:{theme['text']};"
        f"font-size:{theme['font_size']};line-height:{theme['line_height']};"
        f"letter-spacing:{theme['letter_spacing']};"
        "font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',"
        "'Hiragino Sans GB','Microsoft YaHei',sans-serif;"
        "text-align:left;word-wrap:break-word;"
    )


def first_heading(root: ET.Element) -> str:
    for tag in ("h1", "h2"):
        el = root.find(f".//{tag}")
        if el is not None:
            text = plain(el)
            if text:
                return text
    return "公众号预览"


def page(title: str, body: str, theme: dict) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '<meta charset="utf-8"/>\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>\n'
        f"<title>{escape(title)}</title>\n"
        "<style>\n"
        "  body { margin: 0; background: #f6f4f1; }\n"
        "  #article { max-width: 414px; margin: 0 auto; background: #fff; }\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f'<section id="article" style="{section_style(theme)}">\n'
        f"{body}\n"
        "</section>\n"
        "</body>\n"
        "</html>\n"
    )


def convert(md_text: str, style: str) -> str:
    key = style.strip().upper()
    if key not in THEMES:
        known = "、".join(f"{name}（{THEMES[name]['name']}）" for name in THEMES)
        raise ValueError(f"未知版式 {style}，可选：{known}")
    theme = THEMES[key]
    raw = markdown.markdown(
        md_text,
        extensions=["extra", "sane_lists"],
        output_format="xhtml",
    )
    try:
        root = ET.fromstring(f"<article>{raw}</article>")
    except ET.ParseError as exc:
        raise ValueError(f"Markdown 转成的 HTML 无法解析：{exc}") from exc
    footnotes = harvest_footnotes(root)
    start = max((num for num, _ in footnotes), default=0)
    refs = Refs(start)
    body = render_children(root, theme, refs, "article")
    body += references_html(theme, footnotes, refs.links)
    return page(first_heading(root), body, theme)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 Markdown 转成微信公众号内联样式 HTML")
    parser.add_argument("markdown", help="输入的 Markdown 文件")
    parser.add_argument(
        "--style",
        default="B",
        help="版式：A 红线，B 温暖手账（默认），C 蓝条",
    )
    parser.add_argument("-o", "--output", help="输出 HTML 文件；省略则打印到标准输出")
    args = parser.parse_args(argv)

    src = Path(args.markdown)
    if not src.is_file():
        print(f"找不到文件：{src}", file=sys.stderr)
        return 1
    try:
        html = convert(src.read_text(encoding="utf-8"), args.style)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.output:
        dest = Path(args.output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
    else:
        sys.stdout.write(html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
