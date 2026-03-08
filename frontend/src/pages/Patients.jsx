import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, ChevronRight } from 'lucide-react';
import { api } from '../utils/api';

const PATIENT_TYPES = ['general', 'pregnant', 'child'];

export default function Patients() {
  const navigate = useNavigate();
  const [patients, setPatients] = useState([]);
  const [search, setSearch] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [form, setForm] = useState({
    name: '', age: '', gender: 'female', date_of_birth: '',
    village: '', contact_number: '', patient_type: 'general',
    chronic_conditions: '', allergies: '',
    gestational_age_weeks: '', last_menstrual_period: '',
  });

  useEffect(() => { api.patients.list().then(setPatients).finally(() => setLoading(false)); }, []);

  function update(k, v) { setForm(f => ({ ...f, [k]: v })); }

  async function addPatient(e) {
    e.preventDefault();
    setError(''); setSaving(true);
    try {
      const payload = {
        name: form.name, age: parseInt(form.age, 10),
        gender: form.gender, date_of_birth: form.date_of_birth,
        village: form.village, contact_number: form.contact_number || undefined,
        patient_type: form.patient_type,
        chronic_conditions: form.chronic_conditions ? form.chronic_conditions.split(',').map(s => s.trim()) : [],
        allergies: form.allergies ? form.allergies.split(',').map(s => s.trim()) : [],
        gestational_age_weeks: form.gestational_age_weeks ? parseInt(form.gestational_age_weeks, 10) : undefined,
        last_menstrual_period: form.last_menstrual_period || undefined,
      };
      const newP = await api.patients.create(payload);
      setPatients(p => [newP, ...p]);
      setSuccess(`Patient ${newP.name} added successfully!`);
      setShowAdd(false);
      setForm({ name: '', age: '', gender: 'female', date_of_birth: '', village: '', contact_number: '', patient_type: 'general', chronic_conditions: '', allergies: '', gestational_age_weeks: '', last_menstrual_period: '' });
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const filtered = patients.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.village.toLowerCase().includes(search.toLowerCase())
  );

  const typeColors = { general: '#dbeafe', pregnant: '#f3e8ff', child: '#dcfce7' };
  const typeTextColors = { general: '#2563eb', pregnant: '#7c3aed', child: '#16a34a' };

  return (
    <div>
      <div className="page-header">
        <div className="flex items-center justify-between">
          <div>
            <div className="page-title">Patients</div>
            <div className="page-subtitle">{patients.length} patients assigned to you</div>
          </div>
          <button className="btn btn-primary" onClick={() => setShowAdd(!showAdd)}>
            <Plus size={16} /> Add Patient
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Add patient form */}
      {showAdd && (
        <div className="card mb-4">
          <div className="card-title">New Patient</div>
          <form onSubmit={addPatient}>
            <div className="grid-2">
              <div className="form-group">
                <label className="form-label">Full Name *</label>
                <input className="form-input" required value={form.name} onChange={e => update('name', e.target.value)} placeholder="Sunita Devi" />
              </div>
              <div className="form-group">
                <label className="form-label">Age *</label>
                <input className="form-input" type="number" required value={form.age} onChange={e => update('age', e.target.value)} placeholder="28" />
              </div>
              <div className="form-group">
                <label className="form-label">Gender *</label>
                <select className="form-select" value={form.gender} onChange={e => update('gender', e.target.value)}>
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Date of Birth *</label>
                <input className="form-input" type="date" required value={form.date_of_birth} onChange={e => update('date_of_birth', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Village *</label>
                <input className="form-input" required value={form.village} onChange={e => update('village', e.target.value)} placeholder="Raipur" />
              </div>
              <div className="form-group">
                <label className="form-label">Contact Number</label>
                <input className="form-input" value={form.contact_number} onChange={e => update('contact_number', e.target.value)} placeholder="9876543210" />
              </div>
              <div className="form-group">
                <label className="form-label">Patient Type *</label>
                <select className="form-select" value={form.patient_type} onChange={e => update('patient_type', e.target.value)}>
                  {PATIENT_TYPES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Chronic Conditions (comma-separated)</label>
                <input className="form-input" value={form.chronic_conditions} onChange={e => update('chronic_conditions', e.target.value)} placeholder="Diabetes, Hypertension" />
              </div>
            </div>
            {form.patient_type === 'pregnant' && (
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">Gestational Age (weeks)</label>
                  <input className="form-input" type="number" value={form.gestational_age_weeks} onChange={e => update('gestational_age_weeks', e.target.value)} placeholder="24" />
                </div>
                <div className="form-group">
                  <label className="form-label">Last Menstrual Period</label>
                  <input className="form-input" type="date" value={form.last_menstrual_period} onChange={e => update('last_menstrual_period', e.target.value)} />
                </div>
              </div>
            )}
            <div className="flex gap-2 mt-2">
              <button className="btn btn-primary" type="submit" disabled={saving}>
                {saving ? <span className="spinner" /> : 'Add Patient'}
              </button>
              <button className="btn btn-outline" type="button" onClick={() => setShowAdd(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Search */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <Search size={16} color="#94a3b8" />
          <input
            className="form-input" placeholder="Search by name or village..."
            style={{ border: 'none', outline: 'none', padding: '4px 0', flex: 1, background: 'none' }}
            value={search} onChange={e => setSearch(e.target.value)}
          />
        </div>
        {loading ? (
          <div className="text-muted text-sm">Loading patients...</div>
        ) : filtered.length === 0 ? (
          <div className="text-muted text-sm" style={{ padding: '16px 0', textAlign: 'center' }}>
            {patients.length === 0 ? 'No patients yet. Click "Add Patient" to get started.' : 'No patients match your search.'}
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th><th>Age</th><th>Village</th><th>Type</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(p => (
                  <tr key={p.patient_id}>
                    <td style={{ fontWeight: 600 }}>{p.name}</td>
                    <td>{p.age}</td>
                    <td>{p.village}</td>
                    <td>
                      <span style={{
                        background: typeColors[p.patient_type] || '#f1f5f9',
                        color: typeTextColors[p.patient_type] || '#475569',
                        padding: '2px 9px', borderRadius: 12, fontSize: 11, fontWeight: 700,
                      }}>
                        {p.patient_type}
                      </span>
                    </td>
                    <td>
                      <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/patients/${p.patient_id}`)}>
                        View <ChevronRight size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
