import React, {
  FC,
  memo,
  useMemo,
  useEffect,
  useRef,
  useCallback,
  useState,
  forwardRef,
  useImperativeHandle,
} from "react";
import MarkdownPreview from "@uiw/react-markdown-preview";
import { Element } from "hast";
import { Components } from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import katex from "katex";
import "katex/dist/katex.min.css";
import { marked } from "marked";

/* ───────────────────────────── types ───────────────────────────── */
interface Props {
  content?: string;
  fontSize?: string | number;
  width?: string | number;
  backgroundColor?: string;
  maxLine?: number;
}

export interface MarkdownViewerHandle {
  copyContent: () => void;
}

/* ───────────────────────────── constants ───────────────────────── */
const RENDERABLE_LANGUAGES: string[] = [];
const PREVIEWABLE_LANGUAGES = ["latex", "tex", "html", "markdown", "md"];

/* ───────────────────────────── design tokens ────────────────────── */
const T = {
  bg: "#ffffff",
  bgHeader: "#f0f4fa",
  textHeader: "#334155",
  borderHeader: "#d6e0f0",
  bgCode: "#1a2236",
  bgHover: "#f3f4f6",
  bgZebra: "#ffffff",
  border: "#e5e7eb",
  borderCode: "#c7d2e6",
  textPrimary: "#222222",
  textSecondary: "#6b7280",
  textInverse: "#d4d4d4",
  textLink: "#2563eb",
  accent: "#4b5563",
  accentText: "#ffffff",
  radius: 10,
  radiusSm: 8,
  mono: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",

  bgTableHeader: "#f0f4fa",
  textTableHeader: "#334155",
  borderTable: "#e5e7eb",
  borderTableHeader: "#d6e0f0",
} as const;

/* ────────────────── Preview 감지 및 렌더링 ─────────────────────── */
const containsLatex = (text: string): boolean =>
  /\$\$|\\[\[(]|\\(?:frac|int|sum|sqrt|begin|text|alpha|beta|cdot|times|infty|partial|over|under|left|right|lim|prod|log|sin|cos|tan)\b/.test(text);

const canPreview = (code: string, language: string): boolean => {
  if (PREVIEWABLE_LANGUAGES.includes(language)) return true;
  return containsLatex(code);
};

const cleanHtmlForPreview = (code: string): string => {
  let c = code;
  const bodyMatch = c.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  if (bodyMatch) {
    c = bodyMatch[1];
  } else {
    c = c
      .replace(/<!DOCTYPE[^>]*>/gi, "")
      .replace(/<\/?html[^>]*>/gi, "")
      .replace(/<head[^>]*>[\s\S]*?<\/head>/gi, "")
      .replace(/<\/?body[^>]*>/gi, "");
  }
  c = c.replace(/\s+border\s*=\s*["'][^"']*["']/gi, "");
  c = c.replace(/\s+cellpadding\s*=\s*["'][^"']*["']/gi, "");
  c = c.replace(/\s+cellspacing\s*=\s*["'][^"']*["']/gi, "");
  c = c.replace(/>\s+</g, "><");
  return c.trim();
};

const renderLatexToHtml = (code: string): string => {
  const renderMath = (latex: string, displayMode: boolean): string => {
    try {
      return katex.renderToString(latex, {
        displayMode,
        throwOnError: false,
        output: "htmlAndMathml",
      });
    } catch {
      return `<span style="color:#ef4444">${latex}</span>`;
    }
  };
  const tokens: { type: "display" | "inline" | "text"; content: string }[] = [];
  let remaining = code;
  while (remaining.length > 0) {
    const m1 = remaining.match(/^([\s\S]*?)\\\[([\s\S]*?)\\\]/);
    const m2 = remaining.match(/^([\s\S]*?)\$\$([\s\S]*?)\$\$/);
    const m3 = remaining.match(/^([\s\S]*?)\\\(([\s\S]*?)\\\)/);
    const candidates = [
      m1 ? { match: m1, type: "display" as const } : null,
      m2 ? { match: m2, type: "display" as const } : null,
      m3 ? { match: m3, type: "inline" as const } : null,
    ].filter(Boolean) as { match: RegExpMatchArray; type: "display" | "inline" }[];
    if (!candidates.length) {
      if (remaining.trim()) tokens.push({ type: "text", content: remaining });
      break;
    }
    candidates.sort((a, b) => a.match[1].length - b.match[1].length);
    const best = candidates[0];
    if (best.match[1].trim()) tokens.push({ type: "text", content: best.match[1] });
    tokens.push({ type: best.type, content: best.match[2].trim() });
    remaining = remaining.slice(best.match[0].length);
  }
  if (!tokens.length) return renderMath(code.trim(), true);
  return tokens
    .map((t) => {
      if (t.type === "display")
        return `<div style="text-align:center;padding:8px 0;overflow-x:auto;">${renderMath(t.content, true)}</div>`;
      if (t.type === "inline")
        return `<span>${renderMath(t.content, false)}</span>`;
      return `<span style="white-space:pre-wrap;">${t.content.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</span>`;
    })
    .join("");
};

const renderPreviewHtml = (code: string, language: string): string => {
  if (language === "html") return cleanHtmlForPreview(code);
  if (language === "markdown" || language === "md")
    return (marked.parse(code) as string).trim();
  return renderLatexToHtml(code);
};

/* ────────────────── 코드블록 원본 추출 유틸 ─────────────────────── */
function extractAllCodeBlocks(
  source: string
): { lang: string; code: string }[] {
  const result: { lang: string; code: string }[] = [];
  const regex = /```(\w*)\s*\n([\s\S]*?)```/g;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(source)) !== null) {
    result.push({
      lang: (m[1] || "").toLowerCase(),
      code: m[2].replace(/\n$/, ""),
    });
  }
  return result;
}

/* ────────────────── rgb → hex 변환 유틸 ─────────────────────────── */
function rgbToHex(rgb: string): string {
  if (rgb.startsWith("#")) return rgb;
  const match = rgb.match(
    /rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*[\d.]+)?\s*\)/
  );
  if (!match) return rgb;
  const r = parseInt(match[1], 10);
  const g = parseInt(match[2], 10);
  const b = parseInt(match[3], 10);
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
}

/* ────────────────── 테이블 복사 유틸 (Word/Excel/Sheets 호환) ──── */
function buildWordCompatibleHtml(tableEl: HTMLTableElement): string {
  const rows = tableEl.querySelectorAll("tr");
  let html = `<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse; width:100%; table-layout:fixed; font-family:sans-serif; font-size:13px; border:1px solid #000000;">`;

  rows.forEach((row) => {
    html += "<tr>";
    const cells = row.querySelectorAll("th, td");
    cells.forEach((cell) => {
      const isTh = cell.tagName.toLowerCase() === "th";
      const text = (cell as HTMLElement).innerText.trim();
      const colspan = cell.getAttribute("colspan");
      const rowspan = cell.getAttribute("rowspan");
      let attrs = "";
      if (colspan && colspan !== "1") attrs += ` colspan="${colspan}"`;
      if (rowspan && rowspan !== "1") attrs += ` rowspan="${rowspan}"`;

      const bg = isTh ? `background-color:${T.bgTableHeader};` : "";
      const weight = isTh ? "font-weight:bold;" : "";

      html += `<${isTh ? "th" : "td"}${attrs} style="border:1px solid #000000; padding:8px; text-align:left; word-wrap:break-word; overflow-wrap:break-word; ${bg} ${weight}">${text}</${isTh ? "th" : "td"}>`;
    });
    html += "</tr>";
  });

  html += "</table>";
  return html;
}

