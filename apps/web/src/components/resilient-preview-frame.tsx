"use client";

import { useContext, useEffect, useRef, useState } from "react";

import { ArticlePreviewModeContext } from "@/components/article-preview-viewport";
import { PREVIEW_NORMALIZATION_CSS, PREVIEW_PROFILES } from "@/lib/preview-profiles";
import type {
  ContentEditorBlock,
  ContentEditorDocument,
  EditableContentValue,
} from "@/lib/types";

type Props = {
  editable?: boolean;
  editorDocument?: ContentEditorDocument | null;
  onEditingChange?: (editing: boolean) => void;
  onSave?: (target: PreviewEditTarget, content: EditableContentValue) => Promise<void>;
  onSaveStateChange?: (state: InlineSaveState, message?: string) => void;
  src: string;
  title: string;
};

export type PreviewEditTarget =
  | { kind: "title" }
  | { kind: "blocks"; blockIds: string[] };

export type InlineSaveState = "idle" | "editing" | "saving" | "saved" | "error";

type EditableGroup = {
  block?: ContentEditorBlock;
  elements: HTMLElement[];
  key: string;
  target: PreviewEditTarget;
};

type EditableSurface = "box" | "inline";

type EditorCallbacks = {
  onEditingChange?: (editing: boolean) => void;
  onSave?: (target: PreviewEditTarget, content: EditableContentValue) => Promise<void>;
  onSaveStateChange?: (state: InlineSaveState, message?: string) => void;
};

function withRetryToken(src: string, retry: number): string {
  if (!retry) return src;
  const [withoutHash, hash = ""] = src.split("#", 2);
  const separator = withoutHash.includes("?") ? "&" : "?";
  return `${withoutHash}${separator}preview_retry=${retry}${hash ? `#${hash}` : ""}`;
}

function previewHash(src: string): string {
  try {
    return new URL(src, "http://workbench.local").hash;
  } catch {
    return "";
  }
}

const PROOF_FONT_SCALE = PREVIEW_PROFILES.proof.font_scale;
const inlineEditorCleanups = new WeakMap<Document, () => void>();

function normalizedText(value: string): string {
  return value.replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
}

