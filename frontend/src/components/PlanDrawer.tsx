import type { ReactElement } from "react";
import type { TravelPlan, TravelPlanBudget, TravelPlanItem } from "../api/client";

interface PlanDrawerProps {
  open: boolean;
  plan?: TravelPlan | null;
  onClose: () => void;
  onBookHotel?: () => void;
  onBookTransport?: () => void;
  onOpenBookings?: () => void;
  bookingLoading?: boolean;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "";
  }

  if (Array.isArray(value)) {
    return value.map(formatValue).filter(Boolean).join("，");
  }

  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, entry]) => `${key}: ${formatValue(entry)}`)
      .filter((entry) => !entry.endsWith(": "))
      .join("，");
  }

  return String(value);
}

function renderItems(items?: TravelPlanItem[]): ReactElement {
  if (!items || items.length === 0) {
    return <p className="drawer-empty">暂无内容</p>;
  }

  return (
    <ul className="drawer-list">
      {items.map((item, index) => {
        const label = item.name ?? item.title ?? `项目 ${index + 1}`;
        const detailParts = Object.entries(item)
          .filter(([key]) => key !== "name" && key !== "title")
          .map(([key, value]) => {
            const formatted = formatValue(value);
            return formatted ? `${key}: ${formatted}` : "";
          })
          .filter(Boolean);

        return (
          <li key={`${label}-${index}`}>
            <strong>{label}</strong>
            {detailParts.length > 0 ? <span>{detailParts.join("，")}</span> : null}
          </li>
        );
      })}
    </ul>
  );
}

function renderNotes(notes?: string[]): ReactElement {
  if (!notes || notes.length === 0) {
    return <p className="drawer-empty">暂无内容</p>;
  }

  return (
    <ul className="drawer-list">
      {notes.map((note, index) => (
        <li key={`${note}-${index}`}>{note}</li>
      ))}
    </ul>
  );
}

function renderBudget(budget: TravelPlan["budget"]): ReactElement {
  const entries = Object.entries(budget ?? {}).filter(([, value]) => formatValue(value));

  if (entries.length === 0) {
    return <p className="drawer-empty">暂无内容</p>;
  }

  return (
    <dl className="drawer-definition-list">
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

interface PlanSectionProps {
  title: string;
  children: React.ReactNode;
  icon?: string;
}

function PlanSection({ title, children, icon }: PlanSectionProps) {
  return (
    <section className="drawer-section">
      <h3>
        {icon && (
          <span className="section-icon" aria-hidden="true">
            {icon}
          </span>
        )}
        {title}
      </h3>
      <div className="section-content">{children}</div>
    </section>
  );
}

export function PlanDrawer({
  open,
  plan,
  onClose,
  onBookHotel,
  onBookTransport,
  onOpenBookings,
  bookingLoading = false,
}: PlanDrawerProps) {
  if (!open || !plan) {
    return null;
  }

  const formatBudget = (budget: TravelPlanBudget) => {
    if (!budget) return null;

    const parts = [];
    if (budget.total) {
      parts.push(`总计: ${typeof budget.total === "number" ? `￥${budget.total}` : budget.total}`);
    }
    return parts.join(" | ");
  };

  return (
    <aside className="side-drawer plan-drawer" aria-label="完整行程方案">
      <div className="drawer-header">
        <h2>完整行程方案</h2>
        <div className="drawer-actions">
          <button className="secondary-button" type="button" onClick={onClose} title="关闭">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      </div>

      {plan.overview && (
        <PlanSection title="方案概览" icon="📋">
          <div className="overview-content">
            <p>{plan.overview}</p>
          </div>
        </PlanSection>
      )}

      <PlanSection title="交通推荐" icon="🚦">
        {plan.transport && plan.transport.length > 0 ? (
          <div className="items-grid">
            {plan.transport.map((item, index) => (
              <div key={index} className="plan-card">
                <div className="card-header">
                  <h4>{item.name || item.title || `交通方案 ${index + 1}`}</h4>
                  {item.price && <span className="price-tag">{item.price}</span>}
                </div>
                {item.description && <p className="card-description">{item.description}</p>}
              </div>
            ))}
          </div>
        ) : (
          <p className="drawer-empty">暂无交通信息</p>
        )}
      </PlanSection>

      <PlanSection title="酒店推荐" icon="🏨">
        {plan.hotels && plan.hotels.length > 0 ? (
          <div className="items-grid">
            {plan.hotels.map((item, index) => (
              <div key={index} className="plan-card">
                <div className="card-header">
                  <h4>{item.name || item.title || `酒店 ${index + 1}`}</h4>
                  {item.price && <span className="price-tag">{item.price}</span>}
                </div>
                {item.description && <p className="card-description">{item.description}</p>}
              </div>
            ))}
          </div>
        ) : (
          <p className="drawer-empty">暂无酒店信息</p>
        )}
      </PlanSection>

      <PlanSection title="每日行程" icon="🗓️">
        {plan.itinerary && plan.itinerary.length > 0 ? (
          <div className="itinerary-timeline">
            {plan.itinerary.map((item, index) => {
              const dayNumber = index + 1;
              return (
                <div key={index} className="day-item">
                  <div className="day-header">
                    <span className="day-number">第 {dayNumber} 天</span>
                    {item.title && <h5>{item.title}</h5>}
                  </div>
                  {item.description && <p className="day-description">{item.description}</p>}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="drawer-empty">暂无行程安排</p>
        )}
      </PlanSection>

      <PlanSection title="预算估算" icon="💵">
        {renderBudget(plan.budget)}
      </PlanSection>

      <PlanSection title="注意事项" icon="📝">
        {plan.notes && plan.notes.length > 0 ? (
          <ul className="notes-list">
            {plan.notes.map((note, index) => (
              <li key={index}>
                <span className="note-icon">💡</span>
                {note}
              </li>
            ))}
          </ul>
        ) : (
          <p className="drawer-empty">暂无特殊注意事项</p>
        )}
      </PlanSection>

      <div className="drawer-footer">
        <div className="drawer-footer-actions">
          <button
            className="secondary-button"
            type="button"
            onClick={onBookTransport}
            disabled={!onBookTransport || bookingLoading || !plan.transport?.length}
          >
            模拟预订交通
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={onBookHotel}
            disabled={!onBookHotel || bookingLoading || !plan.hotels?.length}
          >
            模拟预订酒店
          </button>
          <button className="secondary-button" type="button" onClick={onOpenBookings}>
            预订记录
          </button>
          <button className="primary-button" type="button" onClick={onClose}>
            完成
          </button>
        </div>
      </div>
    </aside>
  );
}
