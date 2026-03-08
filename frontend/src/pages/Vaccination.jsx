import React, { useEffect, useState } from 'react';
import { api } from '../utils/api';

export default function Vaccination() {
  const [patients, setPatients] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [schedule, setSchedule] = useState(null);
  const [summary, setSummary] = useState(null);
  const [dueVaccines, setDueVaccines] = useState([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [recording, setRecording] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    api.patients.list().then(setPatients);
    api.vaccination.dueVaccinations(14).then(setDueVaccines);
  }, []);

  async function loadSchedule(id) {
    if (!id) return;
    setLoading(true); setError('');
    try {
      const [sched, sum] = await Promise.all([
        api.vaccination.getSchedule(id),
        api.vaccination.summary(id),
      ]);
      setSchedule(sched); setSummary(sum);
    } catch {
      setSchedule(null);
    } finally {
      setLoading(false);
    }
  }

  async function generateSchedule() {
    setGenerating(true); setError('');
    try {
      const sched = await api.vaccination.generateSchedule(selectedId);
      setSchedule(sched);
      const sum = await api.vaccination.summary(selectedId);
      setSummary(sum);
      setSuccess('Vaccination schedule generated successfully!');
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  }

  async function recordVaccination(vaccineName) {
    const today = new Date().toISOString().slice(0, 10);
    setRecording(vaccineName);
    try {
      await api.vaccination.record(selectedId, {
        patient_id: selectedId,
        vaccine_name: vaccineName,
        administered_date: today,
      });
      setSuccess(`${vaccineName} recorded as administered!`);
      await loadSchedule(selectedId);
    } catch (err) {
      setError(err.message);
    } finally {
      setRecording(null);
    }
  }

  function selectPatient(id) {
    setSelectedId(id); setSchedule(null); setSummary(null);
    if (id) loadSchedule(id);
  }

  const today = new Date().toISOString().slice(0, 10);
  const getStatus = (v) => {
    if (v.is_administered) return 'done';
    if (v.due_date?.slice(0, 10) < today) return 'overdue';
    const diff = Math.floor((new Date(v.due_date) - new Date()) / 86400000);
    if (diff <= 7) return 'upcoming';
    return 'pending';
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-title">Vaccination Tracker</div>
        <div className="page-subtitle">Track immunization schedules and record administered vaccines</div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      <div className="grid-2">
        {/* Left: Patient schedule */}
        <div>
          <div className="card mb-4">
            <div className="card-title">Patient Vaccination Schedule</div>
            <div className="form-group">
              <label className="form-label">Select Patient</label>
              <select className="form-select" value={selectedId} onChange={e => selectPatient(e.target.value)}>
                <option value="">-- Choose patient --</option>
                {patients.filter(p => p.patient_type !== 'general').map(p => (
                  <option key={p.patient_id} value={p.patient_id}>
                    {p.name} ({p.patient_type})
                  </option>
                ))}
              </select>
              <div className="text-xs text-muted mt-1">Only children and pregnant women have vaccination schedules</div>
            </div>

            {selectedId && !schedule && !loading && (
              <button className="btn btn-primary btn-full" onClick={generateSchedule} disabled={generating}>
                {generating ? <><span className="spinner" /> Generating...</> : '💉 Generate Schedule (Govt. of India UIP)'}
              </button>
            )}
          </div>

          {/* Summary stats */}
          {summary && (
            <div className="card mb-4">
              <div className="card-title">{schedule?.patient_name}'s Summary</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
                {[
                  { label: 'Total', value: summary.total, color: '#334155' },
                  { label: 'Done', value: summary.completed, color: '#16a34a' },
                  { label: 'Upcoming', value: summary.upcoming, color: '#d97706' },
                  { label: 'Overdue', value: summary.overdue, color: '#dc2626' },
                ].map(s => (
                  <div key={s.label} style={{ textAlign: 'center', padding: '10px 0' }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: s.color }}>{s.value}</div>
                    <div className="text-xs text-muted">{s.label}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Vaccine list */}
          {schedule && (
            <div className="card">
              <div className="card-title">Vaccines ({schedule.vaccinations.length})</div>
              {loading ? <div className="text-muted text-sm">Loading...</div> : (
                schedule.vaccinations.map((v, i) => {
                  const status = getStatus(v);
                  return (
                    <div key={i} className={`vacc-item ${status}`}>
                      <div className={`vacc-check ${status}`}>
                        {status === 'done' ? '✓' : status === 'overdue' ? '!' : status === 'upcoming' ? '⏰' : '—'}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 600 }}>{v.vaccine_name}</div>
                        <div className="text-xs text-muted">{v.age_at_administration} · Due: {v.due_date?.slice(0, 10)}</div>
                      </div>
                      {!v.is_administered && (
                        <button
                          className="btn btn-outline btn-sm"
                          onClick={() => recordVaccination(v.vaccine_name)}
                          disabled={recording === v.vaccine_name}
                          style={{ fontSize: 11 }}
                        >
                          {recording === v.vaccine_name ? '...' : 'Record'}
                        </button>
                      )}
                      {v.is_administered && (
                        <span className="badge badge-done">DONE</span>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>

        {/* Right: All due vaccinations */}
        <div className="card">
          <div className="card-title">⏰ Vaccinations Due (Next 14 Days) — {dueVaccines.length}</div>
          {dueVaccines.length === 0 ? (
            <div className="text-muted text-sm" style={{ padding: '12px 0' }}>
              ✅ No vaccinations due in the next 14 days.
            </div>
          ) : (
            dueVaccines.map((v, i) => (
              <div key={i} className={`vacc-item ${v.status}`}>
                <div className={`vacc-check ${v.status === 'overdue' ? 'overdue' : 'upcoming'}`}>
                  {v.status === 'overdue' ? '!' : '⏰'}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{v.vaccine_name}</div>
                  <div className="text-xs text-muted">{v.patient_name} · Due: {v.due_date?.slice(0, 10)}</div>
                </div>
                <span className={`badge badge-${v.status === 'overdue' ? 'overdue' : 'upcoming'}`}>
                  {v.status === 'overdue' ? `${v.days_overdue}d late` : `${v.days_until_due}d`}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
