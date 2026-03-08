import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users, Syringe, AlertTriangle, Activity, ArrowRight } from 'lucide-react';
import { api } from '../utils/api';

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [dueVaccines, setDueVaccines] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.patients.stats(), api.vaccination.dueVaccinations(7)])
      .then(([s, v]) => { setStats(s); setDueVaccines(v); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="text-center mt-4 text-muted">
        <div className="spinner" style={{ borderTopColor: '#16a34a', borderColor: 'rgba(22,163,74,0.2)', width: 32, height: 32 }} />
        <p className="mt-2">Loading dashboard...</p>
      </div>
    );
  }

  const user = stats || {};
  const today = new Date().toLocaleDateString('en-IN', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div className="flex items-center justify-between">
          <div>
            <div className="page-title">Namaste, {user.asha_worker_name || 'ASHA Worker'} 🙏</div>
            <div className="page-subtitle">{user.area || 'Community Health Worker'} · {today}</div>
          </div>
          <button className="btn btn-primary" onClick={() => navigate('/assessment')}>
            Start New Assessment
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon" style={{ background: '#dcfce7' }}>
            <Users size={22} color="#15803d" />
          </div>
          <div>
            <div className="stat-num">{user.total_patients || 0}</div>
            <div className="stat-lbl">Total Patients</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: '#f3e8ff' }}>
            <Activity size={22} color="#7c3aed" />
          </div>
          <div>
            <div className="stat-num">{user.pregnant_patients || 0}</div>
            <div className="stat-lbl">Pregnant Women</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: '#dbeafe' }}>
            <Users size={22} color="#2563eb" />
          </div>
          <div>
            <div className="stat-num">{user.child_patients || 0}</div>
            <div className="stat-lbl">Children</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: '#fef3c7' }}>
            <Syringe size={22} color="#d97706" />
          </div>
          <div>
            <div className="stat-num">{user.due_vaccinations || 0}</div>
            <div className="stat-lbl">Vaccines Due (7 days)</div>
          </div>
        </div>
      </div>

      <div className="grid-2">
        {/* Quick actions */}
        <div className="card">
          <div className="card-title">Quick Actions</div>
          {[
            { label: 'Start Health Assessment', sub: 'Voice or text-based', path: '/assessment', color: '#dcfce7', accent: '#16a34a', icon: '🩺' },
            { label: 'Manage Patients', sub: 'Add or view patient records', path: '/patients', color: '#dbeafe', accent: '#2563eb', icon: '👥' },
            { label: 'Vaccination Tracker', sub: 'View schedules & reminders', path: '/vaccination', color: '#fef3c7', accent: '#d97706', icon: '💉' },
          ].map(({ label, sub, path, color, accent, icon }) => (
            <div
              key={path}
              onClick={() => navigate(path)}
              style={{
                display: 'flex', alignItems: 'center', gap: 14,
                padding: '14px', background: color, borderRadius: 10, marginBottom: 10,
                cursor: 'pointer', transition: 'all 0.15s', border: `1.5px solid ${accent}20`,
              }}
            >
              <div style={{ fontSize: 22 }}>{icon}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, fontSize: 13, color: '#1e293b' }}>{label}</div>
                <div style={{ fontSize: 11, color: '#64748b', marginTop: 1 }}>{sub}</div>
              </div>
              <ArrowRight size={16} color={accent} />
            </div>
          ))}
        </div>

        {/* Due vaccinations */}
        <div className="card">
          <div className="card-title">
            <span style={{ marginRight: 8 }}>💉</span>
            Vaccines Due Soon ({dueVaccines.length})
          </div>
          {dueVaccines.length === 0 ? (
            <div className="text-muted text-sm" style={{ padding: '12px 0' }}>
              ✅ No vaccinations due in the next 7 days!
            </div>
          ) : (
            dueVaccines.slice(0, 6).map((v, i) => (
              <div key={i} className={`vacc-item ${v.status === 'overdue' ? 'overdue' : 'upcoming'}`}>
                <div className={`vacc-check ${v.status === 'overdue' ? 'overdue' : 'upcoming'}`}>
                  {v.status === 'overdue' ? '!' : '⏰'}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{v.vaccine_name}</div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>{v.patient_name}</div>
                </div>
                <span className={`badge badge-${v.status === 'overdue' ? 'overdue' : 'upcoming'}`}>
                  {v.status === 'overdue'
                    ? `${v.days_overdue}d late`
                    : `Due in ${v.days_until_due}d`}
                </span>
              </div>
            ))
          )}
          {dueVaccines.length > 0 && (
            <button className="btn btn-outline btn-sm btn-full mt-2"
              onClick={() => navigate('/vaccination')}>
              View All
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
