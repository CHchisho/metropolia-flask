import { api } from "./api.js";
import { mountChat } from "./chat.js";
import { mountDocuments } from "./documents.js";
import { el, ICONS, icon, toast } from "./ui.js";

const view = document.getElementById("view");
const title = document.getElementById("page-title");
const historyList = document.getElementById("history-list");
const docCount = document.getElementById("doc-count");
let activeConversation = null;

function closeMenu() {
  document.getElementById("app").classList.remove("menu-open");
}

document.getElementById("menu-btn").addEventListener("click", () => document.getElementById("app").classList.add("menu-open"));
document.getElementById("scrim").addEventListener("click", closeMenu);
document.getElementById("new-chat").addEventListener("click", () => {
  if (location.hash === "#/chat") route();
  else location.hash = "#/chat";
});

function setDocCount(count) {
  docCount.textContent = count;
  docCount.hidden = false;
}

async function refreshHistory() {
  try {
    const conversations = await api.listConversations();
    historyList.replaceChildren(
      ...(conversations.length
        ? conversations.map((c) => historyItem(c))
        : [el("li", { class: "history-empty" }, "No conversations yet")]));
  } catch {
    /* The history list is non-essential; the main view reports connection problems. */
  }
}

function historyItem(conversation) {
  const link = el("a", { href: `#/chat/${conversation.id}`, class: `history-link${conversation.id === activeConversation ? " active" : ""}` }, conversation.title);
  const remove = el("button", {
    class: "icon-btn tiny", type: "button", "aria-label": `Delete conversation ${conversation.title}`,
    onclick: async () => {
      try {
        await api.deleteConversation(conversation.id);
        if (conversation.id === activeConversation) location.hash = "#/chat";
        refreshHistory();
      } catch (error) {
        toast(error.message, "error");
      }
    },
  }, icon(ICONS.trash, 15));
  return el("li", { class: "history-item" }, link, remove);
}

async function route() {
  closeMenu();
  const [, page = "chat", param] = location.hash.split("/");
  document.querySelectorAll(".nav-link").forEach((a) => a.classList.toggle("active", a.dataset.route === page));

  if (page === "documents") {
    title.textContent = "Documents";
    activeConversation = null;
    refreshHistory();
    await mountDocuments(view, { onChange: setDocCount });
    return;
  }

  title.textContent = "Chat";
  activeConversation = param ? Number(param) : null;
  refreshHistory();
  await mountChat(view, activeConversation, {
    onConversation(conversation) {
      activeConversation = conversation.id;
      history.replaceState(null, "", `#/chat/${conversation.id}`); // no re-render: the chat is already on screen
      refreshHistory();
    },
  });
}

async function init() {
  api.listDocuments().then((docs) => setDocCount(docs.length)).catch(() => {});
  api.health().then((h) => {
    const badge = document.getElementById("mode-badge");
    badge.textContent = h.demo_mode ? "Demo mode · offline" : `Model: ${h.llm.replace("openai-compatible:", "")}`;
    badge.title = h.demo_mode
      ? "Answers are extracted from the best-matching passages. Configure an LLM in .env for generated answers."
      : `Embeddings: ${h.embeddings}`;
    badge.hidden = false;
  }).catch(() => {});
  window.addEventListener("hashchange", route);
  await route();
}

init();
