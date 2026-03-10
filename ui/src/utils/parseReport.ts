// BlackBoard/ui/src/utils/parseReport.ts
// @ai-rules:
// 1. [Pattern]: Uses KNOWN section headers to split -- agent results contain ## sub-headings that must not be split.
// 2. [Constraint]: Pure functions only -- no React, no side effects. Consumed by ReportContent.
// 3. [Gotcha]: Turn results can contain ## sub-headings (agent output). Only split on KNOWN_SECTIONS, not arbitrary ##.

export interface ParsedSection {
  title: string;
  content: string;
}

export interface ParsedTurn {
  number: number;
  actor: string;
  action: string;
  time: string;
  delta: string;
  body: string;
}

export interface ParsedReport {
  header: string;
  sections: ParsedSection[];
  turns: ParsedTurn[];
  journal: string[];
}

const KNOWN_SECTIONS = [
  'GitLab Context',
  'Architecture Diagram',
  'Service Metadata',
  'Conversation',
  'Service Ops Journal',
];

const SECTION_RE = new RegExp(
  `^## (${KNOWN_SECTIONS.map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})\\s*$`,
  'm',
);

const TURN_RE = /^### Turn (\d+)\s*-\s*(\w+)\s*\(([^)]+)\)\s*\[([^\]]+)\]\s*\(([^)]+)\)/;

export function parseReportMarkdown(markdown: string): ParsedReport {
  const found: { title: string; start: number; contentStart: number }[] = [];
  let match: RegExpExecArray | null;
  const globalRe = new RegExp(SECTION_RE.source, 'gm');

  while ((match = globalRe.exec(markdown)) !== null) {
    found.push({
      title: match[1],
      start: match.index,
      contentStart: match.index + match[0].length,
    });
  }

  const header = found.length > 0
    ? markdown.slice(0, found[0].start).trim()
    : markdown.trim();

  const sections: ParsedSection[] = [];
  let conversationRaw = '';
  let journalRaw = '';

  for (let i = 0; i < found.length; i++) {
    const end = i + 1 < found.length ? found[i + 1].start : markdown.length;
    const content = markdown.slice(found[i].contentStart, end).trim();
    const title = found[i].title;

    if (title === 'Conversation') {
      conversationRaw = content;
    } else if (title === 'Service Ops Journal') {
      journalRaw = content;
    } else {
      sections.push({ title, content });
    }
  }

  const turns = parseTurns(conversationRaw);
  const journal = parseJournal(journalRaw);

  return { header, sections, turns, journal };
}

function parseTurns(raw: string): ParsedTurn[] {
  if (!raw) return [];
  const turnBlocks = raw.split(/\n(?=### Turn \d)/);
  const turns: ParsedTurn[] = [];

  for (const block of turnBlocks) {
    const match = block.match(TURN_RE);
    if (!match) continue;
    const body = block.slice(match[0].length).trim();
    turns.push({
      number: parseInt(match[1], 10),
      actor: match[2],
      action: match[3],
      time: match[4],
      delta: match[5],
      body,
    });
  }
  return turns;
}

function parseJournal(raw: string): string[] {
  if (!raw) return [];
  return raw
    .split('\n')
    .map((line) => line.replace(/^-\s*/, '').trim())
    .filter(Boolean);
}
