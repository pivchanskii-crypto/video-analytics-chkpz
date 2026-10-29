import { NavLink, useNavigate } from 'react-router-dom';
import {
  Cctv,
  History,
  LayoutDashboard,
  LogOut,
  MonitorPlay,
  ScrollText,
  Shield,
  Settings,
} from 'lucide-react';
import { clearTokens } from '../lib/auth';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/cameras', label: 'Cameras', icon: Cctv },
  { to: '/live', label: 'Live View', icon: MonitorPlay },
  { to: '/timeline', label: 'Timeline', icon: History },
  { to: '/settings', label: 'Settings', icon: Settings },
  { to: '/logs', label: 'System Logs', icon: ScrollText },
];

export default function Sidebar() {
  const navigate = useNavigate();

  function handleLogout() {
    clearTokens();
    navigate('/login', { replace: true });
  }

  return (
    <aside className="fixed inset-y-0 left-0 z-20 flex w-64 flex-col border-r border-slate-200 bg-white">
      <div className="flex h-16 shrink-0 items-center gap-3 border-b border-slate-200 px-4">
        <Shield className="h-7 w-7 text-blue-600" />
        <span className="text-lg font-semibold text-slate-800">
          ЧКПЗ · Видеонаблюдение
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <ul className="space-y-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`
                }
              >
                <Icon className="h-5 w-5" />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="border-t border-slate-200 p-3">
        <button
          type="button"
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50"
        >
          <LogOut className="h-5 w-5" />
          Выйти
        </button>
      </div>
    </aside>
  );
}