import { memo } from 'react';
import { FileText, KeyRound, LayoutDashboard, Database, Settings, UserRound } from 'lucide-react';

const USER_MENU_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'manual', label: 'Manual', icon: FileText },
  { id: 'userdetails', label: 'User Details', icon: UserRound },
];

const ADMIN_MENU_ITEMS = [
  ...USER_MENU_ITEMS,
  { id: 'master', label: 'Master', icon: Database },
  { id: 'credentials', label: 'Credentials', icon: KeyRound },
  { id: 'settings', label: 'Settings', icon: Settings },
];

function Sidebar({ role = 'user', activeTab = 'dashboard', onTabChange }) {
  const menuItems = role === 'admin' ? ADMIN_MENU_ITEMS : USER_MENU_ITEMS;

  return (
    <nav className="side-nav" aria-label="Main navigation">
      {menuItems.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          className={`nav-item ${activeTab === id ? 'active' : ''}`}
          aria-current={activeTab === id ? 'page' : undefined}
          onClick={() => onTabChange && onTabChange(id)}
        >
          <Icon size={16} />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}

export default memo(Sidebar);
