import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { MessageSquare, Send, Trash2, RefreshCw, Clock, CheckCircle, Users, Calendar, ExternalLink, Phone, AlertCircle } from "lucide-react";
import { useAdminBrand } from "./useAdminBrand";

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Dynamic Brand Theme based on active brand
const getThemeColors = (isLaVela) => isLaVela ? {
  bg: "#0D4D4D", surface: "#1A6B6B", surfaceAlt: "#1A6B6B40",
  border: "#D4A57440", borderLight: "#D4A57430",
  gold: "#D4A574", goldDim: "#E6BE8A", goldFaint: "rgba(212,165,116,0.15)",
  green: "#72B08A", greenBright: "#72B08A", greenFaint: "rgba(114,176,138,0.15)",
  red: "#E07070", redBright: "#E07070",
  amber: "#E8A860", amberFaint: "rgba(232,168,96,0.15)",
  blue: "#7AAEC8", blueBright: "#7AAEC8", blueFaint: "rgba(122,174,200,0.15)",
  purple: "#9B8ABF", purpleBright: "#9B8ABF",
  text: "#FDF8F5", textDim: "#D4A574", textMuted: "#E8C4B8",
  white: "#FDF8F5",
} : {
  bg: "#FDF9F9", surface: "#FFFFFF", surfaceAlt: "#FEF2F4",
  border: "#F0E8E8", borderLight: "#E8DEE0",
  gold: "#F8A5B8", goldDim: "#E8889A", goldFaint: "rgba(248,165,184,0.08)",
  green: "#72B08A", greenBright: "#72B08A", greenFaint: "rgba(114,176,138,0.1)",
  red: "#E07070", redBright: "#E07070",
  amber: "#E8A860", amberFaint: "rgba(232,168,96,0.1)",
  blue: "#7AAEC8", blueBright: "#7AAEC8", blueFaint: "rgba(122,174,200,0.08)",
  purple: "#9B8ABF", purpleBright: "#9B8ABF",
  text: "#2D2A2E", textDim: "#8A8490", textMuted: "#C4BAC0",
  white: "#FFFFFF",
};

// Default theme for static references
const C = {
  bg: "#FDF9F9", surface: "#FFFFFF", surfaceAlt: "#FEF2F4",
  border: "#F0E8E8", borderLight: "#E8DEE0",
  gold: "#F8A5B8", goldDim: "#E8889A", goldFaint: "rgba(248,165,184,0.08)",
  green: "#72B08A", greenBright: "#72B08A", greenFaint: "rgba(114,176,138,0.1)",
  red: "#E07070", redBright: "#E07070",
  amber: "#E8A860", amberFaint: "rgba(232,168,96,0.1)",
  blue: "#7AAEC8", blueBright: "#7AAEC8", blueFaint: "rgba(122,174,200,0.08)",
  purple: "#9B8ABF", purpleBright: "#9B8ABF",
  text: "#2D2A2E", textDim: "#8A8490", textMuted: "#C4BAC0",
  white: "#FFFFFF",
};

const FONT_DISPLAY = "'Cormorant Garamond', Georgia, serif";
const FONT_MONO = "'JetBrains Mono', 'Courier New', monospace";

// Task 5: 28-Day Cycle messages
const DAY_LABELS = {
  0: { label: "Welcome", color: C.blue, emoji: "👋" },
  7: { label: "Week 1 Check-in", color: C.green, emoji: "💧" },
  14: { label: "Week 2 Progress", color: C.green, emoji: "🌟" },
  21: { label: "Review Request", color: C.purple, emoji: "⭐" },
  25: { label: "Running Low", color: C.amber, emoji: "⚠️" },
  28: { label: "Cycle Complete", color: C.gold, emoji: "🎉" },
  35: { label: "Win-Back", color: C.red, emoji: "💙" },
};

// Task 6: Loyalty event notifications
const ACTION_TYPE_LABELS = {
  'points_earned': { label: "Points Earned", color: C.green, emoji: "🌿" },
  'redemption_confirmed': { label: "Redemption", color: C.gold, emoji: "✅" },
  'gift_sent': { label: "Gift Sent", color: C.purple, emoji: "🎁" },
  'gift_received': { label: "Gift Received", color: C.blue, emoji: "🎁" },
  'review_thankyou': { label: "Review Thanks", color: C.amber, emoji: "🌟" },
  // Task 7: Birthday + Referral bonuses
  'birthday_bonus': { label: "Birthday", color: C.gold, emoji: "🎂" },
  'referral_bonus': { label: "Referral", color: C.green, emoji: "🎉" },
  'whatsapp': { label: "28-Day Cycle", color: C.textDim, emoji: "📱" },
};