function renderedText(value: string): string {
  return normalizedText(
    value
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/__([^_]+)__/g, "$1")
      .replace(/\[([^\]]+)]\([^)]+\)/g, "$1")
      .replace(/\\([\\`*_[\]{}()#+\-.!])/g, "$1"),
  );
}

function elementDepth(element: Element, root: Element): number {
  let depth = 0;
  let current: Element | null = element;
  while (current && current !== root) {
    depth += 1;
    current = current.parentElement;
  }
  return depth;
}

const INLINE_EDITABLE_TAGS = new Set([
  "A",
  "B",
  "BR",
  "CODE",
  "EM",
  "I",
  "MARK",
  "S",
  "SMALL",
  "SPAN",
  "STRONG",
  "SUB",
  "SUP",
  "U",
]);

function isInlineEditableNode(node: Node): boolean {
  return node.nodeType === 3
    || (node.nodeType === 1 && INLINE_EDITABLE_TAGS.has((node as HTMLElement).tagName));
}

function createInlineFragment(parent: HTMLElement): HTMLElement {
  const wrapper = parent.ownerDocument.createElement("span");
  wrapper.dataset.workbenchInlineFragment = "";
  wrapper.dataset.workbenchInlineFrame = parent.tagName === "BLOCKQUOTE" ? "block" : "inline";
  return wrapper;
}

function wrapMatchingInlineRun(root: HTMLElement, value: string): HTMLElement | null {
  const expected = renderedText(value);
  if (!expected) return null;
  const parents = [root, ...Array.from(root.querySelectorAll<HTMLElement>("*"))]
    .filter((element) => !element.closest("[data-theme-static]"))
    .sort((left, right) => elementDepth(right, root) - elementDepth(left, root));

  for (const parent of parents) {
    const children = Array.from(parent.childNodes);
    for (const child of children) {
      if (child.nodeType !== 3) continue;
      const text = child.textContent ?? "";
      const needle = [value, expected].find((candidate) => candidate && text.includes(candidate));
      if (!needle) continue;
      const start = text.indexOf(needle);
      const matched = (child as Text).splitText(start);
      matched.splitText(needle.length);
      const wrapper = createInlineFragment(parent);
      parent.insertBefore(wrapper, matched);
      wrapper.appendChild(matched);
      return wrapper;
    }
    for (let start = 0; start < children.length; start += 1) {
      if (!isInlineEditableNode(children[start])) continue;
      let combined = "";
      for (let end = start; end < children.length; end += 1) {
        const node = children[end];
        if (!isInlineEditableNode(node)) break;
        combined += node.textContent ?? "";
        const normalized = normalizedText(combined);
        if (normalized === expected) {
          const wrapper = createInlineFragment(parent);
          parent.insertBefore(wrapper, children[start]);
          children.slice(start, end + 1).forEach((child) => wrapper.appendChild(child));
          return wrapper;
        }
        if (normalized.length > expected.length) break;
      }
    }
  }
  return null;
}

function findTextElement(root: HTMLElement, value: string, used: Set<HTMLElement>): HTMLElement | null {
  const expected = renderedText(value);
  if (!expected) return null;
  const allowed = new Set(["P", "STRONG", "H1", "H2", "H3", "H4", "H5", "H6", "LI", "TD", "TH", "BLOCKQUOTE", "SPAN"]);
  const candidates = [root, ...Array.from(root.querySelectorAll<HTMLElement>("p,strong,h1,h2,h3,h4,h5,h6,li,td,th,blockquote,span"))]
    .filter((element) => !used.has(element) && allowed.has(element.tagName))
    .filter((element) => !element.closest("[data-theme-static]"))
    .filter((element) => normalizedText(element.textContent ?? "") === expected)
    .sort((left, right) => Number(right.hasAttribute("data-theme-field")) - Number(left.hasAttribute("data-theme-field")) || elementDepth(right, root) - elementDepth(left, root));
  return candidates[0] ?? wrapMatchingInlineRun(root, value);
}

function markdownFromNode(node: Node): string {
  if (node.nodeType === 3) return (node.textContent ?? "").replace(/\u00a0/g, " ");
  if (node.nodeType !== 1) return "";
  const element = node as HTMLElement;
  if (element.tagName === "BR") return "\n";
  const content = Array.from(element.childNodes).map(markdownFromNode).join("");
  if (element.matches("strong,b")) return `**${content}**`;
  if (element.matches("em,i")) return `*${content}*`;
  if (element.matches("a[href]")) return `[${content}](${element.getAttribute("href")})`;
  if (element.matches("div,p") && element.parentElement?.isContentEditable) return `${content}\n`;
  return content;
}

function editableValue(element: HTMLElement): string {
  return Array.from(element.childNodes).map(markdownFromNode).join("").replace(/\r/g, "").trim();
}

function groupValue(group: EditableGroup): EditableContentValue {
  if (!group.block || typeof group.block.content === "string") return editableValue(group.elements[0]);
  if (group.block.type === "table" && group.block.content.every(Array.isArray)) {
    const rows = group.block.content as string[][];
    let cursor = 0;
    return rows.map((row) => row.map(() => editableValue(group.elements[cursor++])));
  }
  return group.elements.map(editableValue);
}

function labelForGroup(group: EditableGroup, index: number): string {
  if (!group.block) return "直接编辑文章标题";
  const suffix = group.elements.length > 1 ? `第 ${index + 1} 项` : "";
  const labels: Record<ContentEditorBlock["type"], string> = {
    heading: "小标题",
    paragraph: "正文段落",
    quote: "引用内容",
    source: "来源说明",
    ordered_list: "编号列表",
    unordered_list: "项目列表",
    reference_list: "参考来源",
    table: "表格内容",
  };
  return `直接编辑${labels[group.block.type]}${suffix}`;
}

function discoverEditableGroups(document: Document, editorDocument: ContentEditorDocument): EditableGroup[] {
  const groups: EditableGroup[] = [];
  const title = document.querySelector<HTMLElement>("[data-editor-title='true']");
  if (title) groups.push({ elements: [title], key: "title", target: { kind: "title" } });

  const wrappers = Array.from(document.querySelectorAll<HTMLElement>("[data-editor-block-ids]"));
  const wrapperByBlock = new Map<string, HTMLElement>();
  wrappers.forEach((wrapper) => {
    (wrapper.dataset.editorBlockIds ?? "").split(",").filter(Boolean).forEach((blockId) => {
      wrapperByBlock.set(blockId, wrapper);
    });
  });

  const usedByWrapper = new WeakMap<HTMLElement, Set<HTMLElement>>();
  editorDocument.blocks.forEach((block) => {
    const wrapper = wrapperByBlock.get(block.block_id);
    if (!wrapper) return;
    const used = usedByWrapper.get(wrapper) ?? new Set<HTMLElement>();
    usedByWrapper.set(wrapper, used);
    const values = typeof block.content === "string"
      ? [block.content]
      : block.type === "table" && block.content.every(Array.isArray)
        ? (block.content as string[][]).flat()
        : block.content as string[];
    const elements: HTMLElement[] = [];
    for (const value of values) {
      const element = findTextElement(wrapper, value, used);
      if (!element) return;
      used.add(element);
      elements.push(element);
    }
    if (elements.length === values.length) {
      groups.push({
        block,
        elements,
        key: `block:${block.block_id}`,
        target: { kind: "blocks", blockIds: [block.block_id] },
      });
    }
  });
  return groups;
}

function editableSurfaceFor(element: HTMLElement): EditableSurface {
  if (element.dataset.workbenchInlineFrame === "inline") return "inline";
  if (element.dataset.workbenchInlineFrame === "block") return "box";
  const display = element.ownerDocument.defaultView?.getComputedStyle(element).display;
  return display === "inline" ? "inline" : "box";
}

function recordEditorContractCoverage(
  document: Document,
  editorDocument: ContentEditorDocument,
  groups: EditableGroup[],
): void {
  const mappedBlockIds = new Set(
    groups.flatMap((group) => group.block ? [group.block.block_id] : []),
  );
  const missingBlockIds = editorDocument.blocks
    .filter((block) => !(block.type === "heading" && block.level === 1))
    .map((block) => block.block_id)
    .filter((blockId) => !mappedBlockIds.has(blockId));
  const titleMapped = groups.some((group) => group.target.kind === "title");
  const coverageComplete = titleMapped && missingBlockIds.length === 0;
  document.documentElement.dataset.workbenchEditorContract = coverageComplete ? "complete" : "incomplete";
  if (missingBlockIds.length) {
    document.documentElement.dataset.workbenchEditorMissingBlocks = missingBlockIds.join(",");
  } else {
    delete document.documentElement.dataset.workbenchEditorMissingBlocks;
  }
  if (!coverageComplete) {
    console.warn("[workbench-editor-contract] Editable content coverage is incomplete.", {
      missingBlockIds,
      titleMapped,
    });
  }
}

function installInlineEditor(document: Document, editorDocument: ContentEditorDocument, callbacks: EditorCallbacks): () => void {
  const groups = discoverEditableGroups(document, editorDocument);
  recordEditorContractCoverage(document, editorDocument, groups);
  const groupByElement = new Map<HTMLElement, EditableGroup>();
  const timers = new Map<string, number>();
  const pending = new Map<string, { group: EditableGroup; value: EditableContentValue }>();
  let sequence = Promise.resolve();
  let savedIndicator = 0;
  let disposed = false;

  const report = (state: InlineSaveState, message?: string) => {
    if (!disposed) callbacks.onSaveStateChange?.(state, message);
  };

  const runSave = (group: EditableGroup, value: EditableContentValue) => {
    pending.delete(group.key);
    report("saving");
    sequence = sequence
      .catch(() => undefined)
      .then(() => callbacks.onSave?.(group.target, value))
      .then(() => {
        report("saved");
        window.clearTimeout(savedIndicator);
        savedIndicator = window.setTimeout(() => report("editing"), 1400);
      })
      .catch((reason: Error) => {
        report("error", reason.message || "自动保存失败");
      });
  };

  const scheduleSave = (group: EditableGroup) => {
    const value = groupValue(group);
    pending.set(group.key, { group, value });
    const existing = timers.get(group.key);
    if (existing !== undefined) window.clearTimeout(existing);
    report("editing");
    timers.set(group.key, window.setTimeout(() => {
      timers.delete(group.key);
      runSave(group, value);
    }, 650));
  };

  const flushPending = async () => {
    const queued = Array.from(pending.values());
    timers.forEach((timer) => window.clearTimeout(timer));
    timers.clear();
    queued.forEach(({ group, value }) => runSave(group, value));
    await sequence;
  };

  groups.forEach((group) => {
    group.elements.forEach((element, index) => {
      element.contentEditable = "true";
      element.spellcheck = false;
      element.dataset.workbenchInlineEditor = group.key;
      element.dataset.workbenchEditSurface = editableSurfaceFor(element);
      if (group.block) element.dataset.workbenchInlineBlockId = group.block.block_id;
      element.setAttribute("aria-label", labelForGroup(group, index));
      element.setAttribute("role", "textbox");
      element.tabIndex = 0;
      groupByElement.set(element, group);
    });
  });

  const onFocusIn = (event: Event) => {
    const target = (event.target as Element | null)?.closest?.("[data-workbench-inline-editor]") as HTMLElement | null;
    if (!target) return;
    callbacks.onEditingChange?.(true);
    report("editing");
  };
  const onFocusOut = () => {
    window.setTimeout(async () => {
      if ((document.activeElement as Element | null)?.closest?.("[data-workbench-inline-editor]")) return;
      await flushPending();
      callbacks.onEditingChange?.(false);
      report("idle");
    }, 0);
  };
  const onInput = (event: Event) => {
    const target = (event.target as Element | null)?.closest?.("[data-workbench-inline-editor]") as HTMLElement | null;
    const group = target ? groupByElement.get(target) : undefined;
    if (group) scheduleSave(group);
  };
  const onPaste = (event: ClipboardEvent) => {
    const target = (event.target as Element | null)?.closest?.("[data-workbench-inline-editor]");
    if (!target) return;
    event.preventDefault();
    document.execCommand("insertText", false, event.clipboardData?.getData("text/plain") ?? "");
  };
  const onClick = (event: Event) => {
    const target = (event.target as Element | null)?.closest?.("[data-workbench-inline-editor]");
    if (target && (event.target as Element | null)?.closest?.("a")) event.preventDefault();
  };
  const onKeyDown = (event: KeyboardEvent) => {
    const target = (event.target as Element | null)?.closest?.("[data-workbench-inline-editor]") as HTMLElement | null;
    if (!target) return;
    const group = groupByElement.get(target);
    if (event.key === "Escape") {
      event.preventDefault();
      target.blur();
    }
    if (event.key === "Enter" && !event.shiftKey && (!group?.block || group.block.type === "heading")) {
      event.preventDefault();
      target.blur();
    }
  };

  document.addEventListener("focusin", onFocusIn);
  document.addEventListener("focusout", onFocusOut);
  document.addEventListener("input", onInput);
  document.addEventListener("paste", onPaste);
  document.addEventListener("click", onClick);
  document.addEventListener("keydown", onKeyDown);

  return () => {
    const runtimeFragments = Array.from(
      document.querySelectorAll<HTMLElement>("[data-workbench-inline-fragment]"),
    );
    const queued = Array.from(pending.values());
    timers.forEach((timer) => window.clearTimeout(timer));
    timers.clear();
    queued.forEach(({ group, value }) => runSave(group, value));
    callbacks.onEditingChange?.(false);
    disposed = true;
    document.removeEventListener("focusin", onFocusIn);
    document.removeEventListener("focusout", onFocusOut);
    document.removeEventListener("input", onInput);
    document.removeEventListener("paste", onPaste);
    document.removeEventListener("click", onClick);
    document.removeEventListener("keydown", onKeyDown);
    window.clearTimeout(savedIndicator);
    groups.forEach((group) => group.elements.forEach((element) => {
      element.removeAttribute("contenteditable");
      element.removeAttribute("data-workbench-inline-editor");
      element.removeAttribute("data-workbench-inline-block-id");
      element.removeAttribute("data-workbench-edit-surface");
      element.removeAttribute("aria-label");
      element.removeAttribute("role");
      element.removeAttribute("tabindex");
    }));
    runtimeFragments.forEach((fragment) => {
      fragment.replaceWith(...Array.from(fragment.childNodes));
    });
    delete document.documentElement.dataset.workbenchEditorContract;
    delete document.documentElement.dataset.workbenchEditorMissingBlocks;
  };
}

function applyWorkbenchPreviewProfile(
  frame: HTMLIFrameElement,
  mode: "proof" | "mobile",
  editable: boolean,
  editorDocument: ContentEditorDocument | null | undefined,
  callbacks: EditorCallbacks,
) {
  let document: Document | null;
  try {
    document = frame.contentDocument;
  } catch {
    return;
  }
  if (!document?.documentElement) return;

  let normalization = document.querySelector<HTMLStyleElement>("style[data-workbench-preview-normalization]");
  if (!normalization) {
    normalization = document.createElement("style");
    normalization.dataset.workbenchPreviewNormalization = "";
    normalization.textContent = PREVIEW_NORMALIZATION_CSS;
    document.head?.append(normalization);
  }

  document.documentElement.dataset.workbenchPreviewMode = mode;
  document.documentElement.dataset.workbenchEditable = editable && mode === "proof" ? "true" : "false";
  let editorStyle = document.querySelector<HTMLStyleElement>("style[data-workbench-editor-style]");
  if (!editorStyle) {
    editorStyle = document.createElement("style");
    editorStyle.dataset.workbenchEditorStyle = "";
    editorStyle.textContent = `
      html[data-workbench-editable="true"] { --workbench-editor-hover:rgba(143,214,206,.10); --workbench-editor-focus:rgba(143,214,206,.18); }
      html[data-workbench-editable="true"] [data-workbench-inline-editor] { cursor:text; caret-color:#117C73; transition:outline-color .16s ease, background-color .16s ease, box-shadow .16s ease; }
      html[data-workbench-editable="true"] [data-workbench-edit-surface="box"]:hover { outline:2px solid rgba(17,124,115,.48); outline-offset:4px; background-color:var(--workbench-editor-hover)!important; }
      html[data-workbench-editable="true"] [data-workbench-edit-surface="box"]:focus { outline:2px solid #117C73; outline-offset:4px; background-color:var(--workbench-editor-focus)!important; box-shadow:0 0 0 5px rgba(143,214,206,.12); }
      html[data-workbench-editable="true"] [data-workbench-inline-frame="block"] { display:block; }
      html[data-workbench-editable="true"] [data-workbench-edit-surface="inline"]:hover,
      html[data-workbench-editable="true"] [data-workbench-edit-surface="inline"]:focus { outline:none!important; background-color:transparent!important; box-shadow:none!important; }
      html[data-workbench-editable="true"] *:has(> [data-workbench-edit-surface="inline"]:hover) { outline:2px solid rgba(17,124,115,.48); outline-offset:4px; background-color:var(--workbench-editor-hover)!important; }
      html[data-workbench-editable="true"] *:has(> [data-workbench-edit-surface="inline"]:focus) { outline:2px solid #117C73; outline-offset:4px; background-color:var(--workbench-editor-focus)!important; box-shadow:0 0 0 5px rgba(143,214,206,.12); }
      html[data-workbench-editable="true"] [data-workbench-inline-editor]::selection,
      html[data-workbench-editable="true"] [data-workbench-inline-editor] *::selection { background:#BFE9E3; color:#102421; }
    `;
    document.head?.append(editorStyle);
  }

  inlineEditorCleanups.get(document)?.();
  inlineEditorCleanups.delete(document);
  if (editable && mode === "proof" && editorDocument && callbacks.onSave) {
    const cleanup = installInlineEditor(document, editorDocument, callbacks);
    inlineEditorCleanups.set(document, cleanup);
  }

  document.querySelectorAll<HTMLElement>("[style]").forEach((element) => {
    if (!element.dataset.workbenchOriginalFontSize) {
      const original = element.style.fontSize;
      if (!original || !original.endsWith("px")) return;
      element.dataset.workbenchOriginalFontSize = original;
    }
    const original = element.dataset.workbenchOriginalFontSize;
    if (!original) return;
    if (mode === "proof") {
      const pixels = Number.parseFloat(original);
      element.style.fontSize = pixels > 0 ? `${Math.round(pixels * PROOF_FONT_SCALE * 100) / 100}px` : original;
    } else {
      element.style.fontSize = original;
    }
  });
}

export function ResilientPreviewFrame({
  editable = false,
  editorDocument,
  onEditingChange,
  onSave,
  onSaveStateChange,
  src,
  title,
}: Props) {
  const previewMode = useContext(ArticlePreviewModeContext);
  const [retry, setRetry] = useState(0);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const retryRef = useRef(0);
  const loadVersionRef = useRef(0);
  const frameRef = useRef<HTMLIFrameElement>(null);
  const lastScrollTopRef = useRef(0);
  const restoreScrollTopRef = useRef<number | null>(null);
  const previousSrcRef = useRef(src);
  const scrollCleanupRef = useRef<(() => void) | null>(null);
  const editorDocumentRef = useRef(editorDocument);
  const callbacksRef = useRef<EditorCallbacks>({ onEditingChange, onSave, onSaveStateChange });
  editorDocumentRef.current = editorDocument;
  callbacksRef.current = {
    onEditingChange: (editing) => {
      if (!editing) captureFrameScroll();
      onEditingChange?.(editing);
    },
    onSave,
    onSaveStateChange,
  };

  useEffect(() => {
    const previousSrc = previousSrcRef.current;
    if (previousSrc !== src) {
      const previousHash = previewHash(previousSrc);
      const nextHash = previewHash(src);
      const intentionalAnchorNavigation = Boolean(nextHash && nextHash !== previousHash);
      restoreScrollTopRef.current = intentionalAnchorNavigation ? null : lastScrollTopRef.current;
      previousSrcRef.current = src;
    }
    loadVersionRef.current += 1;
    retryRef.current = 0;
    setRetry(0);
    setLoading(true);
    setFailed(false);
  }, [src]);

  useEffect(() => () => {
    scrollCleanupRef.current?.();
    scrollCleanupRef.current = null;
  }, []);

  useEffect(() => {
    if (frameRef.current) {
      applyWorkbenchPreviewProfile(
        frameRef.current,
        previewMode,
        editable,
        editorDocumentRef.current,
        callbacksRef.current,
      );
    }
  }, [editable, previewMode, retry]);

  function readFrameScrollTop(frame: HTMLIFrameElement | null = frameRef.current): number {
    if (!frame) return lastScrollTopRef.current;
    try {
      return frame.contentWindow?.scrollY
        ?? frame.contentDocument?.documentElement.scrollTop
        ?? frame.contentDocument?.body.scrollTop
        ?? lastScrollTopRef.current;
    } catch {
      return lastScrollTopRef.current;
    }
  }

  function captureFrameScroll() {
    lastScrollTopRef.current = readFrameScrollTop();
  }

  function bindFrameScrollTracking(frame: HTMLIFrameElement) {
    scrollCleanupRef.current?.();
    const view = frame.contentWindow;
    if (!view) {
      scrollCleanupRef.current = null;
      return;
    }
    const track = () => {
      lastScrollTopRef.current = readFrameScrollTop(frame);
    };
    view.addEventListener("scroll", track, { passive: true });
    track();
    scrollCleanupRef.current = () => view.removeEventListener("scroll", track);
  }

  function scheduleScrollRestore(frame: HTMLIFrameElement, scrollTop: number | null) {
    if (scrollTop === null) return;
    window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
      if (frameRef.current !== frame) return;
      try {
        frame.contentWindow?.scrollTo(0, scrollTop);
        lastScrollTopRef.current = readFrameScrollTop(frame);
      } catch {
        // Cross-origin previews cannot be restored; current previews are same-origin.
      }
    }));
  }

  function retryOrFail(loadVersion: number) {
    if (loadVersion !== loadVersionRef.current) return;
    if (retryRef.current < 1) {
      captureFrameScroll();
      restoreScrollTopRef.current = lastScrollTopRef.current;
      retryRef.current += 1;
      setRetry(retryRef.current);
      setLoading(true);
      return;
    }
    setLoading(false);
    setFailed(true);
  }

  function handleLoad(event: React.SyntheticEvent<HTMLIFrameElement>) {
    const frame = event.currentTarget;
    const scrollTopToRestore = restoreScrollTopRef.current;
    restoreScrollTopRef.current = null;
    applyWorkbenchPreviewProfile(frame, previewMode, editable, editorDocumentRef.current, callbacksRef.current);
    bindFrameScrollTracking(frame);
    scheduleScrollRestore(frame, scrollTopToRestore);
    const loadVersion = loadVersionRef.current;
    let images: HTMLImageElement[];
    try {
      images = Array.from(frame.contentDocument?.images ?? []);
    } catch {
      setLoading(false);
      return;
    }

    if (!images.length) {
      setLoading(false);
      setFailed(false);
      return;
    }

    const verify = () => {
      if (images.some((image) => image.complete && image.naturalWidth === 0)) {
        retryOrFail(loadVersion);
        return;
      }
      if (images.every((image) => image.complete && image.naturalWidth > 0)) {
        scheduleScrollRestore(frame, scrollTopToRestore);
        setLoading(false);
        setFailed(false);
      }
    };

    verify();
    if (images.every((image) => image.complete)) return;

    const timeout = window.setTimeout(() => retryOrFail(loadVersion), 12000);
    const settle = () => {
      if (!images.every((image) => image.complete)) return;
      window.clearTimeout(timeout);
      verify();
    };
    images.forEach((image) => {
      image.addEventListener("load", settle, { once: true });
      image.addEventListener("error", settle, { once: true });
    });
  }

  return (
    <div className="preview-frame-shell">
      <iframe
        className="preview-frame"
        onLoad={handleLoad}
        ref={frameRef}
        scrolling="yes"
        src={withRetryToken(src, retry)}
        title={title}
      />
      {loading ? (
        <div className="preview-frame-state" role="status">
          <span />
          <strong>正在加载新主题预览…</strong>
        </div>
      ) : null}
      {failed ? (
        <div className="preview-frame-state preview-frame-failed" role="alert">
          <strong>部分图片暂时未加载</strong>
          <button
            onClick={() => {
              captureFrameScroll();
              restoreScrollTopRef.current = lastScrollTopRef.current;
              retryRef.current = 0;
              setFailed(false);
              setLoading(true);
              setRetry((value) => value + 1);
            }}
            type="button"
          >
            重新加载预览
          </button>
        </div>
      ) : null}
    </div>
  );
}