function buildPlainText(tableEl: HTMLTableElement): string {
  const rows = tableEl.querySelectorAll("tr");
  let maxCols = 0;
  rows.forEach((row) => {
    let cols = 0;
    row.querySelectorAll("th, td").forEach((cell) => {
      cols += parseInt(cell.getAttribute("colspan") || "1", 10);
    });
    if (cols > maxCols) maxCols = cols;
  });

  const grid: string[][] = [];
  const occupied: boolean[][] = [];

  rows.forEach((row, rowIdx) => {
    if (!grid[rowIdx]) grid[rowIdx] = new Array(maxCols).fill("");
    if (!occupied[rowIdx]) occupied[rowIdx] = new Array(maxCols).fill(false);

    const cells = row.querySelectorAll("th, td");
    let cellIdx = 0;

    cells.forEach((cell) => {
      while (cellIdx < maxCols && occupied[rowIdx][cellIdx]) cellIdx++;
      const text = (cell as HTMLElement).innerText.trim();
      const cs = parseInt(cell.getAttribute("colspan") || "1", 10);
      const rs = parseInt(cell.getAttribute("rowspan") || "1", 10);

      for (let r = 0; r < rs; r++) {
        for (let c = 0; c < cs; c++) {
          const gr = rowIdx + r;
          const gc = cellIdx + c;
          if (!grid[gr]) grid[gr] = new Array(maxCols).fill("");
          if (!occupied[gr]) occupied[gr] = new Array(maxCols).fill(false);
          occupied[gr][gc] = true;
          if (r === 0 && c === 0) grid[gr][gc] = text;
        }
      }
      cellIdx += cs;
    });
  });

  return grid.map((row) => row.join("\t")).join("\n");
}

function wrapWithStandardHtml(bodyHtml: string): string {
  return `<html><head><meta charset="utf-8"></head><body>${bodyHtml}</body></html>`;
}

function copyTableAsFormatted(tableEl: HTMLTableElement) {
  const plainText = buildPlainText(tableEl);
  const htmlContent = buildWordCompatibleHtml(tableEl);

  const clipboardItem = new ClipboardItem({
    "text/plain": new Blob([plainText], { type: "text/plain" }),
    "text/html": new Blob([wrapWithStandardHtml(htmlContent)], {
      type: "text/html",
    }),
  });

  navigator.clipboard.write([clipboardItem]);
}

function isTableOnly(html: string): boolean {
  const stripped = html.trim();
  if (!stripped) return false;
  const div = document.createElement("div");
  div.innerHTML = stripped;
  const children = Array.from(div.childNodes).filter((node) => {
    if (node.nodeType === Node.TEXT_NODE && !node.textContent?.trim())
      return false;
    return true;
  });
  return (
    children.length >= 1 &&
    children.every(
      (node) =>
        node.nodeType === Node.ELEMENT_NODE &&
        (node as HTMLElement).tagName.toLowerCase() === "table"
    )
  );
}

function getLatexFromKatexEl(el: HTMLElement): string | null {
  const annotation = el.querySelector(
    'annotation[encoding="application/x-tex"]'
  );
  if (annotation?.textContent) return annotation.textContent;

  const mathEl = el.querySelector(".katex-mathml math");
  if (mathEl) {
    const ann = mathEl.querySelector("annotation");
    if (ann?.textContent) return ann.textContent;
  }
  return null;
}

function latexToMathML(latex: string, displayMode: boolean): string {
  try {
    const html = katex.renderToString(latex, {
      output: "mathml",
      displayMode,
      throwOnError: false,
    });
    return html;
  } catch {
    return latex;
  }
}

const WORD_SAFE_PROPERTIES: string[] = [
  "color",
  "background-color",
  "font-size",
  "font-weight",
  "font-style",
  "font-family",
  "text-align",
  "text-decoration",
  "text-indent",
  "vertical-align",
  "line-height",
  "letter-spacing",
  "white-space",
  "margin-top",
  "margin-right",
  "margin-bottom",
  "margin-left",
  "padding-top",
  "padding-right",
  "padding-bottom",
  "padding-left",
  "border-top-width",
  "border-top-style",
  "border-top-color",
  "border-right-width",
  "border-right-style",
  "border-right-color",
  "border-bottom-width",
  "border-bottom-style",
  "border-bottom-color",
  "border-left-width",
  "border-left-style",
  "border-left-color",
  "border-collapse",
  "border-spacing",
  "width",
  "max-width",
  "min-width",
  "height",
  "display",
  "list-style-type",
  "table-layout",
  "word-wrap",
  "overflow-wrap",
  "word-break",
];

function isColorProperty(prop: string): boolean {
  return prop === "color" || prop.includes("color") || prop === "background-color";
}

function getSignificantStyles(el: HTMLElement): string {
  const computed = window.getComputedStyle(el);
  const parts: string[] = [];

  for (const prop of WORD_SAFE_PROPERTIES) {
    const value = computed.getPropertyValue(prop);
    if (!value || value === "normal" || value === "none" || value === "auto")
      continue;
    if (
      prop === "background-color" &&
      (value === "rgba(0, 0, 0, 0)" || value === "transparent")
    )
      continue;
    if (
      (prop.startsWith("margin") || prop.startsWith("padding")) &&
      value === "0px"
    )
      continue;
    if (prop.startsWith("border-") && prop.endsWith("-width") && value === "0px")
      continue;
    if (prop.startsWith("border-") && prop.endsWith("-style") && value === "none")
      continue;

    const finalValue = isColorProperty(prop) ? rgbToHex(value) : value;
    parts.push(`${prop}:${finalValue}`);
  }

  return parts.join(";");
}

function bakeComputedStyles(node: Node): Node {
  if (node.nodeType === Node.TEXT_NODE) {
    return node.cloneNode(true);
  }

  if (node.nodeType !== Node.ELEMENT_NODE) {
    return node.cloneNode(true);
  }

  const el = node as HTMLElement;
  const tag = el.tagName.toLowerCase();

  if (tag === "button" || tag === "script" || tag === "style") {
    return document.createTextNode("");
  }

  const clone = el.cloneNode(false) as HTMLElement;

  clone.removeAttribute("id");
  const attrsToRemove: string[] = [];
  for (const attr of Array.from(clone.attributes)) {
    if (attr.name.startsWith("data-")) attrsToRemove.push(attr.name);
  }
  attrsToRemove.forEach((a) => clone.removeAttribute(a));

  const inlineStyles = getSignificantStyles(el);
  if (inlineStyles) {
    clone.setAttribute("style", inlineStyles);
  }

  for (const child of Array.from(el.childNodes)) {
    const bakedChild = bakeComputedStyles(child);
    clone.appendChild(bakedChild);
  }

  return clone;
}

