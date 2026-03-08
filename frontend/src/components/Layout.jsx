import React, { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Stethoscope, Users, Syringe, LogOut, Cross } from 'lucide-react';
import { api } from '../utils/api';

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', exact: true },
  { to: '/assessment', icon: Stethoscope, label: 'Assessment' },
  { to: '/patients', icon: Users, label: 'Patients' },
  { to: '/vaccination', icon: Syringe, label: 'Vaccination' },
];

export default function Layout({ children }) {
  const navigate = useNavigate();
  const [user, setUser] = useState({ name: 'ASHA Worker', area: '' });

  useEffect(() => {
    api.auth.me().then(u => setUser(u)).catch(() => {});
  }, []);

  function logout() {
    localStorage.clear();
    navigate('/login');
  }

  const initials = user.name?.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase() || 'AW';

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">✚</div>
          <div>
            <div className="logo-text">ASHA Copilot</div>
            <div className="logo-sub">AI Health Assistant</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map(({ to, icon: Icon, label, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
            >
              <Icon size={17} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="user-card">
            <div className="user-avatar">{initials}</div>
            <div>
              <div className="user-name">{user.name || 'ASHA Worker'}</div>
              <div className="user-role">{user.area || 'Community Health Worker'}</div>
            </div>
          </div>
          <button className="logout-btn" onClick={logout}>
            <LogOut size={13} style={{ marginRight: 6 }} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="page-area">{children}</main>
    </div>
  );
}
