// BlackBoard/ui/src/components/PlanCard.tsx
/**
 * Interactive plan card with approve/reject functionality.
 * Shows status badge, action details, and reason.
 */
import { useState } from 'react';
import { Check, X, Loader2, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { useApprovePlan, useRejectPlan } from '../hooks';
import type { Plan, PlanStatus } from '../api/types';

interface PlanCardProps {
  plan: Plan;
}

const STATUS_STYLES: Record<PlanStatus, { bg: string; text: string; label: string }> = {
  pending: { bg: 'bg-status-pending/20', text: 'text-status-pending', label: 'Pending' },
  approved: { bg: 'bg-status-approved/20', text: 'text-status-approved', label: 'Approved' },
  rejected: { bg: 'bg-status-rejected/20', text: 'text-status-rejected', label: 'Rejected' },
  executing: { bg: 'bg-blue-500/20', text: 'text-blue-400', label: 'Executing' },
  completed: { bg: 'bg-green-500/20', text: 'text-green-400', label: 'Completed' },
  failed: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'Failed' },
};

function PlanCard({ plan }: PlanCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectInput, setShowRejectInput] = useState(false);

  const approveMutation = useApprovePlan();
  const rejectMutation = useRejectPlan();

  const statusStyle = STATUS_STYLES[plan.status];
  const isPending = plan.status === 'pending';
  const isLoading = approveMutation.isPending || rejectMutation.isPending;

  const handleApprove = () => {
    approveMutation.mutate(plan.id);
  };

  const handleReject = () => {
    if (showRejectInput) {
      rejectMutation.mutate({ id: plan.id, reason: rejectReason });
      setShowRejectInput(false);
      setRejectReason('');
    } else {
      setShowRejectInput(true);
    }
  };

  const handleCancelReject = () => {
    setShowRejectInput(false);
    setRejectReason('');
  };

  return (
    <div className="bg-bg-primary rounded-lg border border-border overflow-hidden">
      {/* Header */}
      <div
        className="px-3 py-2 flex items-center justify-between cursor-pointer hover:bg-bg-tertiary/50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusStyle.bg} ${statusStyle.text}`}>
            {statusStyle.label}
          </span>
          <span className="text-sm font-medium text-text-primary truncate">
            {plan.action.toUpperCase()}
          </span>
          <span className="text-sm text-text-secondary truncate">
            → {plan.service}
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-text-muted flex-shrink-0" />
        ) : (
          <ChevronDown className="w-4 h-4 text-text-muted flex-shrink-0" />
        )}
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-border">
          {/* Reason */}
          <div className="pt-2">
            <p className="text-xs text-text-muted mb-1">Reason:</p>
            <p className="text-sm text-text-secondary">{plan.reason}</p>
          </div>

          {/* Parameters */}
          {Object.keys(plan.params).length > 0 && (
            <div>
              <p className="text-xs text-text-muted mb-1">Parameters:</p>
              <pre className="text-xs bg-bg-tertiary rounded p-2 overflow-x-auto">
                {JSON.stringify(plan.params, null, 2)}
              </pre>
            </div>
          )}

          {/* Result (for completed/failed) */}
          {plan.result && (
            <div>
              <p className="text-xs text-text-muted mb-1">Result:</p>
              <p className={`text-sm ${plan.status === 'failed' ? 'text-status-critical' : 'text-text-secondary'}`}>
                {plan.result}
              </p>
            </div>
          )}

          {/* Actions */}
          {isPending && (
            <div className="pt-2 space-y-2">
              {showRejectInput ? (
                <div className="space-y-2">
                  <input
                    type="text"
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    placeholder="Rejection reason (optional)"
                    className="w-full px-2 py-1.5 bg-bg-tertiary border border-border rounded text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-border-focus"
                    autoFocus
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={handleReject}
                      disabled={isLoading}
                      className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-status-rejected/20 text-status-rejected rounded text-sm font-medium hover:bg-status-rejected/30 disabled:opacity-50 transition-colors"
                    >
                      {rejectMutation.isPending ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <X className="w-4 h-4" />
                          Confirm Reject
                        </>
                      )}
                    </button>
                    <button
                      onClick={handleCancelReject}
                      disabled={isLoading}
                      className="px-3 py-1.5 bg-bg-tertiary text-text-secondary rounded text-sm hover:bg-bg-tertiary/80 disabled:opacity-50 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex gap-2">
                  <button
                    onClick={handleApprove}
                    disabled={isLoading}
                    className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-status-approved/20 text-status-approved rounded text-sm font-medium hover:bg-status-approved/30 disabled:opacity-50 transition-colors"
                  >
                    {approveMutation.isPending ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <>
                        <Check className="w-4 h-4" />
                        Approve
                      </>
                    )}
                  </button>
                  <button
                    onClick={handleReject}
                    disabled={isLoading}
                    className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-status-rejected/20 text-status-rejected rounded text-sm font-medium hover:bg-status-rejected/30 disabled:opacity-50 transition-colors"
                  >
                    <X className="w-4 h-4" />
                    Reject
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Error display */}
          {(approveMutation.isError || rejectMutation.isError) && (
            <div className="flex items-center gap-2 text-status-critical text-xs">
              <AlertCircle className="w-4 h-4" />
              <span>Action failed. Please try again.</span>
            </div>
          )}

          {/* Timestamps */}
          <div className="pt-2 text-xs text-text-muted space-y-1">
            <p>Created: {new Date(plan.created_at * 1000).toLocaleString()}</p>
            {plan.approved_at && (
              <p>Approved: {new Date(plan.approved_at * 1000).toLocaleString()}</p>
            )}
            {plan.executed_at && (
              <p>Executed: {new Date(plan.executed_at * 1000).toLocaleString()}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default PlanCard;
