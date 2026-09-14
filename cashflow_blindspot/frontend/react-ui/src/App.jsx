import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom';
import { useState } from 'react';
import {
  LayoutDashboard, TrendingUp, TrendingDown, Users,
  Bell, Settings, Wallet, ChevronRight, Upload,
} from 'lucide-react';

import Overview     from './pages/Overview';
import Receivables  from './pages/Receivables';
import Payables     from './pages/Payables';
import Customers    from './pages/Customers';
import Alerts       from './pages/Alerts';
import SettingsPage from './pages/Settings';
import ImportPage   from './pages/Import';

const NAV = [
  { to: '/',             icon: LayoutDashboard, label: 'Overview'     },
  { to: '/receivables',  icon: TrendingUp,      label: 'Receivables'  },
  { to: '/payables',     icon: TrendingDown,    label: 'Payables'     },
  { to: '/customers',    icon: Users,           label: 'Customers'    },
  { to: '/alerts',       icon: Bell,            label: 'Messages'     },
  { to: '/import',       icon: Upload,          label: 'Smart Import' },
  { to: '/settings',     icon: Settings,        label: 'Settings'     },
];

function Sidebar() {
  const loc = useLocation();
  return (
    <aside className="sidebar">
      <div className="sidebar__logo">
        <Wallet size={28} className="sidebar__logo-icon" />
        <div>
          <p className="sidebar__title">CashFlow</p>
          <p className="sidebar__sub">Blindspot AI</p>
        </div>
      </div>
      <nav className="sidebar__nav">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `sidebar__link${isActive ? ' sidebar__link--active' : ''}`
            }
          >
            <Icon size={16} /> {label}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar__footer">
        <span className="status-dot status-dot--alert-ok" />
        <span className="text-muted text-sm">System Online</span>
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <Sidebar />
        <main className="main">
          <Routes>
            <Route path="/"            element={<Overview />}     />
            <Route path="/receivables" element={<Receivables />}  />
            <Route path="/payables"    element={<Payables />}     />
            <Route path="/customers"   element={<Customers />}    />
            <Route path="/alerts"      element={<Alerts />}       />
            <Route path="/import"      element={<ImportPage />}   />
            <Route path="/settings"    element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