function buildWordCompatiblePreviewHtml(rootEl: HTMLElement): string {
  const clone = rootEl.cloneNode(true) as HTMLElement;

  clone.querySelectorAll(".copy-ignore").forEach((el) => el.remove());
  clone.querySelectorAll("button").forEach((btn) => btn.remove());

  const baked = bakeComputedStyles(clone) as HTMLElement;

  baked.querySelectorAll("table").forEach((table) => {
    const wordHtml = buildWordCompatibleHtml(table as HTMLTableElement);
    const wrapper = document.createElement("div");
    wrapper.innerHTML = wordHtml;
    table.replaceWith(wrapper.firstElementChild || wrapper);
  });

  baked.querySelectorAll("pre").forEach((pre) => {
    const div = document.createElement("div");
    div.style.cssText = pre.style.cssText;
    div.style.backgroundColor = T.bgCode;
    div.style.color = T.textInverse;
    div.style.padding = "16px";
    div.style.margin = "16px 0";
    div.style.borderRadius = "8px";
    div.style.fontFamily = "Consolas, Monaco, monospace";
    div.style.whiteSpace = "normal";

    const walker = document.createTreeWalker(pre, NodeFilter.SHOW_TEXT, null);
    const nodes: Text[] = [];
    let n;
    while ((n = walker.nextNode())) nodes.push(n as Text);

    nodes.forEach((node) => {
      const text = node.nodeValue || "";
      if (!text) return;

      const span = document.createElement("span");
      span.innerHTML = text.replace(/ /g, "&nbsp;").replace(/\n/g, "<br>");

      const frag = document.createDocumentFragment();
      Array.from(span.childNodes).forEach((c) => frag.appendChild(c));
      node.replaceWith(frag);
    });

    div.innerHTML = pre.innerHTML;
    pre.replaceWith(div);
  });

  baked.querySelectorAll("*").forEach((el) => el.removeAttribute("class"));

  return baked.innerHTML;
}

function shouldSkipForCopy(el: Element): boolean {
  if (el.classList.contains("copy-ignore")) return true;
  if (el.getAttribute("data-nocopy") === "true") return true;
  if (el.tagName.toLowerCase() === "button") return true;
  return false;
}

function extractCopyableText(rootEl: HTMLElement): string {
  const parts: string[] = [];

  function walk(node: Node) {
    if (node.nodeType === Node.TEXT_NODE) {
      parts.push(node.textContent || "");
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;

    const el = node as Element;

    if (shouldSkipForCopy(el)) return;

    const tag = el.tagName.toLowerCase();

    if (el.classList.contains("katex-display")) {
      const latex = getLatexFromKatexEl(el as HTMLElement);
      if (latex) {
        parts.push(`$$${latex}$$\n`);
        return;
      }
    }
    if (el.classList.contains("katex")) {
      const latex = getLatexFromKatexEl(el as HTMLElement);
      if (latex) {
        parts.push(`$${latex}$`);
        return;
      }
    }

    const blockTags = new Set([
      "p",
      "div",
      "h1",
      "h2",
      "h3",
      "h4",
      "h5",
      "h6",
      "li",
      "tr",
      "br",
      "pre",
      "blockquote",
    ]);
    if (tag === "br") {
      parts.push("\n");
      return;
    }

    for (const child of Array.from(el.childNodes)) walk(child);

    if (blockTags.has(tag)) parts.push("\n");
  }

  walk(rootEl);
  return parts
    .join("")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function serializeCopyableHTML(rootEl: HTMLElement): string {
  function serializeNode(node: Node): string {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent || "";
      return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return "";

    const el = node as HTMLElement;

    if (shouldSkipForCopy(el)) return "";

    const tag = el.tagName.toLowerCase();
    if (tag === "script" || tag === "style") return "";

    if (el.classList.contains("katex-display")) {
      const katexEl = el.querySelector(".katex") as HTMLElement | null;
      if (katexEl) {
        const latex = getLatexFromKatexEl(katexEl);
        if (latex) {
          const mathml = latexToMathML(latex, true);
          return `<div style="text-align:center;margin:12px 0;">${mathml}</div>`;
        }
      }
    }
    if (el.classList.contains("katex")) {
      const latex = getLatexFromKatexEl(el);
      if (latex) {
        const mathml = latexToMathML(latex, false);
        return `<span>${mathml}</span>`;
      }
    }

    if (tag === "table") {
      return buildWordCompatibleHtml(el as HTMLTableElement);
    }

    if (tag === "pre") {
      const text = el.innerText || el.textContent || "";
      const escaped = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/ /g, "&nbsp;")
        .replace(/\n/g, "<br>");
      return `<div style="background:${T.bgCode};color:${T.textInverse};padding:16px;margin:16px 0;border-radius:8px;font-family:Consolas,Monaco,monospace;">${escaped}</div>`;
    }

    const children = Array.from(el.childNodes).map(serializeNode).join("");

    const inlineTags = new Set([
      "span",
      "a",
      "strong",
      "b",
      "em",
      "i",
      "code",
      "sup",
      "sub",
      "u",
      "s",
      "del",
      "ins",
    ]);
    if (inlineTags.has(tag)) {
      const style = getSignificantStyles(el);
      return style ? `<span style="${style}">${children}</span>` : children;
    }

    const style = getSignificantStyles(el);
    const styleAttr = style ? ` style="${style}"` : "";
    const blockMap: Record<string, string> = {
      h1: "h1",
      h2: "h3",
      h3: "h3",
      h4: "h4",
      h5: "h5",
      h6: "h6",
      p: "p",
      ul: "ul",
      ol: "ol",
      li: "li",
      blockquote: "blockquote",
      table: "table",
      thead: "thead",
      tbody: "tbody",
      tr: "tr",
      th: "th",
      td: "td",
    };
    const outTag = blockMap[tag] || "div";
    return `<${outTag}${styleAttr}>${children}</${outTag}>`;
  }

  return Array.from(rootEl.childNodes).map(serializeNode).join("");
}

function buildWordCompatibleContentHtml(rootEl: HTMLElement): string {
  return serializeCopyableHTML(rootEl);
}

function buildPlainTextFromContent(rootEl: HTMLElement): string {
  return extractCopyableText(rootEl);
}

function showCopyToast(message = "서식 포함 복사 완료!") {
  document.querySelectorAll(".copy-toast-notify").forEach((el) => el.remove());
  const toast = document.createElement("div");
  toast.className = "copy-toast-notify";
  toast.textContent = message;
  Object.assign(toast.style, {
    position: "fixed",
    bottom: "32px",
    left: "50%",
    transform: "translateX(-50%) translateY(8px)",
    background: "#1e293b",
    color: "#f8fafc",
    padding: "10px 20px",
    borderRadius: "10px",
    fontSize: "13px",
    fontWeight: "500",
    fontFamily: "system-ui, sans-serif",
    boxShadow: "0 4px 16px rgba(0,0,0,0.25)",
    zIndex: "99999",
    pointerEvents: "none",
    opacity: "0",
    transition: "opacity 0.2s ease, transform 0.2s ease",
  });
  document.body.appendChild(toast);
  requestAnimationFrame(() =>
    requestAnimationFrame(() => {
      toast.style.opacity = "1";
      toast.style.transform = "translateX(-50%) translateY(0)";
    })
  );
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(-50%) translateY(8px)";
    setTimeout(() => toast.remove(), 250);
  }, 2000);
}

