// BlackBoard/ui/src/utils/stripAnsi.ts
// @ai-rules:
// 1. [Constraint]: Pure function, zero deps. Strips ANSI escape sequences from terminal output.
// 2. [Pattern]: Used by CiContextCard for console_tail rendering.
// 3. [Pattern]: stripJenkinsNoise removes Jenkins-specific noise (ha://// blobs, [Pipeline] boundaries).
// 4. [Gotcha]: Both regexes are bounded (line-anchored boundary marker, delimiter-bounded blob
//    match) to avoid over-strip and mid-line corruption. Keep in sync with jenkins.py's Python
//    mirror -- see inline comments above each pattern for the exact contract.

export function stripAnsi(text: string): string {
  return text.replace(
    /[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g,
    '',
  );
}

// Blob body is base64 ([A-Za-z0-9+/]) with optional `=`/`==` padding at the
// very end only. A right-delimiter lookahead (whitespace, ESC, another
// `ha:////`, or end-of-string) bounds the match to its own blob so it can
// never consume into adjacent real text or swallow a second, immediately
// adjacent blob with no separator. Keep in sync with jenkins.py's
// _PIPELINE_ANNOTATION_RE.
const PIPELINE_ANNOTATION_RE = /(?:\x1b\[[0-9;]*m)?ha:\/\/\/\/[A-Za-z0-9+\/]+={0,2}(?:\x1b\[[0-9;]*m)?(?=[\s\x1b]|ha:\/\/\/\/|$)/g;
// Real Jenkins `[Pipeline]` step-boundary markers are always full-line;
// anchored to line-start (optionally after a Timestamper prefix like
// "[2026-08-31T11:23:24.854Z] ") so a marker substring appearing mid-line in
// real log text is never treated as noise. Keep in sync with jenkins.py's
// _PIPELINE_BOUNDARY_RE.
const PIPELINE_BOUNDARY_RE = /^(?:\[[0-9T:.-]+Z\]\s*)?\[Pipeline\]\s*(?:\/\/\s*\w+|End of Pipeline|\{|\}|stage)[^\r\n]*(?:\r?\n|$)/gm;
const BLANK_RUN_RE = /(?:\r?\n){3,}/g;

export function stripJenkinsNoise(text: string): string {
  return text
    .replace(PIPELINE_ANNOTATION_RE, '')
    .replace(PIPELINE_BOUNDARY_RE, '')
    .replace(BLANK_RUN_RE, '\n\n')
    .trim();
}
