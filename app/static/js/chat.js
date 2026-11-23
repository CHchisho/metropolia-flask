import { api } from "./api.js";
import { el, icon, ICONS, renderAnswer, toast } from "./ui.js";

const SUGGESTIONS = [
  "How many times can I retake an exam?",
  "What are the library opening hours?",
  "What is the thesis submission deadline?",
  "Can international students work during their studies?",
];

/**
 * Chat view. `hooks.onConversation(conversation)` is called when a new conversation is created,
 * so the shell can update the URL and the history list.
 */
export async function mountChat(container, conversationId, hooks) {
  let currentId = conversationId;
  let busy = false;

  const messages = el("div", { class: "messages", role: "log", "aria-live": "polite" });
  const input = el("textarea", {
    class: "composer-input",
    rows: "1",
    maxlength: "2000",
    placeholder: "Ask about studies, exams, thesis…",
    "aria-label": "Your question",
  });
  const sendBtn = el("button", { class: "send-btn", type: "submit", "aria-label": "Send" }, icon(ICONS.send, 20));
  const form = el("form", { class: "composer" }, input, sendBtn);
  container.replaceChildren(
    el("div", { class: "chat" }, el("div", { class: "scroll", id: "scroll" }, messages),
      el("div", { class: "composer-wrap" }, form,
        el("p", { class: "composer-hint" }, "Answers are generated from your uploaded documents. Check the sources before relying on them."))),
  );
  const scroller = container.querySelector("#scroll");
  const scrollDown = () => scroller.scrollTo({ top: scroller.scrollHeight, behavior: "smooth" });

  function showEmpty() {
    messages.replaceChildren(
      el("div", { class: "empty-chat" },
        el("div", { class: "empty-icon" }, icon(ICONS.spark, 26)),
        el("h2", {}, "What would you like to know?"),
        el("p", {}, "Ask a question in plain language. I search the uploaded documents and show you exactly where each answer comes from."),
        el("div", { class: "suggestions" },
          SUGGESTIONS.map((text) => el("button", { class: "suggestion", type: "button", onclick: () => send(text) }, text)))),
    );
  }

  function addMessage(message) {
    messages.querySelector(".empty-chat")?.remove();
    const isUser = message.role === "user";
    const bubble = el("div", { class: "bubble" });
    if (isUser) bubble.textContent = message.content;
    else bubble.innerHTML = renderAnswer(message.content);

    const wrap = el("div", { class: `msg ${isUser ? "user" : "assistant"}` },
      !isUser && el("div", { class: "avatar", "aria-hidden": "true" }, icon(ICONS.spark, 16)),
      el("div", { class: "msg-body" }, bubble));
    if (!isUser && message.sources?.length) wrap.querySelector(".msg-body").append(renderSources(message.sources));
    messages.append(wrap);
    return wrap;
  }

  function renderSources(sources) {
    const maxScore = 0.4; // cosine scores above this are shown as a full bar
    const cards = sources.map((s) => {
      const excerpt = el("p", { class: "excerpt" }, s.excerpt);
      const card = el("li", { class: "source", "data-index": s.index },
        el("button", { class: "source-head", type: "button", "aria-expanded": "false", onclick: () => toggle(card) },
          el("span", { class: "source-index" }, s.index),
          el("span", { class: "source-title" }, s.filename, s.page ? el("span", { class: "source-page" }, ` · page ${s.page}`) : null),
          el("span", { class: "relevance", title: `Similarity score ${s.score}` },
            el("span", { class: "relevance-bar", style: `width:${Math.round(Math.min(s.score / maxScore, 1) * 100)}%` })),
          icon(ICONS.chevron, 16)),
        excerpt);
      return card;
    });
    const toggle = (card, open) => {
      const expanded = open ?? !card.classList.contains("open");
      card.classList.toggle("open", expanded);
      card.querySelector(".source-head").setAttribute("aria-expanded", String(expanded));
    };
    cards[0] && toggle(cards[0], true);

    const section = el("div", { class: "sources" },
      el("div", { class: "sources-label" }, icon(ICONS.file, 14), `Sources (${sources.length})`),
      el("ul", { class: "source-list" }, cards));
    return section;
  }

  // Clicking a [n] chip in an answer opens and highlights that source.
  messages.addEventListener("click", (event) => {
    const chip = event.target.closest(".cite");
    if (!chip) return;
    const msg = chip.closest(".msg");
    const card = [...msg.querySelectorAll(".source")].find((c) => c.dataset.index === chip.dataset.cite);
    if (!card) return;
    card.classList.add("open", "flash");
    card.querySelector(".source-head").setAttribute("aria-expanded", "true");
    card.scrollIntoView({ behavior: "smooth", block: "nearest" });
    setTimeout(() => card.classList.remove("flash"), 1400);
  });

  function setBusy(value) {
    busy = value;
    input.disabled = value;
    sendBtn.disabled = value;
  }

  function typingIndicator() {
    return el("div", { class: "msg assistant typing", "aria-label": "Assistant is searching documents" },
      el("div", { class: "avatar" }, icon(ICONS.spark, 16)),
      el("div", { class: "msg-body" }, el("div", { class: "bubble" },
        el("span", { class: "dots" }, el("i"), el("i"), el("i")), el("span", { class: "typing-label" }, "Searching documents…"))));
  }

  function errorBubble(text, retry) {
    return el("div", { class: "msg assistant error" },
      el("div", { class: "avatar" }, icon(ICONS.alert, 16)),
      el("div", { class: "msg-body" }, el("div", { class: "bubble" },
        el("strong", {}, "Something went wrong"), el("p", {}, text),
        el("button", { class: "btn btn-small", type: "button", onclick: retry }, "Try again"))));
  }

  async function send(text) {
    text = text.trim();
    if (!text || busy) return;
    setBusy(true);
    input.value = "";
    autosize();
    addMessage({ role: "user", content: text });
    const typing = typingIndicator();
    messages.append(typing);
    scrollDown();
    try {
      const result = await api.chat(text, currentId);
      typing.remove();
      addMessage(result.message);
      if (currentId == null) {
        currentId = result.conversation.id;
        hooks.onConversation(result.conversation);
      }
    } catch (error) {
      typing.remove();
      const bubble = errorBubble(error.message, () => {
        bubble.remove();
        messages.lastElementChild?.classList.contains("user") && messages.lastElementChild.remove();
        send(text);
      });
      messages.append(bubble);
    } finally {
      setBusy(false);
      scrollDown();
      input.focus();
    }
  }

  function autosize() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
  input.addEventListener("input", autosize);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(input.value); }
  });

  if (currentId == null) {
    showEmpty();
  } else {
    messages.replaceChildren(el("div", { class: "loading-block" }, el("span", { class: "spinner" }), "Loading conversation…"));
    try {
      const data = await api.getConversation(currentId);
      messages.replaceChildren();
      data.messages.forEach(addMessage);
      requestAnimationFrame(() => scroller.scrollTo({ top: scroller.scrollHeight }));
    } catch (error) {
      currentId = null;
      showEmpty();
      toast(error.message, "error");
    }
  }
  input.focus();
}