export function copyContentAsFormatted(rootEl: HTMLElement) {
  const htmlContent = buildWordCompatibleContentHtml(rootEl);
  const plainText = buildPlainTextFromContent(rootEl);

  const wrappedHtml = wrapWithStandardHtml(htmlContent);

  const clipboardItem = new ClipboardItem({
    "text/plain": new Blob([plainText], { type: "text/plain" }),
    "text/html": new Blob([wrappedHtml], { type: "text/html" }),
  });

  navigator.clipboard.write([clipboardItem]).then(() => {
    showCopyToast("서식 포함 복사 완료! ✓");
  });
}

export function copyPreviewAsFormatted(rootEl: HTMLElement) {
  const htmlContent = buildWordCompatiblePreviewHtml(rootEl);

  const cloneTextOnly = rootEl.cloneNode(true) as HTMLElement;
  cloneTextOnly
    .querySelectorAll(".copy-ignore")
    .forEach((el) => el.remove());
  cloneTextOnly.querySelectorAll("button").forEach((btn) => btn.remove());
  const plainText =
    cloneTextOnly.innerText || cloneTextOnly.textContent || "";

  const wrappedHtml = wrapWithStandardHtml(htmlContent);

  const clipboardItem = new ClipboardItem({
    "text/plain": new Blob([plainText], { type: "text/plain" }),
    "text/html": new Blob([wrappedHtml], { type: "text/html" }),
  });

  navigator.clipboard.write([clipboardItem]);
}

const HoverCopyButton: FC<{
  visible: boolean;
  copied: boolean;
  onClick: () => void;
  dark?: boolean;
}> = ({ visible, copied, onClick, dark = false }) => {
  if (!visible && !copied) return null;

  return (
    <button
      onClick={onClick}
      style={{
        position: "absolute",
        top: 6,
        right: 6,
        zIndex: 10,
        padding: "4px 10px",
        fontSize: 11,
        fontWeight: 500,
        border: `1px solid ${dark ? "rgba(255,255,255,0.25)" : T.border}`,
        borderRadius: 6,
        background: copied ? "#10b981" : "#ffffff",
        color: copied ? "#ffffff" : T.textSecondary,
        cursor: "pointer",
        transition: "all 0.15s ease",
        display: "flex",
        alignItems: "center",
        gap: 4,
        boxShadow: dark
          ? "0 1px 6px rgba(0,0,0,0.4)"
          : "0 1px 4px rgba(0,0,0,0.08)",
      }}
    >
      {copied ? (
        <>
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
          Copied
        </>
      ) : (
        <>
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
          </svg>
          Copy
        </>
      )}
    </button>
  );
};

