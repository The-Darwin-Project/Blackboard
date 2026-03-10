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

export interface JournalEntry {
  timestamp: string;
  title: string;
  summary: string;
  raw: string;
}

export interface ParsedReport {
  header: string;
  sections: ParsedSection[];
  turns: ParsedTurn[];
  journal: JournalEntry[];
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

const CLOSE_RE = /\s*--\s*closed in (\d+) turns?\.\s*/;
const PLAN_TITLE_RE = /plan:\s*"([^"]+)"/;
const TIMESTAMP_RE = /^\[([^\]]+)\]\s*/;

function parseJournal(raw: string): JournalEntry[] {
  if (!raw) return [];

  const lines = raw.split('\n').map((l) => l.replace(/^-\s*/, '').trim()).filter(Boolean);
  return lines.map((line) => {
    const tsMatch = line.match(TIMESTAMP_RE);
    const timestamp = tsMatch ? tsMatch[1] : '';
    const body = tsMatch ? line.slice(tsMatch[0].length) : line;

    const closeIdx = body.search(CLOSE_RE);
    const planPart = closeIdx >= 0 ? body.slice(0, closeIdx) : body;
    const closePart = closeIdx >= 0 ? body.slice(closeIdx).replace(CLOSE_RE, '').trim() : '';

    const titleMatch = planPart.match(PLAN_TITLE_RE);
    const title = titleMatch ? titleMatch[1] : planPart.slice(0, 100);

    return { timestamp, title, summary: closePart, raw: line };
  });
}
