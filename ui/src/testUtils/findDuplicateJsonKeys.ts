// BlackBoard/ui/src/testUtils/findDuplicateJsonKeys.ts
// @ai-rules:
// 1. [Constraint]: JSON.parse silently keeps the LAST duplicate key, so duplicates can only be found by scanning raw text.
// 2. [Pattern]: Returns "path.to.key" for every key that repeats within the same object; empty array means clean.
type Frame = { kind: 'object'; keys: Set<string>; expectKey: boolean; name: string } | { kind: 'array'; name: string };

export function findDuplicateJsonKeys(text: string): string[] {
  const duplicates: string[] = [];
  const stack: Frame[] = [];
  let lastKey = '';
  const pathOf = (key?: string) =>
    [...stack.map(f => f.name).filter(Boolean), ...(key !== undefined ? [key] : [])].join('.');

  let i = 0;
  while (i < text.length) {
    const c = text[i];
    if (c === '"') {
      let j = i + 1;
      while (text[j] !== '"') {
        if (text[j] === '\\') j++;
        j++;
      }
      const str = JSON.parse(text.slice(i, j + 1)) as string;
      i = j + 1;
      const top = stack[stack.length - 1];
      if (top?.kind === 'object' && top.expectKey) {
        if (top.keys.has(str)) duplicates.push(pathOf(str));
        top.keys.add(str);
        top.expectKey = false;
        lastKey = str;
      }
      continue;
    }
    if (c === '{') {
      stack.push({ kind: 'object', keys: new Set(), expectKey: true, name: lastKey });
      lastKey = '';
    } else if (c === '[') {
      stack.push({ kind: 'array', name: lastKey });
      lastKey = '';
    } else if (c === '}' || c === ']') {
      stack.pop();
    } else if (c === ',') {
      const top = stack[stack.length - 1];
      if (top?.kind === 'object') top.expectKey = true;
    }
    i++;
  }
  return duplicates;
}
