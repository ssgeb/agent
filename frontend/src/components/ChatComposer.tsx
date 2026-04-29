import { useMemo, useState, type FormEvent } from "react";

interface ChatComposerProps {
  value: string;
  loading?: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

const QUICK_TEMPLATES = [
  {
    title: "周末游",
    template: "周末想去周边城市玩两天，预算1000元左右，帮我推荐交通、酒店和景点。",
  },
  {
    title: "亲子游",
    template: "带8岁孩子去海边度假，5天4晚，预算5000元，希望酒店舒适、行程轻松。",
  },
  {
    title: "文化游",
    template: "想了解历史文化，计划7天游览西安、洛阳、开封，预算3000元。",
  },
  {
    title: "美食游",
    template: "专门去成都品尝美食，计划4天，预算2000元，推荐当地特色餐厅。",
  },
];

export function ChatComposer({
  value,
  loading = false,
  onChange,
  onSubmit,
}: ChatComposerProps) {
  const [showTemplates, setShowTemplates] = useState(false);
  const canSubmit = useMemo(() => value.trim().length > 0 && !loading, [loading, value]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!canSubmit) {
      return;
    }

    onSubmit();
  };

  const handleTemplateSelect = (template: string) => {
    onChange(template);
    setShowTemplates(false);
  };

  return (
    <form className="chat-composer" onSubmit={handleSubmit}>
      <label className="sr-only" htmlFor="travel-message">
        旅行需求
      </label>
      <textarea
        id="travel-message"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="向旅行规划助手提问"
        rows={3}
      />

      <div className="composer-actions-row">
        <div className="composer-left-actions">
          <button
            type="button"
            className="icon-button"
            aria-label="添加"
            title="添加"
            onClick={() => setShowTemplates((current) => !current)}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </button>
          <button
            type="button"
            className="tool-pill"
            onClick={() => setShowTemplates((current) => !current)}
          >
            快捷模板
          </button>
          <button type="button" className="tool-pill" onClick={() => onChange("帮我规划一个3天2晚的旅行方案，包含交通、酒店、景点和预算。")}>
            任务助理
          </button>
        </div>

        <div className="composer-right-actions">
          <button
            type="button"
            className="icon-button"
            aria-label="清空输入"
            title="清空输入"
            onClick={() => onChange("")}
            disabled={loading || value.length === 0}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M3 6h18M8 6V4h8v2M6 6l1 15h10l1-15" />
            </svg>
          </button>
          <button
            className="send-button"
            type="submit"
            aria-label={loading ? "生成中" : "发送"}
            disabled={!canSubmit}
          >
            {loading ? (
              <span className="loading-spinner" aria-hidden="true" />
            ) : (
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m5 12 7-7 7 7M12 19V5" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {showTemplates && (
        <div className="templates-dropdown">
          {QUICK_TEMPLATES.map((item) => (
            <button
              key={item.title}
              type="button"
              className="template-item"
              onClick={() => handleTemplateSelect(item.template)}
            >
              <strong>{item.title}</strong>
              <span>{item.template}</span>
            </button>
          ))}
        </div>
      )}
    </form>
  );
}
