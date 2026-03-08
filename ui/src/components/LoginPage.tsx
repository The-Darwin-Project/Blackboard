// BlackBoard/ui/src/components/LoginPage.tsx
// @ai-rules:
// 1. [Pattern]: Background image from /projectDarwin.png (ui/public/). No overlay card.
// 2. [Pattern]: Disclaimer default in component. Override via config.auth.loginDisclaimer if non-empty.
// 3. [Pattern]: Login button bottom-left, disclaimer bottom-right above star icon.
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
        <div className="energy-particle particle-cyan" />
        <div className="energy-particle particle-orange" />
        <div className="energy-particle particle-green" />
      </div>

      {/* Bottom bar: login left, disclaimer right */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-end',
        padding: '24px 32px',
        gap: 24,
      }}>
        <button
          onClick={login}
          disabled={isLoading}
          style={{
            padding: '10px 28px',
            fontSize: 14,
            fontWeight: 600,
            color: '#e2e8f0',
            background: 'rgba(30, 41, 59, 0.75)',
            border: '1px solid rgba(148, 163, 184, 0.25)',
            borderRadius: 8,
            cursor: isLoading ? 'wait' : 'pointer',
            backdropFilter: 'blur(8px)',
            transition: 'background 0.2s, border-color 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(51, 65, 85, 0.85)';
            e.currentTarget.style.borderColor = 'rgba(148, 163, 184, 0.5)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(30, 41, 59, 0.75)';
            e.currentTarget.style.borderColor = 'rgba(148, 163, 184, 0.25)';
          }}
        >
          {isLoading ? 'Loading...' : 'Login'}
        </button>

        <p style={{
          maxWidth: 340,
          fontSize: 11,
          lineHeight: 1.5,
          color: 'rgba(148, 163, 184, 0.7)',
          textAlign: 'right',
          margin: 0,
        }}>
          {disclaimer}
        </p>
      </div>

      <style>{`
        @keyframes flow-cyan {
          0%   { transform: translate(12vw, 52vh); opacity: 0; }
          15%  { opacity: 1; }
          85%  { opacity: 1; }
          100% { transform: translate(42vw, 38vh); opacity: 0; }
        }
        @keyframes flow-orange {
          0%   { transform: translate(78vw, 48vh); opacity: 0; }
          15%  { opacity: 1; }
          85%  { opacity: 1; }
          100% { transform: translate(52vw, 38vh); opacity: 0; }
        }
        @keyframes flow-green {
          0%   { transform: translate(44vw, 78vh); opacity: 0; }
          15%  { opacity: 1; }
          85%  { opacity: 1; }
          100% { transform: translate(46vw, 42vh); opacity: 0; }
        }
        .energy-particle {
          position: absolute;
          width: 6px;
          height: 6px;
          border-radius: 50%;
          animation-iteration-count: infinite;
          animation-timing-function: ease-in-out;
        }
        .particle-cyan {
          background: #22d3ee;
          box-shadow: 0 0 8px 2px rgba(34, 211, 238, 0.6);
          animation: flow-cyan 4s infinite;
          animation-delay: 0s;
        }
        .particle-orange {
          background: #fb923c;
          box-shadow: 0 0 8px 2px rgba(251, 146, 60, 0.6);
          animation: flow-orange 4.5s infinite;
          animation-delay: 1.2s;
        }
        .particle-green {
          background: #4ade80;
          box-shadow: 0 0 8px 2px rgba(74, 222, 128, 0.6);
          animation: flow-green 3.8s infinite;
          animation-delay: 2.4s;
        }
      `}</style>
    </div>
  );
};

export default LoginPage;
