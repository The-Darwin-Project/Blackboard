// BlackBoard/ui/src/components/Dashboard.tsx
// @ai-rules:
// 1. [Pattern]: Thin wrapper that renders StreamGrid. Exists only to preserve the "/" route import in App.tsx.
// 2. [Constraint]: All logic lives in StreamGrid and OpsStateContext. This file is a pass-through.
import StreamGrid from './ops/StreamGrid';

export default function Dashboard() {
  return <StreamGrid />;
}
