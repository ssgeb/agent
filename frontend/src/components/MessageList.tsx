export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "status";
  text: string;
}

interface MessageListProps {
  messages: ChatMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <section className="message-list" aria-live="polite" aria-label="聊天记录">
      {messages.length === 0 ? (
        <div className="message-empty">
          <div className="assistant-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M12 2 4 6.5v9L12 22l8-6.5v-9L12 2Z" />
              <path d="M12 7v10M7.5 9.5l9 5M16.5 9.5l-9 5" />
            </svg>
          </div>
          <h1>你好，我是旅行规划助手</h1>
        </div>
      ) : (
        <div className="message-stack">
          {messages.map((message) => (
            <article key={message.id} className={`message message-${message.role}`}>
              <div className="message-role">
                {message.role === "user"
                  ? "你"
                  : message.role === "assistant"
                    ? "助手"
                    : "状态"}
              </div>
              <div className="message-content">
                {message.text.split("\n").map((line, index) => (
                  <p key={`${message.id}-${index}`}>{line}</p>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