/* ────────────────── CopyableCodeBlock (일반 코드 블록) ────────────── */
const CopyableCodeBlock: FC<{
  children: React.ReactNode;
  className?: string;
  language?: string;
  preProps?: any;
  code?: string;
  isPreviewable?: boolean;
}> = ({ children, className, language, preProps, code, isPreviewable }) => {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [showPreview, setShowPreview] = useState(!!isPreviewable);

  const handleCopy = useCallback(() => {
    if (showPreview && code) {
      navigator.clipboard.writeText(code);
    } else {
      const pre = wrapperRef.current?.querySelector("pre");
      if (!pre) return;
      const text = pre.innerText || pre.textContent || "";
      navigator.clipboard.writeText(text);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [showPreview, code]);

  const previewHtml = useMemo(
    () => (isPreviewable && code ? renderPreviewHtml(code, language || "") : ""),
    [isPreviewable, code, language]
  );

  const inPreview = showPreview && isPreviewable;

  return (
    <div
      ref={wrapperRef}
      className="copy-ignore"
      data-nocopy="true"
      style={{
        position: "relative",
        margin: "16px 0",
        borderRadius: T.radius,
        border: `1px solid ${inPreview ? T.border : T.borderCode}`,
        overflow: "hidden",
        background: inPreview ? T.bg : T.bgCode,
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* 호버 버튼 영역 */}
      <div
        style={{
          position: "absolute",
          top: 6,
          right: 6,
          zIndex: 10,
          display: "flex",
          gap: 4,
          opacity: hovered || copied ? 1 : 0,
          transition: "opacity 0.15s ease",
          pointerEvents: hovered || copied ? "auto" : "none",
        }}
      >
        {isPreviewable && (
          <button
            onClick={() => setShowPreview((v) => !v)}
            style={{
              padding: "4px 10px",
              fontSize: 11,
              fontWeight: 500,
              border: `1px solid ${inPreview ? T.border : "rgba(255,255,255,0.25)"}`,
              borderRadius: 6,
              background: "#ffffff",
              color: T.textSecondary,
              cursor: "pointer",
              transition: "all 0.15s ease",
              display: "flex",
              alignItems: "center",
              gap: 4,
              boxShadow: inPreview
                ? "0 1px 4px rgba(0,0,0,0.08)"
                : "0 1px 6px rgba(0,0,0,0.4)",
            }}
          >
            {inPreview ? "Code" : "Preview"}
          </button>
        )}
        <button
          onClick={handleCopy}
          style={{
            padding: "4px 10px",
            fontSize: 11,
            fontWeight: 500,
            border: `1px solid ${
              copied ? "transparent" : inPreview ? T.border : "rgba(255,255,255,0.25)"
            }`,
            borderRadius: 6,
            background: copied ? "#10b981" : "#ffffff",
            color: copied ? "#ffffff" : T.textSecondary,
            cursor: "pointer",
            transition: "all 0.15s ease",
            display: "flex",
            alignItems: "center",
            gap: 4,
            boxShadow: inPreview
              ? "0 1px 4px rgba(0,0,0,0.08)"
              : "0 1px 6px rgba(0,0,0,0.4)",
          }}
        >
          {copied ? (
            <>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Copied
            </>
          ) : (
            <>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
              Copy
            </>
          )}
        </button>
      </div>

      {inPreview ? (
        <div
          className="renderable-preview"
          style={{
            padding: 16,
            overflowX: "auto",
            background: T.bg,
            fontSize: 14,
            lineHeight: 1.7,
          }}
          dangerouslySetInnerHTML={{ __html: previewHtml }}
        />
      ) : (
        <pre
          {...preProps}
          style={{
            margin: 0,
            padding: 16,
            background: T.bgCode,
            color: T.textInverse,
            fontSize: 13,
            lineHeight: 1.7,
            overflowX: "auto",
            fontFamily: T.mono,
          }}
        >
          <code className={className}>{children}</code>
        </pre>
      )}
    </div>
  );
};

/* ──────────────────────────────────────────────────────────────────── */
/* ✅ 변경: CopyableTableWrapper – useEffect DOM 조작 완전 제거       */
/*    모든 테이블 스타일은 SHARED_TABLE_CSS의 .md-table-wrapper 규칙으로 처리 */
/* ──────────────────────────────────────────────────────────────────── */
const CopyableTableWrapper: FC<{
  children: React.ReactNode;
  tableProps?: any;
}> = ({ children, tableProps }) => {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);
  const [hovered, setHovered] = useState(false);

  // ✅ 변경: useEffect 완전 제거 — DOM 직접 조작 없음

  const handleCopy = useCallback(() => {
    const table = wrapperRef.current?.querySelector("table");
    if (!table) return;
    copyTableAsFormatted(table);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, []);

  return (
    <div
      ref={wrapperRef}
      className="md-table-wrapper" // ✅ 변경: CSS 클래스로 스타일 적용
      style={{ position: "relative" }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <HoverCopyButton
        visible={hovered}
        copied={copied}
        onClick={handleCopy}
      />

      <div
        style={{
          border: `1px solid ${T.borderCode}`,
          borderRadius: `${T.radius}px`,
          overflow: "hidden",
          background: T.bg,
        }}
      >
        <div
          style={{
            overflowX: "auto",
            WebkitOverflowScrolling: "touch",
          }}
        >
          <table
            {...tableProps}
            style={{
              width: "100%",
              borderCollapse: "separate",
              borderSpacing: 0,
              border: "none",
              borderRadius: 0,
              background: T.bg,
              margin: 0,
            }}
          >
            {children}
          </table>
        </div>
      </div>
    </div>
  );
};

/* ────────────────── RenderableCodeBlock ──────────────────────────── */
const RenderableCodeBlock: FC<{
  language: string;
  code: string;
  className?: string;
}> = memo(({ language, code, className }) => {
  const [showCode, setShowCode] = useState(false);
  const previewRef = useRef<HTMLDivElement>(null);
  const codeWrapperRef = useRef<HTMLDivElement>(null);
  const [codeHovered, setCodeHovered] = useState(false);
  const [codeCopied, setCodeCopied] = useState(false);

  const cleanedHtml = useMemo(() => {
    if (language !== "html") return "";
    let c = code;
    // <style> 보존 — 캘린더 등 신뢰 HTML의 scoped CSS 유지 (#{uniqueId} 접두사로 격리됨)
    const bodyMatch = c.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
    if (bodyMatch) {
      c = bodyMatch[1];
    } else {
      c = c
        .replace(/<!DOCTYPE[^>]*>/gi, "")
        .replace(/<\/?html[^>]*>/gi, "")
        .replace(/<head[^>]*>[\s\S]*?<\/head>/gi, "")
        .replace(/<\/?body[^>]*>/gi, "");
    }
    c = c.replace(/\s+border\s*=\s*["'][^"']*["']/gi, "");
    c = c.replace(/\s+cellpadding\s*=\s*["'][^"']*["']/gi, "");
    c = c.replace(/\s+cellspacing\s*=\s*["'][^"']*["']/gi, "");
    c = c.replace(/>\s+</g, "><");
    return c.trim();
  }, [code, language]);

  const renderedMarkdown = useMemo(() => {
    if (language !== "markdown" && language !== "md") return "";
    return (marked.parse(code) as string).trim();
  }, [code, language]);

  const renderedLatex = useMemo(() => {
    if (language !== "latex" && language !== "tex") return "";
    const renderMath = (latex: string, displayMode: boolean): string => {
      try {
        return katex.renderToString(latex, {
          displayMode,
          throwOnError: false,
          output: "htmlAndMathml",
        });
      } catch {
        return `<span style="color:#ef4444">${latex}</span>`;
      }
    };
    const tokens: {
      type: "display" | "inline" | "text";
      content: string;
    }[] = [];
    let remaining = code;
    while (remaining.length > 0) {
      const m1 = remaining.match(/^([\s\S]*?)\\\[([\s\S]*?)\\\]/);
      const m2 = remaining.match(/^([\s\S]*?)\$\$([\s\S]*?)\$\$/);
      const m3 = remaining.match(/^([\s\S]*?)\\\(([\s\S]*?)\\\)/);
      const candidates = [
        m1 ? { match: m1, type: "display" as const } : null,
        m2 ? { match: m2, type: "display" as const } : null,
        m3 ? { match: m3, type: "inline" as const } : null,
      ].filter(Boolean) as {
        match: RegExpMatchArray;
        type: "display" | "inline";
      }[];
      if (!candidates.length) {
        if (remaining.trim())
          tokens.push({ type: "text", content: remaining });
        break;
      }
      candidates.sort((a, b) => a.match[1].length - b.match[1].length);
      const best = candidates[0];
      if (best.match[1].trim())
        tokens.push({ type: "text", content: best.match[1] });
      tokens.push({ type: best.type, content: best.match[2].trim() });
      remaining = remaining.slice(best.match[0].length);
    }
    if (!tokens.length) return renderMath(code.trim(), true);
    return tokens
      .map((t) => {
        if (t.type === "display")
          return `<div style="text-align:center;padding:8px 0;overflow-x:auto;">${renderMath(t.content, true)}</div>`;
        if (t.type === "inline")
          return `<span>${renderMath(t.content, false)}</span>`;
        return `<span style="white-space:pre-wrap;">${t.content.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</span>`;
      })
      .join("");
  }, [code, language]);

  const previewHtml =
    language === "html"
      ? cleanedHtml
      : language === "latex" || language === "tex"
        ? renderedLatex
        : renderedMarkdown;
  const tableOnly = useMemo(() => isTableOnly(previewHtml), [previewHtml]);

  const handleCopyCode = useCallback(() => {
    navigator.clipboard.writeText(code);
    setCodeCopied(true);
    setTimeout(() => setCodeCopied(false), 2000);
  }, [code]);

  useEffect(() => {
    if (showCode || !previewRef.current) return;
    const tables = previewRef.current.querySelectorAll("table");
    tables.forEach((table) => {
      table.style.width = "100%";
      table.style.maxWidth = "100%";
      table.style.tableLayout = "auto";
      table.style.borderCollapse = "separate";
      table.style.borderSpacing = "0";
      table.style.border = "none";
      table.style.borderRadius = "0";
      table.style.background = T.bg;
      table.style.margin = "0";
      table.style.outline = "none";
      table.style.boxShadow = "none";

      const ths = table.querySelectorAll("th");
      ths.forEach((th) => {
        (th as HTMLElement).style.cssText = `
          background-color: ${T.bgTableHeader} !important;
          color: ${T.textTableHeader} !important;
          font-weight: 600;
          padding: 10px 14px;
          text-align: left;
          border: none;
          border-bottom: 2px solid ${T.borderTableHeader};
          font-size: 13px;
          white-space: nowrap;
        `;
      });

      const tds = table.querySelectorAll("td");
      tds.forEach((td) => {
        (td as HTMLElement).style.cssText = `
          padding: 10px 14px;
          text-align: left;
          vertical-align: top;
          border: none;
          border-bottom: 1px solid ${T.borderTable};
          color: ${T.textPrimary};
          font-size: 13px;
          white-space: normal;
          overflow-wrap: break-word;
          word-break: break-word;
        `;
      });

      const lastRow = table.querySelector(
        "tbody tr:last-child, tr:last-child"
      );
      if (lastRow) {
        lastRow.querySelectorAll("td").forEach((td) => {
          (td as HTMLElement).style.borderBottom = "none";
        });
      }
    });
  }, [showCode, previewHtml]);

  const TabButton: FC<{
    active: boolean;
    label: string;
    onClick: () => void;
  }> = ({ active, label, onClick }) => (
    <button
      onClick={onClick}
      style={{
        padding: "4px 12px",
        fontSize: 12,
        fontWeight: 600,
        borderRadius: T.radiusSm,
        border: "none",
        cursor: "pointer",
        background: active ? "#ffffff" : "transparent",
        color: active ? "#111827" : "#6b7280",
        boxShadow: active ? "0 1px 2px rgba(0,0,0,0.05)" : "none",
        transition: "all 0.15s ease",
      }}
    >
      {label}
    </button>
  );

  return (
    <div
      className={className || ""}
      style={{
        margin: "12px 0",
        background: "transparent",
      }}
    >
      <div
        ref={previewRef}
        className="renderable-preview"
        style={{
          overflowX: "auto",
          padding: 0,
          background: "transparent",
        }}
      >
        <div dangerouslySetInnerHTML={{ __html: previewHtml }} />
      </div>
    </div>
  );
});

/* ────────────────── ScrollFloatingButton (위/아래 이동) ────────────── */
type ScrollDirection = "top" | "bottom" | null;

const ScrollFloatingButton: FC<{
  containerRef: React.RefObject<HTMLDivElement>;
}> = ({ containerRef }) => {
  const [direction, setDirection] = useState<ScrollDirection>(null);
  const [buttonLeft, setButtonLeft] = useState("50%");
  const lastScrollTopRef = useRef(0);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const updatePosition = () => {
      const el = containerRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      setButtonLeft(`${rect.left + rect.width / 2}px`);
    };

    updatePosition();

    const resizeObserver = new ResizeObserver(updatePosition);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    window.addEventListener("resize", updatePosition);
    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", updatePosition);
    };
  }, [containerRef]);

  useEffect(() => {
    const checkScroll = () => {
      const scrollParent = containerRef.current;
      if (!scrollParent) return;

      const scrollTop = scrollParent.scrollTop;
      const scrollHeight = scrollParent.scrollHeight;
      const clientHeight = scrollParent.clientHeight;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
      const distanceFromTop = scrollTop;
      const prevScrollTop = lastScrollTopRef.current;
      lastScrollTopRef.current = scrollTop;

      const isScrollingDown = scrollTop > prevScrollTop;
      const isScrollingUp = scrollTop < prevScrollTop;
      const isFarFromBottom = distanceFromBottom > 150;
      const isFarFromTop = distanceFromTop > 150;

      if (isScrollingDown && isFarFromBottom) {
        setDirection("bottom");
        if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
        hideTimerRef.current = setTimeout(() => setDirection(null), 3000);
      } else if (isScrollingUp && isFarFromTop) {
        setDirection("top");
        if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
        hideTimerRef.current = setTimeout(() => setDirection(null), 3000);
      } else if (isScrollingDown && !isFarFromBottom) {
        setDirection(null);
        if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
      } else if (isScrollingUp && !isFarFromTop) {
        setDirection(null);
        if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
      }
    };

    const el = containerRef.current;
    if (!el) return;

    el.addEventListener("scroll", checkScroll);
    return () => {
      el.removeEventListener("scroll", checkScroll);
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    };
  }, [containerRef]);

  const handleClick = useCallback(() => {
    const scrollParent = containerRef.current;
    if (!scrollParent || !direction) return;

    const targetTop =
      direction === "bottom" ? scrollParent.scrollHeight : 0;
    scrollParent.scrollTo({ top: targetTop, behavior: "smooth" });
    setDirection(null);
  }, [containerRef, direction]);

  const visible = direction !== null;
  const isTop = direction === "top";

  return (
    <button
      onClick={handleClick}
      aria-label={isTop ? "Scroll to top" : "Scroll to bottom"}
      style={{
        position: "fixed",
        bottom: 80,
        left: buttonLeft,
        transform: `translateX(-50%) scale(${visible ? 1 : 0})`,
        zIndex: 9999,
        width: 36,
        height: 36,
        borderRadius: "50%",
        border: `1px solid ${T.border}`,
        background: T.bg,
        color: T.textSecondary,
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow:
          "0 4px 16px rgba(0,0,0,0.15), 0 2px 4px rgba(0,0,0,0.1)",
        transition:
          "transform 0.2s ease, opacity 0.2s ease, background 0.15s ease",
        opacity: visible ? 1 : 0,
        pointerEvents: visible ? "auto" : "none",
      }}
      onMouseEnter={(e) => {
        if (!visible) return;
        e.currentTarget.style.background = T.bgHover;
        e.currentTarget.style.color = T.textPrimary;
        e.currentTarget.style.transform = "translateX(-50%) scale(1.08)";
      }}
      onMouseLeave={(e) => {
        if (!visible) return;
        e.currentTarget.style.background = T.bg;
        e.currentTarget.style.color = T.textSecondary;
        e.currentTarget.style.transform = "translateX(-50%) scale(1)";
      }}
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{
          transition: "transform 0.2s ease",
          transform: isTop ? "rotate(180deg)" : "rotate(0deg)",
        }}
      >
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </button>
  );
};

