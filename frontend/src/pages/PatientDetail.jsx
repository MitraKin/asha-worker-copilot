import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Stethoscope } from 'lucide-react';
import { api } from '../utils/api';

const RISK_COLORS = { low: '#16a34a', medium: '#d97706', high: '#ea580c', critical: '#dc2626' };

export default function PatientDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.patients.history(id).then(setData).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="text-muted text-sm mt-2">Loading patient details...</div>;
  if (!data) return <div className="alert alert-error">Patient not found.</div>;

  const { patient, assessments, vaccinations } = data;

  return (
    <div>
      <div className="page-header">
        <button className="btn btn-ghost mb-2" onClick={() => navigate('/patients')}>
          <ArrowLeft size={15} /> Back to Patients
        </button>
        <div className="flex items-center justify-between">
          <div>
            <div className="page-title">{patient.name}</div>
            <div className="page-subtitle">
              {patient.age}yr · {patient.gender} · {patient.village}
              {patient.patient_type !== 'general' && ` · ${patient.patient_type}`}
            </div>
          </div>
          <button className="btn btn-primary" onClick={() => navigate('/assessment', { state: { patientId: id } })}>
            <Stethoscope size={15} /> New Assessment
          </button>
        </div>
      </div>

      <div className="grid-2">
        {/* Patient info */}
        <div className="card">
          <div className="card-title">Patient Info</div>
          {[
            ['Date of Birth', patient.date_of_birth?.slice(0, 10) || 'N/A'],
            ['Contact', patient.contact_number || 'N/A'],
            ['Chronic Conditions', patient.chronic_conditions?.join(', ') || 'None'],
            ['Allergies', patient.allergies?.join(', ') || 'None'],
            ...(patient.patient_type === 'pregnant' ? [
              ['Gestational Age', patient.gestational_age_weeks ? `${patient.gestational_age_weeks} weeks` : 'N/A'],
              ['Last Menstrual Period', patient.last_menstrual_period?.slice(0, 10) || 'N/A'],
            ] : []),
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between" style={{ padding: '8px 0', borderBottom: '1px solid #f1f5f9' }}>
              <span className="text-sm text-muted">{label}</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#334155' }}>{value}</span>
            </div>
          ))}
        </div>

        {/* Assessment history */}
        <div className="card">
          <div className="card-title">Assessment History ({assessments.length})</div>
          {assessments.length === 0 ? (
            <div className="text-muted text-sm">No assessments yet.</div>
          ) : assessments.slice(0, 8).map(a => (
            <div key={a.assessment_id} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '10px 0', borderBottom: '1px solid #f1f5f9',
            }}>
              <div style={{
                width: 10, height: 10, borderRadius: '50%',
                background: RISK_COLORS[a.risk_level] || '#94a3b8', flexShrink: 0,
              }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 600, textTransform: 'capitalize' }}>
                  {a.risk_level} Risk
                  {a.emergency_detected && ' ⚠️ Emergency'}
                </div>
                <div className="text-xs text-muted">
                  {a.created_at?.slice(0, 10)} · Score: {a.risk_score || 'N/A'}
                </div>
              </div>
              <span className={`badge badge-${a.risk_level}`}>{a.risk_level}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Vaccination summary */}
      {vaccinations.length > 0 && (
        <div className="card mt-4">
          <div className="card-title">Vaccination Records ({vaccinations.length})</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
            {vaccinations.slice(0, 12).map((v, i) => (
              <div key={i} className={`vacc-item ${v.is_administered ? 'done' : 'pending'}`}>
                <div className={`vacc-check ${v.is_administered ? 'done' : 'pending'}`}>
                  {v.is_administered ? '✓' : '—'}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{v.vaccine_name}</div>
                  <div className="text-xs text-muted">
                    {v.is_administered ? `Done: ${v.administered_date?.slice(0, 10)}` : `Due: ${v.due_date?.slice(0, 10)}`}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
