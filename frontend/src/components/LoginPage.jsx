import React, { useState } from 'react';
import { getApiBase, apiFetch } from '../config';
import { IconMail, IconShield, IconAlert } from './Icons';

export default function LoginPage({ onLoggedIn }) {
  const API_BASE = getApiBase();
  const [step, setStep] = useState('email'); // 'email' | 'otp'
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const extractError = async (resp) => {
    try {
      const data = await resp.json();
      const detail = data.detail || data.message || data.error;
      return typeof detail === 'string' ? detail : 'Something went wrong. Please try again.';
    } catch {
      return 'Something went wrong. Please try again.';
    }
  };

  const handleRequestOtp = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    setError('');
    try {
      const resp = await apiFetch(`${API_BASE}/auth/login/request-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() }),
      });
      if (!resp.ok) {
        setError(await extractError(resp));
        return;
      }
      setStep('otp');
    } catch {
      setError('Could not reach the server. Check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    if (!otp.trim()) return;
    setLoading(true);
    setError('');
    try {
      const resp = await apiFetch(`${API_BASE}/auth/login/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), otp: otp.trim() }),
      });
      if (!resp.ok) {
        setError(await extractError(resp));
        return;
      }
      const data = await resp.json();
      onLoggedIn(data.email);
    } catch {
      setError('Could not reach the server. Check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page-wrapper">
      <div className="login-card">
        <div className="login-brand">
          <img src="/logo.png" alt="" className="brand-logo-img" width="44" height="44" />
          <span className="brand-name" style={{ fontSize: '1.3rem' }}>Profile Bot AI</span>
        </div>

        {step === 'email' ? (
          <>
            <h1 className="login-title">Sign in to continue</h1>
            <p className="login-subtitle">Use your company email — we'll send a one-time code.</p>

            <form onSubmit={handleRequestOtp} className="login-form">
              <label className="login-input-wrap">
                <IconMail size={16} color="#94A3B8" />
                <input
                  type="email"
                  className="login-input"
                  placeholder="you@snypartech.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoFocus
                  required
                />
              </label>

              {error && (
                <div className="login-error">
                  <IconAlert size={14} color="#EF4444" />
                  <span>{error}</span>
                </div>
              )}

              <button type="submit" className="btn-primary-action" disabled={loading}>
                {loading ? <span className="spinner-light-sm" /> : 'Send code'}
              </button>
            </form>
          </>
        ) : (
          <>
            <h1 className="login-title">Enter your code</h1>
            <p className="login-subtitle">We sent a 6-digit code to <strong>{email}</strong>.</p>

            <form onSubmit={handleVerifyOtp} className="login-form">
              <label className="login-input-wrap">
                <IconShield size={16} color="#94A3B8" />
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  className="login-input login-otp-input"
                  placeholder="000000"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                  autoFocus
                  required
                />
              </label>

              {error && (
                <div className="login-error">
                  <IconAlert size={14} color="#EF4444" />
                  <span>{error}</span>
                </div>
              )}

              <button type="submit" className="btn-primary-action" disabled={loading}>
                {loading ? <span className="spinner-light-sm" /> : 'Verify & sign in'}
              </button>

              <button
                type="button"
                className="login-back-link"
                onClick={() => { setStep('email'); setOtp(''); setError(''); }}
              >
                Use a different email
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
