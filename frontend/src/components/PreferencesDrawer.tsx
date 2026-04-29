import { useEffect, useState } from "react";
import {
  getUserPreferences,
  updateUserPreferences,
  type UserPreferences,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";

interface PreferencesDrawerProps {
  open: boolean;
  onClose: () => void;
}

const EMPTY_PREFERENCES: UserPreferences = {
  budget: null,
  transport_preferences: {},
  hotel_preferences: {},
  attraction_preferences: {},
  pace_preference: null,
  must_visit_places: [],
  excluded_places: [],
  notes: [],
};

function joinList(values?: string[]) {
  return values?.join("，") ?? "";
}

function splitList(value: string) {
  return value
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function toText(value: unknown) {
  return value === null || value === undefined ? "" : String(value);
}

export function PreferencesDrawer({ open, onClose }: PreferencesDrawerProps) {
  const { token } = useAuth();
  const [budgetMax, setBudgetMax] = useState("");
  const [transportMode, setTransportMode] = useState("");
  const [hotelStars, setHotelStars] = useState("");
  const [hotelNear, setHotelNear] = useState("");
  const [attractionTheme, setAttractionTheme] = useState("");
  const [pace, setPace] = useState("");
  const [mustVisitPlaces, setMustVisitPlaces] = useState("");
  const [excludedPlaces, setExcludedPlaces] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open || !token) {
      return;
    }

    let cancelled = false;

    const loadPreferences = async () => {
      setLoading(true);
      setError("");
      setStatus("");

      try {
        const { preferences } = await getUserPreferences(token);
        if (cancelled) {
          return;
        }
        setBudgetMax(toText(preferences.budget?.max));
        setTransportMode(toText(preferences.transport_preferences.mode));
        setHotelStars(toText(preferences.hotel_preferences.stars));
        setHotelNear(toText(preferences.hotel_preferences.near));
        setAttractionTheme(toText(preferences.attraction_preferences.theme));
        setPace(preferences.pace_preference ?? "");
        setMustVisitPlaces(joinList(preferences.must_visit_places));
        setExcludedPlaces(joinList(preferences.excluded_places));
        setNotes(joinList(preferences.notes));
      } catch {
        if (!cancelled) {
          setError("偏好加载失败");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadPreferences();

    return () => {
      cancelled = true;
    };
  }, [open, token]);

  if (!open) {
    return null;
  }

  const handleSave = async () => {
    if (!token) {
      setError("请先登录");
      return;
    }

    const budgetValue = Number(budgetMax);
    const starsValue = Number(hotelStars);
    const preferences: UserPreferences = {
      ...EMPTY_PREFERENCES,
      budget: budgetMax.trim() ? { max: budgetValue } : null,
      transport_preferences: transportMode.trim() ? { mode: transportMode.trim() } : {},
      hotel_preferences: {
        ...(hotelStars.trim() && Number.isFinite(starsValue) ? { stars: starsValue } : {}),
        ...(hotelNear.trim() ? { near: hotelNear.trim() } : {}),
      },
      attraction_preferences: attractionTheme.trim() ? { theme: attractionTheme.trim() } : {},
      pace_preference: pace || null,
      must_visit_places: splitList(mustVisitPlaces),
      excluded_places: splitList(excludedPlaces),
      notes: splitList(notes),
    };

    setSaving(true);
    setError("");
    setStatus("");

    try {
      await updateUserPreferences(preferences, token);
      setStatus("偏好已保存");
    } catch {
      setError("偏好保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <aside className="side-drawer preferences-drawer" aria-label="偏好设置">
      <div className="drawer-header">
        <h2>偏好设置</h2>
        <button className="secondary-button" type="button" onClick={onClose}>
          关闭
        </button>
      </div>

      <div className="preferences-form">
        {loading ? (
          <div className="loading-state">
            <span className="loading-spinner" aria-hidden="true" />
            <span>加载中...</span>
          </div>
        ) : (
          <>
            <label>
              <span>预算上限</span>
              <input
                inputMode="numeric"
                value={budgetMax}
                onChange={(event) => setBudgetMax(event.target.value)}
                placeholder="例如 2200"
              />
            </label>

            <div className="preference-grid">
              <label>
                <span>交通偏好</span>
                <input
                  value={transportMode}
                  onChange={(event) => setTransportMode(event.target.value)}
                  placeholder="train / flight / drive"
                />
              </label>
              <label>
                <span>行程节奏</span>
                <select value={pace} onChange={(event) => setPace(event.target.value)}>
                  <option value="">不固定</option>
                  <option value="relaxed">轻松</option>
                  <option value="moderate">适中</option>
                  <option value="compact">紧凑</option>
                </select>
              </label>
            </div>

            <div className="preference-grid">
              <label>
                <span>酒店星级</span>
                <input
                  inputMode="numeric"
                  value={hotelStars}
                  onChange={(event) => setHotelStars(event.target.value)}
                  placeholder="例如 4"
                />
              </label>
              <label>
                <span>酒店位置偏好</span>
                <input
                  value={hotelNear}
                  onChange={(event) => setHotelNear(event.target.value)}
                  placeholder="例如 西湖 / 外滩"
                />
              </label>
            </div>

            <label>
              <span>景点主题偏好</span>
              <input
                value={attractionTheme}
                onChange={(event) => setAttractionTheme(event.target.value)}
                placeholder="亲子 / citywalk / 自然风景"
              />
            </label>

            <label>
              <span>必去地点</span>
              <input
                value={mustVisitPlaces}
                onChange={(event) => setMustVisitPlaces(event.target.value)}
                placeholder="用逗号分隔"
              />
            </label>

            <label>
              <span>避开地点</span>
              <input
                value={excludedPlaces}
                onChange={(event) => setExcludedPlaces(event.target.value)}
                placeholder="用逗号分隔"
              />
            </label>

            <label>
              <span>备注</span>
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="例如 少走路，优先地铁"
                rows={3}
              />
            </label>

            {error && <p className="form-error">{error}</p>}
            {status && <p className="form-success">{status}</p>}
          </>
        )}
      </div>

      <div className="drawer-footer">
        <button className="primary-button full-width" type="button" onClick={handleSave} disabled={saving}>
          {saving ? "保存中..." : "保存偏好"}
        </button>
      </div>
    </aside>
  );
}
