(() => {
  "use strict";

  const defaults = {
    enabled: true,
    unlockAntiCopy: true,
    hoverFallback: true,
    replaceReadonly: false
  };
  let settings = { ...defaults };
  let hoveredElement = null;
  const targets = new Map();
  const blockedKeys = new Set(["a", "c", "v", "x", "s", "p", "u"]);

  function shouldUnlock(event) {
    if (!settings.enabled || !settings.unlockAntiCopy) return false;
    if (event.type !== "keydown") return true;
    const primary = event.ctrlKey || event.metaKey;
    return primary && (blockedKeys.has(event.key.toLowerCase()) || event.shiftKey);
  }

  function bypassPageBlocker(event) {
    if (shouldUnlock(event)) {
      // Keep browser default behavior; only prevent later page handlers from cancelling it.
      event.stopImmediatePropagation();
    }
  }

  ["copy", "cut", "paste", "contextmenu", "selectstart", "selectionchange", "dragstart", "drop", "keydown"]
    .forEach((name) => document.addEventListener(name, bypassPageBlocker, true));

  const style = document.createElement("style");
  style.dataset.viet2enUnlock = "true";
  style.textContent = `
    html.viet2en-unlock *, html.viet2en-unlock *::before, html.viet2en-unlock *::after {
      -webkit-user-select: text !important;
      user-select: text !important;
      -webkit-touch-callout: default !important;
    }
  `;

  function applySettings(nextSettings) {
    settings = { ...settings, ...nextSettings };
    document.documentElement?.classList.toggle(
      "viet2en-unlock",
      Boolean(settings.enabled && settings.unlockAntiCopy)
    );
    if (!style.isConnected) (document.head || document.documentElement)?.appendChild(style);
  }

  chrome.storage.sync.get(defaults).then(applySettings);
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "sync") return;
    applySettings(Object.fromEntries(Object.entries(changes).map(([key, value]) => [key, value.newValue])));
  });

  document.addEventListener("mousemove", (event) => {
    hoveredElement = event.target instanceof Element ? event.target : null;
  }, { capture: true, passive: true });

  function extractInputSelection(element, requestId) {
    const start = element.selectionStart;
    const end = element.selectionEnd;
    if (typeof start !== "number" || typeof end !== "number" || end <= start) return null;
    const text = element.value.slice(start, end);
    targets.set(requestId, { kind: "input", element, start, end, originalValue: element.value });
    return { text, source: "input", editable: !element.readOnly && !element.disabled, priority: 100 };
  }

  function extractDocumentSelection(requestId) {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return null;
    const text = selection.toString();
    if (!text.trim()) return null;
    const range = selection.getRangeAt(0).cloneRange();
    const container = range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE
      ? range.commonAncestorContainer
      : range.commonAncestorContainer.parentElement;
    const editable = Boolean(container?.closest?.("[contenteditable='true'], textarea, input"));
    targets.set(requestId, { kind: "range", range, editable });
    return { text, source: "selection", editable, priority: 90 };
  }

  function extractHoverText(requestId) {
    if (!settings.hoverFallback || !hoveredElement) return null;
    const element = hoveredElement.closest("p, li, blockquote, pre, code, article, section, div") || hoveredElement;
    const text = (element.innerText || element.textContent || "").trim().slice(0, 12000);
    if (!text) return null;
    targets.set(requestId, { kind: "readonly", element });
    return { text, source: "hover", editable: false, priority: 20 };
  }

  function extract(requestId) {
    const active = document.activeElement;
    if (active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement) {
      const inputResult = extractInputSelection(active, requestId);
      if (inputResult) return inputResult;
    }
    return extractDocumentSelection(requestId) || extractHoverText(requestId) || { text: "", priority: 0 };
  }

  function dispatchEditEvent(element) {
    element.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertReplacementText" }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function applyTranslation(requestId, text) {
    const target = targets.get(requestId);
    targets.delete(requestId);
    if (!target) return false;

    if (target.kind === "input") {
      const { element, start, end } = target;
      if (!element.isConnected || element.readOnly || element.disabled) return false;
      element.focus();
      element.setRangeText(text, start, end, "end");
      dispatchEditEvent(element);
      return true;
    }

    if (target.kind === "range" && (target.editable || settings.replaceReadonly)) {
      try {
        const range = target.range;
        range.deleteContents();
        const node = document.createTextNode(text);
        range.insertNode(node);
        range.setStartAfter(node);
        range.collapse(true);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        if (target.editable) dispatchEditEvent(node.parentElement || document.body);
        return true;
      } catch (_error) {
        return false;
      }
    }
    return false;
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!settings.enabled) {
      sendResponse({ text: "", priority: 0 });
      return;
    }
    if (message.type === "extract") {
      sendResponse(extract(message.request_id));
      return;
    }
    if (message.type === "apply") {
      sendResponse({ success: applyTranslation(message.request_id, String(message.text || "")) });
    }
  });
})();
