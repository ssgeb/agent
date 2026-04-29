import { useEffect, useState } from "react";
import { listBookingRecords, type BookingRecord } from "../api/client";
import { useAuth } from "../auth/AuthContext";

interface BookingDrawerProps {
  open: boolean;
  onClose: () => void;
}

function getBookingTitle(booking: BookingRecord): string {
  return `${booking.booking_type} · ${booking.item_name}`;
}

function getBookingDate(booking: BookingRecord): string {
  const date = new Date(booking.created_at);
  if (Number.isNaN(date.getTime())) {
    return "刚刚";
  }

  return date.toLocaleDateString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function BookingDrawer({ open, onClose }: BookingDrawerProps) {
  const { token, user } = useAuth();
  const [bookings, setBookings] = useState<BookingRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open || !token || !user) {
      return;
    }

    let cancelled = false;

    const loadBookings = async () => {
      setLoading(true);
      setError("");

      try {
        const response = await listBookingRecords(token, 50);
        if (!cancelled) {
          setBookings(response.bookings);
        }
      } catch {
        if (!cancelled) {
          setError("加载预订记录失败");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadBookings();

    return () => {
      cancelled = true;
    };
  }, [open, token, user]);

  return (
    <aside className={`history-drawer ${open ? "open" : ""}`} aria-label="预订记录">
      <div className="drawer-header">
        <h2>预订记录</h2>
        <button className="secondary-button" type="button" onClick={onClose}>
          关闭
        </button>
      </div>
      <div className="history-list">
        {loading ? (
          <div className="loading-state">
            <span className="loading-spinner" aria-hidden="true" />
            <span>加载中...</span>
          </div>
        ) : error ? (
          <div className="error-state">
            <p>{error}</p>
          </div>
        ) : bookings.length === 0 ? (
          <div className="empty-state">
            <p>暂无预订记录</p>
          </div>
        ) : (
          bookings.map((booking) => (
            <article key={booking.booking_id} className="history-item" aria-label={getBookingTitle(booking)}>
              <span className="history-item-title">{getBookingTitle(booking)}</span>
              <span className="history-item-date">{getBookingDate(booking)}</span>
              <span className="history-item-preview">
                {booking.currency} {booking.amount ?? "未填写"} · {booking.status}
              </span>
            </article>
          ))
        )}
      </div>
    </aside>
  );
}
