// BlackBoard/ui/src/hooks/usePlanState.ts
// @ai-rules:
// 1. [Constraint]: Memoized on the conversation array identity only. Callers pass a stable reference (useMemo / query data);
//    the default is the module-level EMPTY_CONVERSATION so an omitted argument never defeats the memo.
import { useMemo } from 'react';
import type { ConversationTurn } from '../api/types';
import { derivePlanState } from '../utils/planState';

export const EMPTY_CONVERSATION: ConversationTurn[] = [];

export function usePlanState(conversation: ConversationTurn[] = EMPTY_CONVERSATION) {
  return useMemo(() => derivePlanState(conversation), [conversation]);
}
