// BlackBoard/ui/src/components/LoginPage.tsx
// @ai-rules:
// 1. [Pattern]: Background image from /projectDarwin.png (ui/public/). No overlay card.
// 2. [Pattern]: Disclaimer default in component. Override via config.auth.loginDisclaimer if non-empty.
// 3. [Pattern]: Login button hidden -- revealed on hover over "PROJECT DARWIN" title zone.
import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

const DEFAULT_DISCLAIMER =
  'This system uses AI to autonomously manage infrastructure. ' +
  'AI-generated actions should be reviewed before acting on them.';

const LoginPage = () => {
  const { login, authConfig, isLoading } = useAuth();
  const disclaimer = authConfig?.loginDisclaimer || DEFAULT_DISCLAIMER;
  const [showLogin, setShowLogin] = useState(false);

  return (
    <div style={{
      position: 'fixed', inset: 0,
      backgroundImage: 'url(/projectDarwin.png)',
      backgroundSize: 'cover',
      backgroundPosition: 'center',
      backgroundRepeat: 'no-repeat',
      backgroundColor: '#030712',
    }}>
      {/* Animated energy particles + swirl effects */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden' }}>
        {/* Traveling particles */}
        <div className="energy-particle particle-cyan p1" />
        <div className="energy-particle particle-cyan p2" />
        <div className="energy-particle particle-orange p3" />
        <div className="energy-particle particle-orange p4" />
        <div className="energy-particle particle-green p5" />
        <div className="energy-particle particle-green p6" />
        <div className="energy-particle particle-white p7" />
        {/* Swirl rings -- blue at Architect (left), amber at SysAdmin (right) */}
        <div className="swirl swirl-blue-1" />
        <div className="swirl swirl-blue-2" />
        <div className="swirl swirl-amber-1" />
        <div className="swirl swirl-amber-2" />
      </div>

      {/* Title hover zone with pulsing glow line hint */}
      <div className="title-zone"
        onMouseEnter={() => setShowLogin(true)}
        onMouseLeave={() => setShowLogin(false)}
        style={{
          position: 'absolute',
          top: 0,
          left: '25%',
          width: '50%',
          height: '16%',
          cursor: 'default',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'flex-end',
          paddingBottom: '0%',
        }}
      >
        {/* Pulsing glow bar at bottom of title zone -- hints "hover here" */}
        <div className="title-glow-hint" />
        <button
          onClick={login}
          disabled={isLoading}
          className={`login-btn ${showLogin ? 'login-btn-visible' : ''}`}
        >
          {isLoading ? 'Loading...' : 'Login'}
        </button>
      </div>

      {/* Disclaimer -- bottom-right */}
      <div style={{
        position: 'absolute',
        bottom: 28,
        right: 36,
      }}>
        <p style={{
          maxWidth: 400,
          fontSize: 13,
          lineHeight: 1.6,
          color: 'rgba(203, 213, 225, 0.85)',
          textAlign: 'right',
          margin: 0,
          background: 'rgba(3, 7, 18, 0.6)',
          padding: '10px 14px',
          borderRadius: 6,
          backdropFilter: 'blur(4px)',
        }}>
          {disclaimer}
        </p>
      </div>

      <style>{`
        /* ============================================================
         * Traveling particles (agents -> brain)
         * ============================================================ */
        @keyframes flow-cyan {
          0%   { transform: translate(10vw, 50vh); opacity: 0; }
          10%  { opacity: 1; }
          90%  { opacity: 1; }
          100% { transform: translate(43vw, 37vh); opacity: 0; }
        }
        @keyframes flow-cyan-2 {
          0%   { transform: translate(18vw, 55vh); opacity: 0; }
          10%  { opacity: 1; }
          90%  { opacity: 1; }
          100% { transform: translate(40vw, 40vh); opacity: 0; }
        }
        @keyframes flow-orange {
          0%   { transform: translate(80vw, 46vh); opacity: 0; }
          10%  { opacity: 1; }
          90%  { opacity: 1; }
          100% { transform: translate(53vw, 37vh); opacity: 0; }
        }
        @keyframes flow-orange-2 {
          0%   { transform: translate(75vw, 50vh); opacity: 0; }
          10%  { opacity: 1; }
          90%  { opacity: 1; }
          100% { transform: translate(50vw, 40vh); opacity: 0; }
        }
        @keyframes flow-green {
          0%   { transform: translate(43vw, 80vh); opacity: 0; }
          10%  { opacity: 1; }
          90%  { opacity: 1; }
          100% { transform: translate(47vw, 42vh); opacity: 0; }
        }
        @keyframes flow-green-2 {
          0%   { transform: translate(48vw, 76vh); opacity: 0; }
          10%  { opacity: 1; }
          90%  { opacity: 1; }
          100% { transform: translate(44vw, 44vh); opacity: 0; }
        }
        @keyframes flow-white {
          0%   { transform: translate(46vw, 38vh); opacity: 0; }
          20%  { opacity: 0.8; }
          80%  { opacity: 0.8; }
          100% { transform: translate(46vw, 38vh) scale(2.5); opacity: 0; }
        }
        .energy-particle {
          position: absolute;
          border-radius: 50%;
          animation-iteration-count: infinite;
          animation-timing-function: ease-in-out;
        }
        .particle-cyan  { background: #22d3ee; box-shadow: 0 0 14px 4px rgba(34,211,238,0.5); }
        .particle-orange { background: #fb923c; box-shadow: 0 0 14px 4px rgba(251,146,60,0.5); }
        .particle-green  { background: #4ade80; box-shadow: 0 0 14px 4px rgba(74,222,128,0.5); }
        .particle-white  { background: #f8fafc; box-shadow: 0 0 20px 6px rgba(248,250,252,0.3); }

        .p1 { width: 10px; height: 10px; animation: flow-cyan 3.5s infinite; }
        .p2 { width: 7px;  height: 7px;  animation: flow-cyan-2 4.2s infinite; animation-delay: 1.8s; }
        .p3 { width: 10px; height: 10px; animation: flow-orange 4s infinite; animation-delay: 0.6s; }
        .p4 { width: 7px;  height: 7px;  animation: flow-orange-2 3.6s infinite; animation-delay: 2.2s; }
        .p5 { width: 10px; height: 10px; animation: flow-green 3.8s infinite; animation-delay: 1.2s; }
        .p6 { width: 7px;  height: 7px;  animation: flow-green-2 4.4s infinite; animation-delay: 3s; }
        .p7 { width: 5px;  height: 5px;  animation: flow-white 3s infinite; animation-delay: 2s; }

        /* ============================================================
         * Swirl rings at Brain center -- "processing" effect
         * Two rings: blue (outer) and amber (inner), counter-rotating
         * ============================================================ */
        @keyframes swirl-spin {
          0%   { transform: translate(-50%, -50%) rotate(0deg); opacity: 0.9; }
          50%  { opacity: 0.5; }
          100% { transform: translate(-50%, -50%) rotate(360deg); opacity: 0.9; }
        }
        @keyframes swirl-spin-reverse {
          0%   { transform: translate(-50%, -50%) rotate(0deg); opacity: 0.9; }
          50%  { opacity: 0.45; }
          100% { transform: translate(-50%, -50%) rotate(-360deg); opacity: 0.9; }
        }
        .swirl {
          position: absolute;
          border-radius: 50%;
          border-style: solid;
          border-color: transparent;
        }
        /* Blue swirls -- Brain outer blue sphere */
        .swirl-blue-1, .swirl-blue-2 {
          top: 42%;    /* ← blue vertical */
          left: 45%;   /* ← blue horizontal */
        }
        /* Amber swirls -- Brain inner amber core */
        .swirl-amber-1, .swirl-amber-2 {
          top: 42%;    /* ← amber vertical */
          left: 55%;   /* ← amber horizontal */
        }
        .swirl-blue-1 {
          width: 200px;
          height: 200px;
          border-width: 3px;
          border-top-color: rgba(56, 189, 248, 0.9);
          border-right-color: rgba(56, 189, 248, 0.4);
          border-bottom-color: rgba(56, 189, 248, 0.1);
          box-shadow: 0 0 40px 10px rgba(56, 189, 248, 0.2), inset 0 0 30px 5px rgba(56, 189, 248, 0.08);
          animation: swirl-spin 5s linear infinite;
        }
        .swirl-blue-2 {
          width: 160px;
          height: 160px;
          border-width: 2px;
          border-top-color: rgba(56, 189, 248, 0.7);
          border-left-color: rgba(56, 189, 248, 0.3);
          box-shadow: 0 0 30px 6px rgba(56, 189, 248, 0.15), inset 0 0 20px 3px rgba(56, 189, 248, 0.06);
          animation: swirl-spin-reverse 3.5s linear infinite;
        }
        .swirl-amber-1 {
          width: 120px;
          height: 120px;
          border-width: 3px;
          border-top-color: rgba(251, 146, 60, 0.9);
          border-left-color: rgba(251, 146, 60, 0.4);
          border-bottom-color: rgba(251, 146, 60, 0.1);
          box-shadow: 0 0 40px 10px rgba(251, 146, 60, 0.2), inset 0 0 30px 5px rgba(251, 146, 60, 0.08);
          animation: swirl-spin-reverse 4.5s linear infinite;
        }
        .swirl-amber-2 {
          width: 80px;
          height: 80px;
          border-width: 2px;
          border-top-color: rgba(251, 146, 60, 0.7);
          border-right-color: rgba(251, 146, 60, 0.3);
          box-shadow: 0 0 30px 6px rgba(251, 146, 60, 0.15), inset 0 0 20px 3px rgba(251, 146, 60, 0.06);
          animation: swirl-spin 3s linear infinite;
        }

        /* ============================================================
         * Title zone glow hint -- pulsing line that invites hover
         * ============================================================ */
        @keyframes glow-pulse {
          0%   { opacity: 0.15; box-shadow: 0 0 6px 1px rgba(56,189,248,0.2); }
          50%  { opacity: 0.5;  box-shadow: 0 0 14px 3px rgba(56,189,248,0.4); }
          100% { opacity: 0.15; box-shadow: 0 0 6px 1px rgba(56,189,248,0.2); }
        }
        .title-glow-hint {
          width: 60%;
          height: 2px;
          background: rgba(56, 189, 248, 0.4);
          border-radius: 1px;
          animation: glow-pulse 2.5s ease-in-out infinite;
          margin-bottom: -1px;
          z-index: 1;
        }
        .title-zone:hover .title-glow-hint {
          opacity: 0 !important;
          animation: none;
        }

        /* ============================================================
         * Login button
         * ============================================================ */
        @keyframes btn-glow {
          0%   { box-shadow: 0 0 8px 0 rgba(56,189,248,0.2), inset 0 0 0 0 rgba(56,189,248,0); }
          50%  { box-shadow: 0 4px 16px 2px rgba(56,189,248,0.35), inset 0 0 10px 0 rgba(56,189,248,0.06); }
          100% { box-shadow: 0 0 8px 0 rgba(56,189,248,0.2), inset 0 0 0 0 rgba(56,189,248,0); }
        }
        @keyframes btn-reveal {
          from { opacity: 0; transform: translateY(-10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .login-btn {
          padding: 16px 0;
          width: 60%;
          font-size: 16px;
          font-weight: 600;
          letter-spacing: 2px;
          text-transform: uppercase;
          color: rgba(186, 230, 253, 0.9);
          background: linear-gradient(180deg, rgba(56, 189, 248, 0.15) 0%, rgba(30, 41, 59, 0.7) 100%);
          border: 1px solid rgba(56, 189, 248, 0.3);
          border-top: 2px solid rgba(56, 189, 248, 0.6);
          border-radius: 0 0 8px 8px;
          cursor: pointer;
          backdrop-filter: blur(8px);
          transition: all 0.3s ease;
          opacity: 0;
          pointer-events: none;
          position: relative;
        }
        .login-btn::before {
          content: '';
          position: absolute;
          top: -1px;
          left: 15%;
          width: 70%;
          height: 2px;
          background: rgba(56, 189, 248, 0.8);
          box-shadow: 0 0 12px 2px rgba(56, 189, 248, 0.5);
        }
        .login-btn-visible {
          opacity: 1;
          pointer-events: auto;
          margin-top: -2px;
          animation: btn-reveal 0.35s ease-out, btn-glow 3s ease-in-out 0.35s infinite;
        }
        .login-btn:hover {
          background: linear-gradient(180deg, rgba(56, 189, 248, 0.3) 0%, rgba(30, 58, 138, 0.8) 100%);
          border-color: rgba(56, 189, 248, 0.6);
          color: #e0f2fe;
          box-shadow: 0 4px 24px 4px rgba(56, 189, 248, 0.4), inset 0 0 16px rgba(56, 189, 248, 0.1) !important;
        }
        .login-btn:hover::before {
          background: rgba(56, 189, 248, 1);
          box-shadow: 0 0 18px 4px rgba(56, 189, 248, 0.7);
        }
        .login-btn:active {
          transform: translateY(1px);
        }
        .login-btn:disabled {
          cursor: wait;
          animation: none;
          opacity: 0.6;
        }
      `}</style>
    </div>
  );
};

export default LoginPage;