/* ──────────── 공통 스타일 ───────────────────────────────── */
const SHARED_TABLE_CSS = `
  .wmde-markdown .copied,
  .wmde-markdown .code-copied,
  .wmde-markdown pre > .copied,
  .wmde-markdown [data-code-block-copy],
  .wmde-markdown pre > code + button,
  .wmde-markdown pre > button,
  .wmde-markdown pre > span[data-code],
  .wmde-markdown .wmde-markdown-copy-btn,
  .w-md-editor-preview .copied,
  .wmde-markdown pre > .copy-btn {
    display: none !important;
  }

  .wmde-markdown hr {
    border: none !important;
    border-top: 1px solid ${T.border} !important;
    height: 0 !important;
    margin: 20px 0 !important;
    background: transparent !important;
  }

  .renderable-preview hr {
    border: none;
    border-top: 1px solid ${T.border};
    height: 0;
    margin: 16px 0;
  }

  .renderable-preview table {
    border-collapse: separate !important;
    border-spacing: 0 !important;
    width: 100% !important;
    max-width: 100% !important;
    table-layout: auto !important;
    border: none !important;
    border-radius: 0 !important;
    background: ${T.bg} !important;
    margin: 0 !important;
    display: table;
    outline: none !important;
    box-shadow: none !important;
  }

  .renderable-preview thead th {
    background: ${T.bgTableHeader} !important;
    color: ${T.textTableHeader} !important;
    font-weight: 600;
    white-space: nowrap;
    border-bottom: 2px solid ${T.borderTableHeader} !important;
    border-top: none !important;
    border-left: none !important;
    border-right: none !important;
    padding: 10px 14px;
    font-size: 13px;
  }

  .renderable-preview th,
  .renderable-preview td {
    padding: 10px 14px;
    text-align: left;
    vertical-align: top;
    border: none !important;
    border-bottom: 1px solid ${T.borderTable} !important;
    color: ${T.textPrimary};
    font-size: 13px;
    line-height: 1.55;
  }

  .renderable-preview td {
    white-space: normal;
    overflow-wrap: break-word;
    word-break: break-word;
  }

  .renderable-preview tbody tr:last-child td { border-bottom: none !important; }
  .renderable-preview tbody tr:nth-child(even), .renderable-preview tbody tr:nth-child(odd) { background: ${T.bg}; }
  .renderable-preview tbody tr:hover { background: ${T.bgHover}; }
  .renderable-preview p { margin: 0 0 8px 0; }
  .renderable-preview p:last-child { margin-bottom: 0; }
  .renderable-preview ul, .renderable-preview ol { margin: 4px 0; padding-left: 20px; }
  .renderable-preview h1, .renderable-preview h2, .renderable-preview h3 { margin: 12px 0 6px 0; color: ${T.textPrimary}; }

  /* ✅ 변경: .md-table-wrapper CSS 규칙 추가 — useEffect DOM 조작 대체 */
  .md-table-wrapper table {
    border-collapse: separate !important;
    border-spacing: 0 !important;
    width: 100% !important;
    max-width: 100% !important;
    table-layout: auto !important;
    border: none !important;
    border-radius: 0 !important;
    background: ${T.bg} !important;
    margin: 0 !important;
    outline: none !important;
    box-shadow: none !important;
  }

  .md-table-wrapper th {
    background: ${T.bgTableHeader} !important;
    color: ${T.textTableHeader} !important;
    font-weight: 600 !important;
    white-space: nowrap !important;
    border: 1px solid ${T.borderTable} !important;
    border-bottom: 2px solid ${T.borderTableHeader} !important;
    padding: 10px 14px !important;
    font-size: 13px !important;
    text-align: left !important;
  }

  .md-table-wrapper td {
    border: 1px solid ${T.borderTable} !important;
    padding: 10px 14px !important;
    text-align: left !important;
    vertical-align: top !important;
    color: ${T.textPrimary} !important;
    font-size: 13px !important;
    white-space: normal !important;
    overflow-wrap: break-word !important;
    word-break: break-word !important;
  }

  .md-table-wrapper tbody tr:nth-child(even),
  .md-table-wrapper tbody tr:nth-child(odd) {
    background: ${T.bg};
  }

  .md-table-wrapper tbody tr:hover {
    background: ${T.bgHover};
  }
  /* ✅ 변경 끝 */

  .wmde-markdown table {
    border-collapse: separate !important;
    border-spacing: 0 !important;
    width: 100%;
    max-width: 100%;
    table-layout: auto;
    border: 1px solid ${T.borderTable} !important;
    border-radius: 0 !important;
    background: ${T.bg};
    margin: 0 !important;
    display: table;
    outline: none !important;
    box-shadow: none !important;
  }

  .wmde-markdown thead th {
    background: ${T.bgTableHeader} !important;
    color: ${T.textTableHeader} !important;
    font-weight: 600;
    white-space: nowrap;
    border: 1px solid ${T.borderTable} !important;
    border-bottom: 2px solid ${T.borderTableHeader} !important;
    padding: 10px 14px;
    font-size: 13px;
  }

  .wmde-markdown th, .wmde-markdown td {
    padding: 10px 14px;
    text-align: left;
    vertical-align: top;
    border: 1px solid ${T.borderTable} !important;
    color: ${T.textPrimary};
    font-size: 13px;
    line-height: 1.55;
  }

  .wmde-markdown td { white-space: normal; overflow-wrap: break-word; word-break: break-word; }
  .wmde-markdown tbody tr:nth-child(even), .wmde-markdown tbody tr:nth-child(odd) { background: ${T.bg}; }
  .wmde-markdown tbody tr:hover { background: ${T.bgHover}; }
`;

