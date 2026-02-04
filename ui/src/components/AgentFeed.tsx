// BlackBoard/ui/src/components/AgentFeed.tsx
/**
 * Agent activity feed showing events and pending plans.
 * Uses /events/ endpoint for activity stream.
 */
import { User, Bot, Wrench, Loader2, Activity } from 'lucide-react';
import { useEvents, usePlans } from '../hooks';
import { getAgentFromEventType, type Agent, type ArchitectureEvent, type Plan } from '../api/types';
import PlanCard from './PlanCard';
import ChatInput from './ChatInput';

// Agent styling
const AGENT_STYLES: Record<Agent, { icon: typeof User; color: string; name: string }> = {
  aligner: { icon: Bot, color: 'text-agent-aligner bg-agent-aligner/20', name: 'Aligner' },
  architect: { icon: User, color: 'text-agent-architect bg-agent-architect/20', name: 'Architect' },
  sysadmin: { icon: Wrench, color: 'text-agent-sysadmin bg-agent-sysadmin/20', name: 'SysAdmin' },
};

// Event type display names
const EVENT_LABELS: Record<string, string> = {
  telemetry_received: 'Telemetry processed',
  service_discovered: 'New service discovered',
  plan_created: 'Plan created',
  plan_approved: 'Plan approved',
  plan_rejected: 'Plan rejected',
  plan_executed: 'Plan executed',
  plan_failed: 'Plan execution failed',
};

function AgentFeed() {
  const { data: events, isLoading: eventsLoading } = useEvents(50);
  const { data: plans, isLoading: plansLoading } = usePlans();

  // Get pending plans
  const pendingPlans = plans?.filter((p: Plan) => p.status === 'pending') ?? [];

  // Filter significant events (skip telemetry noise)
  const significantEvents = events?.filter(
    (e: ArchitectureEvent) => e.type !== 'telemetry_received'
  ) ?? [];

  const isLoading = eventsLoading || plansLoading;

  return (
    <div className="flex flex-col h-full">
      {/* Scrollable Feed */}
      <div className="flex-1 overflow-auto p-3 space-y-3">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 text-accent animate-spin" />
          </div>
        ) : (
          <>
            {/* Pending Plans Section */}
            {pendingPlans.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-status-pending flex items-center gap-1">
                  <Activity className="w-3 h-3" />
                  Pending Approval ({pendingPlans.length})
                </h3>
                {pendingPlans.map((plan: Plan) => (
                  <PlanCard key={plan.id} plan={plan} />
                ))}
              </div>
            )}

            {/* Recent Activity Section */}
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-text-muted">Recent Activity</h3>
              {significantEvents.length === 0 ? (
                <div className="text-center py-4 text-text-muted">
                  <p className="text-sm">No recent activity</p>
                  <p className="text-xs">Events will appear as agents take action</p>
                </div>
              ) : (
                significantEvents.slice(0, 20).map((event: ArchitectureEvent, index: number) => (
                  <EventItem key={`${event.timestamp}-${index}`} event={event} />
                ))
              )}
            </div>
          </>
        )}
      </div>

      {/* Chat Input */}
      <ChatInput />
    </div>
  );
}

interface EventItemProps {
  event: ArchitectureEvent;
}

function EventItem({ event }: EventItemProps) {
  const agent = getAgentFromEventType(event.type);
  const style = AGENT_STYLES[agent];
  const Icon = style.icon;
  const label = EVENT_LABELS[event.type] || event.type;

  // Extract relevant details
  const planId = event.details.plan_id as string | undefined;
  const serviceName = event.details.service as string | undefined;

  return (
    <div className="flex gap-2 p-2 rounded-lg bg-bg-primary">
      <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${style.color}`}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-text-primary">{style.name}</span>
          <span className="text-xs text-text-muted">
            {new Date(event.timestamp * 1000).toLocaleTimeString()}
          </span>
        </div>
        <p className="text-sm text-text-secondary truncate">{label}</p>
        {(planId || serviceName) && (
          <p className="text-xs text-text-muted truncate">
            {planId && `Plan: ${planId}`}
            {planId && serviceName && ' • '}
            {serviceName && `Service: ${serviceName}`}
          </p>
        )}
      </div>
    </div>
  );
}

export default AgentFeed;