export default function WhatsAppCRMActions() {
  const { isLaVela } = useAdminBrand();
  const TC = getThemeColors(isLaVela);
  
  const [actions, setActions] = useState([]);
  const [stats, setStats] = useState({ pending: 0, sent: 0, total: 0, by_day: {} });
  const [loading, setLoading] = useState(true);
  const [runningScheduler, setRunningScheduler] = useState(false);
  const [selectedDay, setSelectedDay] = useState(null);
  const [selectedType, setSelectedType] = useState(null); // Task 6: Filter by action type
  const [error, setError] = useState(null);

  const fetchActions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("reroots_token");
      const { data } = await axios.get(`${API}/admin/crm-actions?status=pending&limit=100`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setActions(data.actions || []);
      setStats(data.stats || { pending: 0, sent: 0, total: 0, by_day: {} });
    } catch (err) {
      console.error("Failed to fetch CRM actions:", err);
      setError("Failed to load CRM actions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchActions();
  }, [fetchActions]);

  const runScheduler = async () => {
    setRunningScheduler(true);
    try {
      const token = localStorage.getItem("reroots_token");
      const { data } = await axios.post(`${API}/admin/crm-actions/run-scheduler`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      await fetchActions();
      alert(`Scheduler complete! Created ${data.total_actions_created} new actions.`);
    } catch (err) {
      console.error("Scheduler error:", err);
      alert("Failed to run scheduler");
    } finally {
      setRunningScheduler(false);
    }
  };

  const markAsSent = async (action) => {
    try {
      const token = localStorage.getItem("reroots_token");
      
      // Use different endpoint based on action type
      if (action.action_id) {
        // Loyalty notification - use action_id
        await axios.post(`${API}/admin/crm-actions/action/${action.action_id}/sent`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });
      } else {
        // 28-day cycle - use order_id + day
        await axios.post(`${API}/admin/crm-actions/${action.order_id}/day/${action.day}/sent`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });
      }
      
      // Remove from list
      setActions(prev => prev.filter(a => {
        if (action.action_id) return a.action_id !== action.action_id;
        return !(a.order_id === action.order_id && a.day === action.day);
      }));
      setStats(prev => ({
        ...prev,
        pending: prev.pending - 1,
        sent: prev.sent + 1
      }));
    } catch (err) {
      console.error("Failed to mark as sent:", err);
    }
  };

  const deleteAction = async (action) => {
    if (!window.confirm("Delete this message? This action cannot be undone.")) return;
    try {
      const token = localStorage.getItem("reroots_token");
      
      // Use different endpoint based on action type
      if (action.action_id) {
        // Loyalty notification - use action_id
        await axios.delete(`${API}/admin/crm-actions/action/${action.action_id}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
      } else {
        // 28-day cycle - use order_id + day
        await axios.delete(`${API}/admin/crm-actions/${action.order_id}/day/${action.day}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
      }
      
      setActions(prev => prev.filter(a => {
        if (action.action_id) return a.action_id !== action.action_id;
        return !(a.order_id === action.order_id && a.day === action.day);
      }));
      setStats(prev => ({
        ...prev,
        pending: prev.pending - 1,
        total: prev.total - 1
      }));
    } catch (err) {
      console.error("Failed to delete action:", err);
    }
  };

  const filteredActions = actions.filter(a => {
    // Filter by day (for 28-day cycle messages)
    if (selectedDay !== null && a.day !== selectedDay) return false;
    // Filter by action type (for loyalty notifications)
    if (selectedType !== null && (a.action_type || a.type) !== selectedType) return false;
    return true;
  });

  const formatDate = (dateStr) => {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-CA', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div style={{ padding: "2rem", background: C.bg, minHeight: "100vh", fontFamily: "'Inter', sans-serif" }}>
      {/* Header */}
      <div style={{ marginBottom: "2rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "0.5rem" }}>
          <MessageSquare size={28} color={C.gold} />
          <h1 style={{ fontFamily: FONT_DISPLAY, fontSize: "1.8rem", fontWeight: 300, color: C.text, letterSpacing: "0.05em" }}>
            WhatsApp CRM Actions
          </h1>
        </div>
        <p style={{ color: C.textDim, fontSize: "0.85rem", fontFamily: FONT_MONO }}>
          28-day customer engagement messages via wa.me links
        </p>
      </div>

      {/* Stats Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginBottom: "2rem" }}>
        <StatCard 
          icon={<Clock size={20} />} 
          label="Pending" 
          value={stats.pending} 
          color={C.amber}
          bgColor={C.amberFaint}
        />
        <StatCard 
          icon={<CheckCircle size={20} />} 
          label="Sent" 
          value={stats.sent} 
          color={C.green}
          bgColor={C.greenFaint}
        />
        <StatCard 
          icon={<Users size={20} />} 
          label="Total Actions" 
          value={stats.total} 
          color={C.blue}
          bgColor={C.blueFaint}
        />
      </div>

      {/* Day Filter Pills (28-Day Cycle) */}
      <div style={{ marginBottom: "1rem" }}>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ color: C.textDim, fontSize: "0.75rem", fontFamily: FONT_MONO, marginRight: "0.5rem" }}>28-DAY:</span>
          <DayPill 
            label="All Days" 
            active={selectedDay === null && selectedType === null} 
            onClick={() => { setSelectedDay(null); setSelectedType(null); }}
            count={actions.length}
          />
          {Object.entries(DAY_LABELS).map(([day, info]) => {
            const count = actions.filter(a => a.day === parseInt(day)).length;
            return (
              <DayPill 
                key={day}
                label={`Day ${day}`}
                emoji={info.emoji}
                active={selectedDay === parseInt(day)}
                onClick={() => { setSelectedDay(parseInt(day)); setSelectedType(null); }}
                count={count}
                color={info.color}
              />
            );
          })}
        </div>
      </div>

      {/* Task 6: Action Type Filter Pills (Loyalty Notifications) */}
      <div style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ color: C.textDim, fontSize: "0.75rem", fontFamily: FONT_MONO, marginRight: "0.5rem" }}>LOYALTY:</span>
          {Object.entries(ACTION_TYPE_LABELS).filter(([key]) => key !== 'whatsapp').map(([type, info]) => {
            const count = actions.filter(a => (a.action_type || a.type) === type).length;
            if (count === 0) return null;
            return (
              <DayPill 
                key={type}
                label={info.label}
                emoji={info.emoji}
                active={selectedType === type}
                onClick={() => { setSelectedType(type); setSelectedDay(null); }}
                count={count}
                color={info.color}
              />
            );
          })}
        </div>
      </div>

      {/* Actions Bar */}
      <div style={{ 
        display: "flex", 
        justifyContent: "space-between", 
        alignItems: "center", 
        marginBottom: "1.5rem",
        padding: "1rem",
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: "8px"
      }}>
        <div style={{ color: C.textDim, fontSize: "0.8rem", fontFamily: FONT_MONO }}>
          {filteredActions.length} message{filteredActions.length !== 1 ? 's' : ''} pending
        </div>
        <div style={{ display: "flex", gap: "0.75rem" }}>
          <button
            onClick={fetchActions}
            disabled={loading}
            style={{
              display: "flex", alignItems: "center", gap: "0.5rem",
              background: "transparent", color: C.textDim, border: `1px solid ${C.border}`,
              padding: "0.5rem 1rem", borderRadius: "6px", cursor: "pointer",
              fontSize: "0.75rem", fontFamily: FONT_MONO
            }}
          >
            <RefreshCw size={14} className={loading ? "spin" : ""} />
            Refresh
          </button>
          <button
            onClick={runScheduler}
            disabled={runningScheduler}
            style={{
              display: "flex", alignItems: "center", gap: "0.5rem",
              background: C.gold, color: C.white, border: "none",
              padding: "0.5rem 1rem", borderRadius: "6px", cursor: "pointer",
              fontSize: "0.75rem", fontFamily: FONT_MONO, fontWeight: 500
            }}
          >
            <Calendar size={14} />
            {runningScheduler ? "Running..." : "Generate Actions"}
          </button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div style={{ 
          padding: "1rem", 
          background: "rgba(224, 112, 112, 0.1)", 
          border: `1px solid ${C.red}`,
          borderRadius: "8px",
          color: C.red,
          marginBottom: "1rem",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem"
        }}>
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div style={{ textAlign: "center", padding: "3rem", color: C.textDim }}>
          <RefreshCw size={24} className="spin" style={{ marginBottom: "1rem" }} />
          <p>Loading actions...</p>
        </div>
      )}

      {/* Empty State */}
      {!loading && filteredActions.length === 0 && (
        <div style={{ 
          textAlign: "center", 
          padding: "4rem 2rem",
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: "12px"
        }}>
          <MessageSquare size={48} color={C.textMuted} style={{ marginBottom: "1rem" }} />
          <h3 style={{ fontFamily: FONT_DISPLAY, fontSize: "1.3rem", color: C.text, marginBottom: "0.5rem" }}>
            No pending messages
          </h3>
          <p style={{ color: C.textDim, fontSize: "0.85rem", marginBottom: "1.5rem" }}>
            Click "Generate Actions" to create WhatsApp messages based on customer order dates.
          </p>
          <button
            onClick={runScheduler}
            disabled={runningScheduler}
            style={{
              background: C.gold, color: C.white, border: "none",
              padding: "0.75rem 1.5rem", borderRadius: "8px", cursor: "pointer",
              fontSize: "0.8rem", fontFamily: FONT_MONO
            }}
          >
            {runningScheduler ? "Generating..." : "Generate Actions Now"}
          </button>
        </div>
      )}

      {/* Actions List */}
      {!loading && filteredActions.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {filteredActions.map((action, idx) => (
            <ActionCard 
              key={action.action_id || `${action.order_id}-${action.day}-${idx}`}
              action={action}
              onSend={() => {
                // Open wa.me link in new tab
                window.open(action.link, '_blank');
                // Mark as sent after a small delay (user may have sent)
                setTimeout(() => {
                  if (window.confirm("Did you send this message? Click OK to mark it as sent.")) {
                    markAsSent(action);
                  }
                }, 1000);
              }}
              onMarkSent={() => markAsSent(action)}
              onDelete={() => deleteAction(action)}
              formatDate={formatDate}
            />
          ))}
        </div>
      )}

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .spin { animation: spin 1s linear infinite; }
      `}</style>
    </div>
  );
}

function StatCard({ icon, label, value, color, bgColor }) {
  return (
    <div style={{
      background: C.surface,
      border: `1px solid ${C.border}`,
      borderRadius: "12px",
      padding: "1.25rem",
      display: "flex",
      alignItems: "center",
      gap: "1rem"
    }}>
      <div style={{
        width: 44, height: 44,
        background: bgColor,
        borderRadius: "10px",
        display: "flex", alignItems: "center", justifyContent: "center",
        color: color
      }}>
        {icon}
      </div>
      <div>
        <div style={{ fontSize: "1.5rem", fontWeight: 600, color: C.text }}>{value}</div>
        <div style={{ fontSize: "0.75rem", color: C.textDim, fontFamily: FONT_MONO, textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div>
      </div>
    </div>
  );
}

function DayPill({ label, emoji, active, onClick, count, color }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", gap: "0.35rem",
        background: active ? (color || C.gold) : C.surface,
        color: active ? C.white : C.textDim,
        border: `1px solid ${active ? (color || C.gold) : C.border}`,
        padding: "0.4rem 0.75rem",
        borderRadius: "20px",
        cursor: "pointer",
        fontSize: "0.72rem",
        fontFamily: FONT_MONO,
        transition: "all 0.2s"
      }}
    >
      {emoji && <span>{emoji}</span>}
      {label}
      {count > 0 && (
        <span style={{
          background: active ? "rgba(255,255,255,0.25)" : C.border,
          padding: "0.1rem 0.4rem",
          borderRadius: "10px",
          fontSize: "0.65rem"
        }}>
          {count}
        </span>
      )}
    </button>
  );
}

function ActionCard({ action, onSend, onMarkSent, onDelete, formatDate }) {
  const [expanded, setExpanded] = useState(false);
  
  // Determine if this is a 28-day cycle message or a loyalty notification
  const actionType = action.action_type || action.type;
  const isLoyaltyAction = actionType && actionType !== 'whatsapp';
  
  // Get label info based on action type
  const labelInfo = isLoyaltyAction 
    ? (ACTION_TYPE_LABELS[actionType] || { label: actionType, color: C.textDim, emoji: "📱" })
    : (DAY_LABELS[action.day] || { label: `Day ${action.day}`, color: C.textDim, emoji: "📱" });

  return (
    <div style={{
      background: C.surface,
      border: `1px solid ${C.border}`,
      borderRadius: "12px",
      overflow: "hidden",
      transition: "all 0.2s"
    }}>
      {/* Header */}
      <div 
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "1rem 1.25rem",
          cursor: "pointer",
          borderBottom: expanded ? `1px solid ${C.border}` : "none"
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          {/* Action Badge */}
          <div style={{
            background: `${labelInfo.color}15`,
            color: labelInfo.color,
            padding: "0.5rem 0.75rem",
            borderRadius: "8px",
            fontSize: "0.7rem",
            fontFamily: FONT_MONO,
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: "0.4rem"
          }}>
            {labelInfo.emoji} {isLoyaltyAction ? labelInfo.label : `Day ${action.day}`}
          </div>
          
          {/* Customer Info */}
          <div>
            <div style={{ fontWeight: 500, color: C.text, fontSize: "0.9rem" }}>
              {action.customer_name || action.customer_email}
            </div>
            <div style={{ 
              display: "flex", 
              alignItems: "center", 
              gap: "0.75rem",
              color: C.textDim, 
              fontSize: "0.75rem",
              marginTop: "0.2rem"
            }}>
              <span style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                <Phone size={12} />
                {action.customer_phone}
              </span>
              <span style={{ color: C.textMuted }}>•</span>
              <span>{formatDate(action.created_at)}</span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: "0.5rem" }} onClick={e => e.stopPropagation()}>
          <button
            onClick={onSend}
            title="Open WhatsApp with pre-filled message"
            style={{
              display: "flex", alignItems: "center", gap: "0.4rem",
              background: "#25D366",
              color: C.white,
              border: "none",
              padding: "0.5rem 1rem",
              borderRadius: "6px",
              cursor: "pointer",
              fontSize: "0.72rem",
              fontFamily: FONT_MONO,
              fontWeight: 500
            }}
          >
            <Send size={14} />
            Send via WhatsApp
            <ExternalLink size={12} />
          </button>
          <button
            onClick={onMarkSent}
            title="Mark as sent without opening WhatsApp"
            style={{
              display: "flex", alignItems: "center", gap: "0.3rem",
              background: "transparent",
              color: C.green,
              border: `1px solid ${C.green}`,
              padding: "0.5rem 0.75rem",
              borderRadius: "6px",
              cursor: "pointer",
              fontSize: "0.72rem",
              fontFamily: FONT_MONO
            }}
          >
            <CheckCircle size={14} />
          </button>
          <button
            onClick={onDelete}
            title="Delete this action"
            style={{
              display: "flex", alignItems: "center", gap: "0.3rem",
              background: "transparent",
              color: C.red,
              border: `1px solid ${C.border}`,
              padding: "0.5rem 0.75rem",
              borderRadius: "6px",
              cursor: "pointer",
              fontSize: "0.72rem",
              fontFamily: FONT_MONO
            }}
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {/* Expanded Message Preview */}
      {expanded && (
        <div style={{ padding: "1.25rem", background: C.surfaceAlt }}>
          <div style={{ 
            fontSize: "0.7rem", 
            color: C.textDim, 
            fontFamily: FONT_MONO, 
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            marginBottom: "0.75rem"
          }}>
            {labelInfo.label} — Message Preview
          </div>
          <div style={{
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: "12px",
            padding: "1rem",
            whiteSpace: "pre-wrap",
            fontSize: "0.85rem",
            color: C.text,
            lineHeight: 1.6,
            fontFamily: "'Inter', sans-serif"
          }}>
            {action.message}
          </div>
          {action.order_id && (
            <div style={{ 
              marginTop: "0.75rem", 
              fontSize: "0.7rem", 
              color: C.textMuted,
              fontFamily: FONT_MONO 
            }}>
              Order: {action.order_id?.slice(0, 8)}...
            </div>
          )}
        </div>
      )}
    </div>
  );
}