const VSCODE_DARK_PLUS_CSS = `
  .wmde-markdown pre { background: ${T.bgCode} !important; }
  .wmde-markdown pre code { color: ${T.textInverse} !important; }
  .wmde-markdown code[class*="language-"], .wmde-markdown pre[class*="language-"] { color: #d4d4d4 !important; background: ${T.bgCode} !important; }
  .wmde-markdown code[class*="language-"]::selection, .wmde-markdown pre[class*="language-"]::selection { background: #264F78 !important; }
  .wmde-markdown .token.doctype .token.doctype-tag { color: #569CD6 !important; }
  .wmde-markdown .token.doctype .token.name { color: #9cdcfe !important; }
  .wmde-markdown .token.comment, .wmde-markdown .token.prolog { color: #6a9955 !important; }
  .wmde-markdown .token.punctuation { color: #d4d4d4 !important; }
  .wmde-markdown .token.property, .wmde-markdown .token.tag, .wmde-markdown .token.boolean, .wmde-markdown .token.number, .wmde-markdown .token.constant, .wmde-markdown .token.symbol, .wmde-markdown .token.inserted, .wmde-markdown .token.unit { color: #b5cea8 !important; }
  .wmde-markdown .token.selector, .wmde-markdown .token.attr-name, .wmde-markdown .token.string, .wmde-markdown .token.char, .wmde-markdown .token.builtin, .wmde-markdown .token.deleted { color: #ce9178 !important; }
  .wmde-markdown .token.operator, .wmde-markdown .token.entity { color: #d4d4d4 !important; }
  .wmde-markdown .token.keyword { color: #569CD6 !important; }
  .wmde-markdown .token.function { color: #dcdcaa !important; }
  .wmde-markdown .token.class-name { color: #4ec9b0 !important; }
`;

