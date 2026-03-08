import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, Send, AlertTriangle, Volume2 } from 'lucide-react';
import { api } from '../utils/api';

const LANGUAGES = [
  { code: 'hi-IN', label: 'हिंदी (Hindi)' },
  { code: 'en-IN', label: 'English (India)' },
  { code: 'ta-IN', label: 'தமிழ் (Tamil)' },
  { code: 'te-IN', label: 'తెలుగు (Telugu)' },
  { code: 'kn-IN', label: 'ಕನ್ನಡ (Kannada)' },
  { code: 'bn-IN', label: 'বাংলা (Bengali)' },
  { code: 'mr-IN', label: 'मराठी (Marathi)' },
];

function RiskResult({ result }) {
  const level = result.risk_level || 'medium';
  const isEmergency = result.emergency_detected;

  if (isEmergency) {
    return (
      <div className="emergency-banner">
        <div className="emergency-title">⚠️ EMERGENCY DETECTED</div>
        <div className="emergency-sub">{result.message}</div>
        <button
          className="btn btn-danger btn-full"
          style={{ marginTop: 16, fontSize: 16, padding: '14px', letterSpacing: 0.5 }}
          onClick={() => window.open('tel:108')}
        >
          📞 CALL 108 NOW
        </button>
      </div>
    );
  }

  return (
    <div className={`risk-badge ${level}`}>
      <div className="risk-label-text">Risk Level</div>
      <div className="risk-level-text">{level.toUpperCase()}</div>
      {result.risk_score !== undefined && (
        <div className="risk-score-text">Score: {result.risk_score} / 100</div>
      )}
    </div>
  );
}

