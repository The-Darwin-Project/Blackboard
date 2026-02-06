// BlackBoard/ui/src/components/GraphContextMenu.tsx
/**
 * Context menu for right-click actions on graph nodes.
 * 
 * Actions:
 * - Ask Architect to Scale
 * - Ask Architect to Debug
 */
import { useCallback } from 'react';
import { Scale, Bug, X } from 'lucide-react';
import { useChat } from '../hooks';

interface GraphContextMenuProps {
  serviceName: string;
  position: { x: number; y: number };
  onClose: () => void;
}

function GraphContextMenu({ serviceName, position, onClose }: GraphContextMenuProps) {
  const chatMutation = useChat();
  const { mutate: sendMessage, isPending } = chatMutation;

  const handleScale = useCallback(() => {
    sendMessage({ message: `Please analyze ${serviceName} and create a scaling plan if needed.`, service: serviceName });
    onClose();
  }, [serviceName, sendMessage, onClose]);

  const handleDebug = useCallback(() => {
    sendMessage({ message: `Please investigate any issues with ${serviceName} and suggest fixes.`, service: serviceName });
    onClose();
  }, [serviceName, sendMessage, onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
      />
      
      {/* Menu */}
      <div
        className="fixed z-50 bg-bg-secondary border border-border rounded-lg shadow-xl py-1 min-w-48"
        style={{
          left: position.x,
          top: position.y,
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-border">
          <span className="text-sm font-medium text-text-primary">{serviceName}</span>
          <button
            onClick={onClose}
            className="p-1 hover:bg-bg-hover rounded"
          >
            <X className="w-3 h-3 text-text-muted" />
          </button>
        </div>

        {/* Actions */}
        <div className="py-1">
          <button
            onClick={handleScale}
            disabled={isPending}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors disabled:opacity-50"
          >
            <Scale className="w-4 h-4" />
            <span>Ask Architect to Scale</span>
          </button>
          
          <button
            onClick={handleDebug}
            disabled={isPending}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors disabled:opacity-50"
          >
            <Bug className="w-4 h-4" />
            <span>Ask Architect to Debug</span>
          </button>
        </div>

        {/* Status */}
        {isPending && (
          <div className="px-3 py-2 border-t border-border">
            <p className="text-xs text-text-muted">Sending request...</p>
          </div>
        )}
      </div>
    </>
  );
}

export default GraphContextMenu;
