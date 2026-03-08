import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../utils/api';

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState('login'); // login | register | confirm
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [form, setForm] = useState({
    username: '', password: '', name: '', email: '', area: '', code: '',
  });

  function update(field, value) {
    setForm(f => ({ ...f, [field]: value }));
  }

  async function handleLogin(e) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const res = await api.auth.login(form.username, form.password);
      localStorage.setItem('access_token', res.access_token);
      localStorage.setItem('refresh_token', res.refresh_token);
      navigate('/');
    } catch (err) {
      setError(err.message || 'Login failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(e) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      // Cognito uses email as the username
      await api.auth.register({
        username: form.email, password: form.password,
        email: form.email, name: form.name, area: form.area,
      });
      setSuccess('Registration successful! Check your email for the verification code.');
      setMode('confirm');
    } catch (err) {
      setError(err.message || 'Registration failed.');
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm(e) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      await api.auth.confirm(form.email, form.code);
      setSuccess('Account verified! You can now log in.');
      setMode('login');
    } catch (err) {
      setError(err.message || 'Invalid verification code.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <div className="logo-circle">✚</div>
          <h1>ASHA Worker Copilot</h1>
          <p>AI-powered health assistant for rural India</p>
        </div>

        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        {/* LOGIN */}
        {mode === 'login' && (
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label className="form-label">Email</label>
              <input className="form-input" type="email" placeholder="your@email.com" required
                value={form.username} onChange={e => update('username', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Password</label>
              <input className="form-input" type="password" placeholder="Your password" required
                value={form.password} onChange={e => update('password', e.target.value)} />
            </div>
            <button className="btn btn-primary btn-full btn-lg" type="submit" disabled={loading}>
              {loading ? <span className="spinner" /> : 'Sign In'}
            </button>
            <div className="text-center mt-4 text-sm text-muted">
              New ASHA worker?{' '}
              <button type="button" className="btn btn-ghost" onClick={() => setMode('register')}
                style={{ fontSize: 13 }}>Register here</button>
            </div>
          </form>
        )}

        {/* REGISTER */}
        {mode === 'register' && (
          <form onSubmit={handleRegister}>
            <div className="form-group">
              <label className="form-label">Full Name</label>
              <input className="form-input" placeholder="Sunita Devi" required
                value={form.name} onChange={e => update('name', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Email</label>
              <input className="form-input" type="email" placeholder="email@example.com" required
                value={form.email} onChange={e => update('email', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Password</label>
              <input className="form-input" type="password" placeholder="Min 8 chars, 1 uppercase, 1 number" required
                value={form.password} onChange={e => update('password', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Assigned Area / Village</label>
              <input className="form-input" placeholder="Gram Panchayat Raipur, Block Sadar" required
                value={form.area} onChange={e => update('area', e.target.value)} />
            </div>
            <button className="btn btn-primary btn-full" type="submit" disabled={loading}>
              {loading ? <span className="spinner" /> : 'Create Account'}
            </button>
            <div className="text-center mt-4 text-sm text-muted">
              Already have an account?{' '}
              <button type="button" className="btn btn-ghost" onClick={() => setMode('login')}
                style={{ fontSize: 13 }}>Sign in</button>
            </div>
          </form>
        )}

        {/* CONFIRM */}
        {mode === 'confirm' && (
          <form onSubmit={handleConfirm}>
            <p className="text-sm text-muted mb-4">
              Enter the 6-digit code sent to your email to verify your account.
            </p>
            <div className="form-group">
              <label className="form-label">Verification Code</label>
              <input className="form-input" placeholder="123456" required maxLength={6}
                value={form.code} onChange={e => update('code', e.target.value)} />
            </div>
            <button className="btn btn-primary btn-full" type="submit" disabled={loading}>
              {loading ? <span className="spinner" /> : 'Verify Account'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