export default function Assessment() {
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState('');
  const [language, setLanguage] = useState('hi-IN');
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [textInput, setTextInput] = useState('');
  const [recording, setRecording] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState('select'); // select | chatting | complete
  const mediaRef = useRef(null);
  const chunksRef = useRef([]);
  const chatEndRef = useRef(null);

  useEffect(() => {
    api.patients.list().then(setPatients).catch(() => {});
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function startSession() {
    if (!selectedPatient) { setError('Please select a patient first.'); return; }
    setError(''); setLoading(true);
    try {
      const resp = await api.assessment.start({
        patient_id: selectedPatient,
        language,
        assessment_type: 'general',
      });
      setSession(resp);
      setMessages([{ role: 'ai', text: resp.message, audio: resp.audio_response_url }]);
      setStep('chatting');
      if (resp.audio_response_url) playAudio(resp.audio_response_url);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function sendText() {
    if (!textInput.trim() || !session) return;
    const userText = textInput.trim();
    setTextInput('');
    setMessages(m => [...m, { role: 'user', text: userText }]);
    setLoading(true);
    try {
      const resp = await api.assessment.sendText({
        session_id: session.session_id,
        text_input: userText,
        language,
      });
      setMessages(m => [...m, { role: 'ai', text: resp.message, audio: resp.audio_response_url, result: resp.is_complete ? resp : null }]);
      if (resp.audio_response_url) playAudio(resp.audio_response_url);
      if (resp.is_complete) setStep('complete');
      setSession(resp);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function startRecording() {
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = e => chunksRef.current.push(e.data);
      mr.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/wav' });
        const reader = new FileReader();
        reader.onload = async () => {
          const b64 = reader.result.split(',')[1];
          setLoading(true);
          try {
            const resp = await api.assessment.sendAudio({
              session_id: session.session_id,
              audio_base64: b64,
              source_language: language,
            });
            setMessages(m => [...m,
              { role: 'user', text: '🎤 Voice input sent' },
              { role: 'ai', text: resp.message, audio: resp.audio_response_url, result: resp.is_complete ? resp : null }
            ]);
            if (resp.audio_response_url) playAudio(resp.audio_response_url);
            if (resp.is_complete) setStep('complete');
            setSession(resp);
          } catch (err) {
            setError(err.message);
          } finally {
            setLoading(false);
          }
        };
        reader.readAsDataURL(blob);
        stream.getTracks().forEach(t => t.stop());
      };
      mr.start();
      mediaRef.current = mr;
      setRecording(true);
    } catch {
      setError('Microphone access denied. Please allow microphone access.');
    }
  }

  function stopRecording() {
    mediaRef.current?.stop();
    setRecording(false);
  }

  function playAudio(b64) {
    try {
      const audio = new Audio(`data:audio/mp3;base64,${b64}`);
      audio.play();
    } catch {}
  }

  function reset() {
    setSession(null); setMessages([]); setStep('select');
    setSelectedPatient(''); setError('');
  }

  const questionNum = session?.question_number || 0;

  return (
    <div>
      <div className="page-header">
        <div className="page-title">Health Assessment</div>
        <div className="page-subtitle">AI-guided voice and text assessment in regional languages</div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {/* STEP 1: Select patient */}
      {step === 'select' && (
        <div className="card" style={{ maxWidth: 560 }}>
          <div className="card-title">Start New Assessment</div>
          <div className="form-group">
            <label className="form-label">Select Patient</label>
            <select className="form-select" value={selectedPatient} onChange={e => setSelectedPatient(e.target.value)}>
              <option value="">-- Choose a patient --</option>
              {patients.map(p => (
                <option key={p.patient_id} value={p.patient_id}>
                  {p.name} — {p.age}yr — {p.village}
                </option>
              ))}
            </select>
            {patients.length === 0 && (
              <div className="text-muted text-sm mt-1">No patients yet. <a href="/patients">Add a patient first.</a></div>
            )}
          </div>
          <div className="form-group">
            <label className="form-label">Language</label>
            <select className="form-select" value={language} onChange={e => setLanguage(e.target.value)}>
              {LANGUAGES.map(l => (
                <option key={l.code} value={l.code}>{l.label}</option>
              ))}
            </select>
          </div>
          <button className="btn btn-primary btn-full" onClick={startSession} disabled={loading || !selectedPatient}>
            {loading ? <><span className="spinner" /> Starting...</> : '🩺 Start Assessment'}
          </button>
        </div>
      )}

      {/* STEP 2: Chat */}
      {step === 'chatting' && (
        <div className="card" style={{ maxWidth: 680 }}>
          {/* Patient + progress */}
          <div className="flex items-center justify-between mb-4">
            <div>
              <div style={{ fontWeight: 700, fontSize: 14 }}>
                {patients.find(p => p.patient_id === selectedPatient)?.name || 'Patient'}
              </div>
              <div className="text-xs text-muted">Question {questionNum} of 10 · {language}</div>
            </div>
            <span className="badge badge-info">Q{questionNum}/10</span>
          </div>

          <div className="progress-bar mb-4">
            <div className="progress-fill" style={{ width: `${(questionNum / 10) * 100}%` }} />
          </div>

          {/* Chat */}
          <div className="chat-area" style={{ maxHeight: 360, overflowY: 'auto', marginBottom: 16 }}>
            {messages.map((m, i) => (
              <div key={i} className={`chat-bubble ${m.role}`}>
                <div className="sender">{m.role === 'ai' ? '🤖 AI Assistant' : '👤 You'}</div>
                {m.text}
                {m.audio && (
                  <button onClick={() => playAudio(m.audio)}
                    className="btn btn-ghost btn-sm"
                    style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 6, padding: '4px 8px', fontSize: 11 }}>
                    <Volume2 size={12} /> Play
                  </button>
                )}
              </div>
            ))}
            {loading && (
              <div className="chat-bubble ai text-muted" style={{ opacity: 0.6 }}>
                <div className="sender">🤖 AI Assistant</div>
                Thinking...
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="flex gap-2 items-center" style={{ flexWrap: 'wrap' }}>
            {/* Voice button */}
            <button
              className={`voice-btn ${recording ? 'recording' : 'idle'}`}
              onClick={recording ? stopRecording : startRecording}
              title={recording ? 'Stop recording' : 'Hold to speak'}
            >
              {recording ? <MicOff size={28} color="white" /> : <Mic size={28} color="white" />}
            </button>

            {/* Text input */}
            <input
              className="form-input" placeholder="Or type your response here..."
              style={{ flex: 1, minWidth: 200 }}
              value={textInput}
              onChange={e => setTextInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') sendText(); }}
            />
            <button className="btn btn-primary" onClick={sendText} disabled={!textInput.trim() || loading}>
              <Send size={15} />
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: Complete */}
      {step === 'complete' && session && (
        <div style={{ maxWidth: 660 }}>
          {session.emergency_detected && (
            <RiskResult result={session} />
          )}
          {!session.emergency_detected && (
            <>
              <RiskResult result={session} />
              <div className="card mb-4">
                <div className="card-title">Assessment Complete</div>
                <div style={{ fontSize: 13.5, color: '#334155', lineHeight: 1.65 }}>
                  {messages[messages.length - 1]?.text}
                </div>
              </div>
            </>
          )}
          <button className="btn btn-outline btn-full" onClick={reset}>
            Start New Assessment
          </button>
        </div>
      )}
    </div>
  );
}
