/** Thin fetch wrapper. Every failure becomes an Error with a user-readable message. */
async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`/api${path}`, options);
  } catch {
    throw new Error("Cannot reach the server. Is the application running?");
  }
  if (response.status === 204) return null;
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(body?.error?.message ?? `Request failed (${response.status})`);
  }
  return body;
}

const json = (method, data) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});

export const api = {
  health: () => request("/health"),
  listDocuments: () => request("/documents").then((r) => r.documents),
  uploadDocument(file) {
    const form = new FormData();
    form.append("file", file);
    return request("/documents", { method: "POST", body: form }).then((r) => r.document);
  },
  deleteDocument: (id) => request(`/documents/${id}`, { method: "DELETE" }),
  chat: (message, conversationId) =>
    request("/chat", json("POST", { message, conversation_id: conversationId ?? null })),
  listConversations: () => request("/conversations").then((r) => r.conversations),
  getConversation: (id) => request(`/conversations/${id}`),
  deleteConversation: (id) => request(`/conversations/${id}`, { method: "DELETE" }),
};
