// BlackBoard/ui/src/components/graph/NamespaceGroupNode.tsx
// @ai-rules:
// 1. [Pattern]: React Flow `type: 'group'` parent node -- purely visual container. Service
//    nodes attach via `parentId` + `extent: 'parent'` (see ArchitectureGraph.tsx buildGraph()).
// 2. [Constraint]: Sized entirely via the node's top-level `style.width/height` (computed by
//    the active layout function) -- this component only renders the label chip + border.
import { memo } from 'react';
import type { NodeProps } from '@xyflow/react';
import './ArchitectureGraph.css';

interface NamespaceGroupNodeData {
  label: string;
}

function NamespaceGroupNodeComponent({ data }: NodeProps & { data: NamespaceGroupNodeData }) {
  return (
    <div className="namespace-group-node">
      <div className="namespace-group-label">{data.label}</div>
    </div>
  );
}

export default memo(NamespaceGroupNodeComponent);
