// BlackBoard/ui/src/utils/stripAnsi.ts
// @ai-rules:
// 1. [Constraint]: Pure function, zero deps. Strips ANSI escape sequences from terminal output.
// 2. [Pattern]: Used by CiContextCard for console_tail rendering.
// 3. [Pattern]: stripJenkinsNoise removes Jenkins-specific noise (ha://// blobs, [Pipeline] boundaries).
// 4. [Gotcha]: Both regexes are bounded (line-anchored boundary marker, delimiter-bounded blob
//    match, and a hard MAX_BLOB_LEN cap) to avoid over-strip and mid-line corruption. Keep in
//    sync with jenkins.py's Python mirror -- see inline comments above each pattern for the
//    exact contract, and tests/test_jenkins_noise_strip_parity.py for the cross-language guard.

export function stripAnsi(text: string): string {
  return text.replace(
    /[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g,
    '',
  );
}

// Hard cap on how long a single `ha:////` match can be. Chosen so a blob at
// this max length, positioned as close as possible to the end of the input,
// is still guaranteed to have been visible in whatever pre-strip window the
// caller applied -- see jenkins.py's _MAX_BLOB_LEN comment for the full
// invariant (this file has no window of its own; it's the UI's
// defense-in-depth copy, always fed an already-windowed console_tail).
const MAX_BLOB_LEN = 8192;

// Blob body is base64 ([A-Za-z0-9+/]) with optional `=`/`==` padding at the
// very end only, bounded to at most MAX_BLOB_LEN chars. A right-delimiter
// lookahead (whitespace, ESC, another `ha:////`, or end-of-string) bounds
// the match to its own blob so it can never consume into adjacent real text
// or swallow a second, immediately adjacent blob with no separator. Keep in
// sync with jenkins.py's _PIPELINE_ANNOTATION_RE.
const PIPELINE_ANNOTATION_RE = new RegExp(
  `(?:\\x1b\\[[0-9;]*m)?ha:\\/\\/\\/\\/[A-Za-z0-9+\\/]{1,${MAX_BLOB_LEN}}={0,2}(?:\\x1b\\[[0-9;]*m)?(?=[\\s\\x1b]|ha:\\/\\/\\/\\/|$)`,
  'g',
);
// Real Jenkins `[Pipeline]` step-boundary markers are always full-line;
// anchored to line-start (optionally after a Timestamper prefix like
// "[2026-08-31T11:23:24.854Z] ") so a marker substring appearing mid-line in
// real log text is never treated as noise. The trailing `\b` after the
// `\w+`/`stage`/`Pipeline` alternatives (not after the bare `{`/`}`
// literals, which aren't word characters) stops a marker substring that is
// merely a PREFIX of a longer real word -- e.g. "stagecoach", "staged
// rollback", "End of PipelineExtra: ..." -- from being misidentified as a
// boundary. Keep in sync with jenkins.py's _PIPELINE_BOUNDARY_RE.
const PIPELINE_BOUNDARY_RE = /^(?:\[[0-9T:.-]+Z\]\s*)?\[Pipeline\]\s*(?:\/\/\s*\w+\b|End of Pipeline\b|\{|\}|stage\b)[^\r\n]*(?:\r?\n|$)/gm;
const BLANK_RUN_RE = /(?:\r?\n){3,}/g;

export function stripJenkinsNoise(text: string): string {
  return text
    .replace(PIPELINE_ANNOTATION_RE, '')
    .replace(PIPELINE_BOUNDARY_RE, '')
    .replace(BLANK_RUN_RE, '\n\n')
    .trim();
}
