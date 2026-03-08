// BlackBoard/ui/src/components/LoginPage.tsx
// @ai-rules:
// 1. [Pattern]: Background image from /projectDarwin.png (ui/public/). No overlay card.
// 2. [Pattern]: Disclaimer default in component. Override via config.auth.loginDisclaimer if non-empty.
// 3. [Pattern]: Login button bottom-left, disclaimer bottom-right covering star icon.
import { useAuth } from '../contexts/AuthContext';

const DEFAULT_DISCLAIMER =
  'This system uses AI to autonomously manage infrastructure. ' +
  'AI-generated actions should be reviewed before acting on them.';

const LoginPage = () => {
  const { login, authConfig, isLoading } = useAuth();
  const disclaimer = authConfig?.loginDisclaimer || DEFAULT_DISCLAIMER;

  return (
    <div style={{
      position: 'fixed', inset: 0,
      backgroundImage: 'url(/projectDarwin.png)',
      backgroundSize: 'cover',
      backgroundPosition: 'center',
      backgroundRepeat: 'no-repeat',
      backgroundColor: '#030712',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'flex-end',
    }}>
      {/* Animated energy particles */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden' }}>
        <div className="energy-particle particle-cyan p1" />
        <div className="energy-particle particle-cyan p2" />
        <div className="energy-particle particle-orange p3" />
        <div className="energy-particle particle-orange p4" />
        <div className="energy-particle particle-green p5" />
        <div className="energy-particle particle-green p6" />
        <div className="energy-particle particle-white p7" />
      </div>

      {/* Bottom bar: login left, disclaimer right */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-end',
        padding: '28px 36px',
        gap: 32,
      }}>
        <button
          onClick={login}
          disabled={isLoading}
          className="login-btn"
        >
          {isLoading ? 'Loading...' : 'Login'}
        </button>

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

        @keyframes btn-glow {
          0%   { box-shadow: 0 0 8px 0 rgba(99,102,241,0.3), inset 0 0 0 0 rgba(99,102,241,0); }
          50%  { box-shadow: 0 0 20px 4px rgba(99,102,241,0.5), inset 0 0 12px 0 rgba(99,102,241,0.1); }
          100% { box-shadow: 0 0 8px 0 rgba(99,102,241,0.3), inset 0 0 0 0 rgba(99,102,241,0); }
        }
        .login-btn {
          padding: 14px 40px;
          font-size: 16px;
          font-weight: 700;
          letter-spacing: 0.5px;
          color: #e2e8f0;
          background: rgba(30, 41, 59, 0.8);
          border: 1px solid rgba(99, 102, 241, 0.4);
          border-radius: 10px;
          cursor: pointer;
          backdrop-filter: blur(8px);
          transition: all 0.3s ease;
          animation: btn-glow 2.5s ease-in-out infinite;
        }
        .login-btn:hover {
          background: rgba(67, 56, 202, 0.6);
          border-color: rgba(129, 140, 248, 0.7);
          transform: translateY(-1px);
          box-shadow: 0 0 28px 6px rgba(99,102,241,0.6) !important;
        }
        .login-btn:active {
          transform: translateY(0);
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
