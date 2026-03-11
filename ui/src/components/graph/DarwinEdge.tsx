// BlackBoard/ui/src/components/graph/DarwinEdge.tsx
import { BaseEdge, getBezierPath, type EdgeProps } from '@xyflow/react';
import './ArchitectureGraph.css';

export default function DarwinEdge(props: EdgeProps) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data } = props;

  const [edgePath] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition });

  const isAsync = data?.async === true;
  const isTicket = data?.ticket === true;

  return (
    <BaseEdge
      path={edgePath}
      style={{
        stroke: isTicket ? '#f59e0b' : isAsync ? '#6366f1' : '#4b5563',
        strokeWidth: isAsync || isTicket ? 2 : 1.5,
        strokeDasharray: isAsync || isTicket ? '6 3' : undefined,
        animation: isAsync ? 'edge-flow 1s linear infinite' : undefined,
      }}
    />
  );
}