/* ────────────────────── MarkdownViewer ───────────────────────────── */
const MarkdownViewer = memo(
  forwardRef<MarkdownViewerHandle, Props>(
    (
      {
        content,
        fontSize = "0.9rem",
        backgroundColor = "var(--basic-0)",
        maxLine,
      },
      ref
    ) => {
      const containerRef = useRef<HTMLDivElement>(null);

      useImperativeHandle(ref, () => ({
        copyContent: () => {
          if (!containerRef.current) return;
          const previewEl = containerRef.current.querySelector(
            ".wmde-markdown"
          ) as HTMLElement | null;
          if (!previewEl) return;
          copyContentAsFormatted(previewEl);
        },
      }));

      const sanitizedContent = useMemo(() => {
        if (!content) return "";
        let c = content.replace(/<reasoning>[\s\S]*?<\/reasoning>/gi, "");
        c = c.replace(/<\/?reasoning>/gi, "");
        c = c.replace(/<\/?answer>/gi, "");
        // HTML 엔티티 디코딩 (&#126; → ~, &#60; → < 등)
        c = c.replace(/&#(\d+);/g, (_, code) => String.fromCharCode(parseInt(code)));
        c = c.replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
        // ```코드블록``` 내부를 보호한 뒤 style 제거 (캘린더 등 신뢰 HTML의 스타일 보존)
        const codeBlockHolder: string[] = [];
        c = c.replace(/```(\w*)\s*\n([\s\S]*?)```/g, (match) => {
          codeBlockHolder.push(match);
          return `\x00CB${codeBlockHolder.length - 1}\x00`;
        });
        // 인라인 style 속성 제거 — 코드블록 외부만 적용
        c = c.replace(/(<[^>]*?)\s+style\s*=\s*(?:"[^"]*"|'[^']*')/gi, "$1");
        // 단일 ~ 이스케이프 — GFM singleTilde 취소선 해석 방지 (~~쌍틸드~~는 보존)
        // 코드블록이 플레이스홀더 상태일 때 적용하여 코드블록 내부 CSS ~ 보호
        c = c.replace(/(?<!~)~(?!~)/g, "\\~");
        // 코드블록 복원
        c = c.replace(/\x00CB(\d+)\x00/g, (_, idx) => codeBlockHolder[parseInt(idx)]);
        c = c.replace(/\\\[([\s\S]*?)\\\]/g, (_, e) => `$$${e}$$`);
        c = c.replace(/\\\(([\s\S]*?)\\\)/g, (_, e) => `$${e}$`);
        return c.trim();
      }, [content]);

      const codeBlockMap = useMemo(() => {
        const blocks = extractAllCodeBlocks(sanitizedContent);
        const map = new Map<string, string[]>();
        for (const b of blocks) {
          if (!map.has(b.lang)) map.set(b.lang, []);
          map.get(b.lang)!.push(b.code);
        }
        return map;
      }, [sanitizedContent]);

      const langCounterRef = useRef<Map<string, number>>(new Map());
      langCounterRef.current = new Map();

      const actualMaxDepth = useMemo(() => {
        if (!sanitizedContent) return 3;
        let max = 0;
        for (const line of sanitizedContent.split("\n")) {
          if (line.trim().startsWith("-")) {
            const depth =
              Math.floor((line.length - line.trimStart().length) / 2) + 1;
            if (depth > max) max = depth;
          }
        }
        return Math.max(max, 3);
      }, [sanitizedContent]);

      const generateListStyles = useMemo(() => {
        const styles = ["disc", "square", "circle"];
        let css = "";
        for (let d = 1; d <= actualMaxDepth; d++) {
          const sel =
            ".wmde-markdown " +
            (d === 1 ? "ul" : Array(d - 1).fill("li ul").join(" "));
          css += `${sel}{list-style-type:${styles[(d - 1) % 3]}!important;${d === 1 ? "padding-left:1.2em;margin:0.4em 0;" : ""}}`;
        }
        return css;
      }, [actualMaxDepth]);

      const clampStyles: React.CSSProperties = maxLine
        ? {
            height: `${maxLine * 20}px`,
            color: "#545E83",
            fontSize: 12,
            overflow: "hidden",
            textOverflow: "ellipsis",
            display: "-webkit-box",
            WebkitBoxOrient: "vertical",
            WebkitLineClamp: maxLine,
          }
        : {};

      const customComponents: Components = useMemo(
        () => ({
          end: () => null,
          answer: () => null,
          question: () => null,
          a: ({ href, children, ...props }) => {
            const isFileDownload =
              href && /\/api\/v1\/chat\/(hwpx|excel)\//.test(href);
            const handleClick = isFileDownload
              ? (e: React.MouseEvent) => {
                  e.preventDefault();
                  const fn = decodeURIComponent(
                    (href || "").split("/").pop() || "download"
                  );
                  fetch(href!)
                    .then((r) => {
                      if (!r.ok) throw new Error(`${r.status}`);
                      return r.blob();
                    })
                    .then((blob) => {
                      const url = URL.createObjectURL(blob);
                      const anchor = document.createElement("a");
                      anchor.href = url;
                      anchor.download = fn;
                      document.body.appendChild(anchor);
                      anchor.click();
                      document.body.removeChild(anchor);
                      URL.revokeObjectURL(url);
                    })
                    .catch((err) =>
                      console.error("File download error:", err)
                    );
                }
              : undefined;
            return (
              <a
                {...props}
                href={href}
                onClick={handleClick}
                style={{
                  cursor: "pointer",
                  color: T.textLink,
                  textDecoration: isFileDownload ? "none" : "underline",
                }}
              >
                {children}
              </a>
            );
          },
          code: ({ children, className, node, ...props }) => {
            const match = /language-(\w+)/.exec(className || "");
            const language = match ? match[1].toLowerCase() : "";
            let codeString = "";

            if (
              RENDERABLE_LANGUAGES.includes(language) &&
              codeBlockMap.has(language)
            ) {
              const arr = codeBlockMap.get(language)!;
              const counter = langCounterRef.current;
              const idx = counter.get(language) || 0;
              codeString = arr[idx] ?? "";
              counter.set(language, idx + 1);
            }

            if (!codeString) {
              const extractText = (n: any): string => {
                if (typeof n === "string") return n;
                if (typeof n === "number") return String(n);
                if (Array.isArray(n)) return n.map(extractText).join("");
                if (n?.props?.children) return extractText(n.props.children);
                return "";
              };
              codeString = extractText(children).replace(/\n$/, "");
            }

            const isBlock =
              (node?.position && codeString.includes("\n")) ||
              (className && className.startsWith("language-"));

            if (isBlock && RENDERABLE_LANGUAGES.includes(language)) {
              return (
                <RenderableCodeBlock
                  language={language}
                  code={codeString}
                  className={className}
                />
              );
            }
            if (isBlock) {
              const previewable = canPreview(codeString, language);
              return (
                <CopyableCodeBlock
                  className={className}
                  language={language}
                  code={codeString}
                  isPreviewable={previewable}
                >
                  {children}
                </CopyableCodeBlock>
              );
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            );
          },
          pre: ({ children, node, ...props }) => {
            const isMarkdownCodeBlock =
              node?.children?.length === 1 &&
              node.children[0].type === "element" &&
              node.children[0].tagName === "code";

            if (isMarkdownCodeBlock) {
              return <>{children}</>;
            }

            return <pre {...props}>{children}</pre>;
          },
          table: ({ children, node, ...props }) => (
            <CopyableTableWrapper tableProps={props}>
              {children}
            </CopyableTableWrapper>
          ),
        }),
        [codeBlockMap]
      );

      return (
        <div ref={containerRef} style={{ position: "relative" }}>
          <style>{SHARED_TABLE_CSS}</style>
          <style>{VSCODE_DARK_PLUS_CSS}</style>
          <style>{generateListStyles}</style>
          <style>{`
            .wmde-markdown .katex-display { overflow-x: auto; overflow-y: hidden; padding: 8px 0; }
            .wmde-markdown .katex { font-size: 1em; color: ${T.textPrimary}; }
            .renderable-preview .katex { font-size: 1.15em; color: ${T.textPrimary}; }
            .renderable-preview .katex * { color: inherit; }
            .renderable-preview .katex-display { overflow-x: auto; text-align: center; padding: 8px 0; }
          `}</style>

          <MarkdownPreview
            source={sanitizedContent}
            style={{
              padding: 10,
              fontSize,
              width: "100%",
              maxWidth: "100%",
              backgroundColor,
              overflowWrap: "break-word",
              ...clampStyles,
            }}
            remarkPlugins={[remarkMath]}
            rehypePlugins={[rehypeKatex]}
            components={customComponents}
          />
        </div>
      );
    }
  )
);

export { ScrollFloatingButton };
export default MarkdownViewer;
