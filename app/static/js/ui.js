/** Small DOM helpers shared by the views. */

/** Create an element: el("div", { class: "x", onclick: fn }, child, "text"). */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key === "class") node.className = value;
    else if (key === "html") node.innerHTML = value;
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(child));
  }
  return node;
}

export function icon(path, size = 18) {
  const wrap = document.createElement("span");
  wrap.className = "icon";
  wrap.innerHTML = `<svg viewBox="0 0 24 24" width="${size}" height="${size}">${path}</svg>`;
  return wrap;
}

export const ICONS = {
  send: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/><path d="M14 3v5h5"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5M5 20h14"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z"/>',
  alert: '<path d="M12 9v4M12 17h.01M10.3 4.3 2.7 18a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0Z"/>',
};

export function toast(message, kind = "info") {
  const node = el("div", { class: `toast toast-${kind}`, role: "status" }, message);
  document.getElementById("toasts").append(node);
  setTimeout(() => node.classList.add("leaving"), 4200);
  setTimeout(() => node.remove(), 4600);
}

export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDate(iso) {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

const escapeHtml = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/**
 * Minimal, safe rendering of model output: paragraphs, "-" lists, **bold**, and [n] citation chips.
 * Input is HTML-escaped first, so model output can never inject markup.
 */
export function renderAnswer(text) {
  const inline = (s) =>
    escapeHtml(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\[(\d{1,2})\]/g, '<button type="button" class="cite" data-cite="$1">$1</button>');

  const html = [];
  let list = [];
  const flush = () => {
    if (list.length) html.push(`<ul>${list.map((i) => `<li>${inline(i)}</li>`).join("")}</ul>`);
    list = [];
  };
  for (const line of text.split("\n")) {
    const item = line.match(/^\s*[-*•]\s+(.*)$/);
    if (item) list.push(item[1]);
    else {
      flush();
      if (line.trim()) html.push(`<p>${inline(line)}</p>`);
    }
  }
  flush();
  return html.join("");
}
