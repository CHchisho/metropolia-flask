import { api } from "./api.js";
import { el, formatBytes, formatDate, icon, ICONS, toast } from "./ui.js";

const MAX_MB = 10;
const STATUS_LABEL = { ready: "Ready", processing: "Processing", failed: "Failed" };

/** Documents view: upload zone, summary, and the library table. `hooks.onChange(count)` updates the nav badge. */
export async function mountDocuments(container, hooks) {
  const fileInput = el("input", { type: "file", accept: ".pdf,.txt", multiple: true, hidden: true });
  const dropzone = el("div", { class: "dropzone", tabindex: "0", role: "button", "aria-label": "Upload documents" },
    el("div", { class: "drop-icon" }, icon(ICONS.upload, 26)),
    el("div", { class: "drop-title" }, "Drag & drop documents here"),
    el("div", { class: "drop-sub" }, `or click to browse · PDF or TXT · up to ${MAX_MB} MB each`),
    fileInput);
  const stats = el("div", { class: "stats" });
  const library = el("section", { class: "card library" });
  const uploading = [];

  container.replaceChildren(
    el("div", { class: "page" },
      el("div", { class: "page-intro" },
        el("h2", {}, "Document library"),
        el("p", {}, "Documents are split into passages and indexed. The assistant only answers from what is listed here.")),
      dropzone, stats, library));

  const pick = () => fileInput.click();
  dropzone.addEventListener("click", pick);
  dropzone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
  fileInput.addEventListener("change", () => { handleFiles(fileInput.files); fileInput.value = ""; });
  ["dragenter", "dragover"].forEach((t) => dropzone.addEventListener(t, (e) => { e.preventDefault(); dropzone.classList.add("active"); }));
  ["dragleave", "drop"].forEach((t) => dropzone.addEventListener(t, (e) => { e.preventDefault(); dropzone.classList.remove("active"); }));
  dropzone.addEventListener("drop", (e) => handleFiles(e.dataTransfer.files));

  async function handleFiles(fileList) {
    for (const file of fileList) {
      const ext = file.name.split(".").pop().toLowerCase();
      if (!["pdf", "txt"].includes(ext)) { toast(`${file.name}: only PDF and TXT files are supported.`, "error"); continue; }
      if (file.size > MAX_MB * 1024 * 1024) { toast(`${file.name} is larger than ${MAX_MB} MB.`, "error"); continue; }
      const entry = { name: file.name, size: file.size };
      uploading.push(entry);
      render(documents);
      try {
        const doc = await api.uploadDocument(file);
        doc.status === "failed" ? toast(`${doc.filename}: ${doc.error}`, "error") : toast(`${doc.filename} is ready.`, "success");
      } catch (error) {
        toast(`${file.name}: ${error.message}`, "error");
      } finally {
        uploading.splice(uploading.indexOf(entry), 1);
        await load();
      }
    }
  }

  async function remove(doc) {
    if (!confirm(`Delete "${doc.filename}"? The assistant will no longer use it.`)) return;
    try {
      await api.deleteDocument(doc.id);
      toast("Document deleted.", "success");
      await load();
    } catch (error) {
      toast(error.message, "error");
    }
  }

  let documents = [];

  function render(docs) {
    const ready = docs.filter((d) => d.status === "ready");
    stats.replaceChildren(
      stat(docs.length, "Documents"),
      stat(ready.length, "Ready to search"),
      stat(ready.reduce((n, d) => n + d.chunk_count, 0), "Indexed passages"));

    const rows = [
      ...uploading.map((u) => row({ filename: u.name, file_type: u.name.split(".").pop(), size_bytes: u.size, status: "processing", chunk_count: 0 }, true)),
      ...docs.map((d) => row(d)),
    ];
    if (!rows.length) {
      library.replaceChildren(el("div", { class: "empty-state" },
        el("div", { class: "empty-icon" }, icon(ICONS.file, 26)),
        el("h3", {}, "No documents yet"),
        el("p", {}, "Upload a PDF or TXT file to start asking questions about it.")));
      return;
    }
    library.replaceChildren(
      el("div", { class: "table", role: "table" },
        el("div", { class: "tr th", role: "row" },
          ["Document", "Status", "Size", "Passages", "Added", ""].map((h) => el("div", { class: "td", role: "columnheader" }, h))),
        rows));
  }

  const stat = (value, label) => el("div", { class: "stat" }, el("div", { class: "stat-value" }, String(value)), el("div", { class: "stat-label" }, label));

  function row(doc, pending = false) {
    const pill = el("span", { class: `pill pill-${doc.status}`, title: doc.error ?? "" },
      doc.status === "processing" ? el("span", { class: "spinner small" }) : el("i", { class: "dot" }), STATUS_LABEL[doc.status]);
    return el("div", { class: "tr", role: "row" },
      el("div", { class: "td doc-cell", role: "cell" },
        el("div", { class: `file-badge ${doc.file_type}` }, doc.file_type.toUpperCase()),
        el("div", { class: "doc-text" }, el("div", { class: "doc-name" }, doc.filename),
          doc.error && el("div", { class: "doc-error" }, doc.error))),
      el("div", { class: "td", role: "cell", "data-label": "Status" }, pill),
      el("div", { class: "td muted", role: "cell", "data-label": "Size" }, formatBytes(doc.size_bytes)),
      el("div", { class: "td muted", role: "cell", "data-label": "Passages" }, doc.status === "ready" ? String(doc.chunk_count) : "–"),
      el("div", { class: "td muted", role: "cell", "data-label": "Added" }, pending ? "Just now" : formatDate(doc.created_at)),
      el("div", { class: "td actions", role: "cell" },
        !pending && el("button", { class: "icon-btn danger", type: "button", "aria-label": `Delete ${doc.filename}`, onclick: () => remove(doc) }, icon(ICONS.trash, 18))));
  }

  async function load() {
    try {
      documents = await api.listDocuments();
      hooks.onChange(documents.length);
      render(documents);
    } catch (error) {
      library.replaceChildren(el("div", { class: "empty-state" },
        el("div", { class: "empty-icon error" }, icon(ICONS.alert, 26)),
        el("h3", {}, "Could not load documents"), el("p", {}, error.message),
        el("button", { class: "btn", type: "button", onclick: load }, "Retry")));
    }
  }

  library.replaceChildren(el("div", { class: "loading-block" }, el("span", { class: "spinner" }), "Loading documents…"));
  await load();
}
