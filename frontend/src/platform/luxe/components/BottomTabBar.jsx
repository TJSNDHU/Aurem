/**
 * BottomTabBar — mobile-only sticky bottom navigation.
 * 5 tabs: Home / Campaign / ORA / Inbox / Settings.
 * Respects safe-area-inset for iPhone home bar.
 */
import React from 'react';
import {
  Home as HomeIcon,
  Zap as CampaignIcon,
  Sparkles as ORAIcon,
  Inbox as InboxIcon,
  Settings as SettingsIcon,
} from 'lucide-react';

const TABS = [
  { k: 'home',       label: 'Home',     icon: HomeIcon },
  { k: 'crm',        label: 'CRM',      icon: CampaignIcon },
  { k: 'ora',        label: 'ORA',      icon: ORAIcon },
  { k: 'campaign',   label: 'Campaign', icon: InboxIcon },
  { k: 'settings',   label: 'Settings', icon: SettingsIcon },
];

export const BottomTabBar = ({ active, onNav }) => (
  <nav data-testid="bottom-tab-bar" className="av2-bottom-tabs" role="tablist">
    {TABS.map(({ k, label, icon: Icon }) => (
      <button
        key={k}
        type="button"
        role="tab"
        data-testid={`bottom-tab-${k}`}
        data-active={active === k}
        aria-selected={active === k}
        onClick={() => onNav?.(k)}
        className="av2-tab"
      >
        <Icon size={20} />
        <span>{label}</span>
      </button>
    ))}
  </nav>
);

export default BottomTabBar;
