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

// Blob body is base64 ([A-Za-z0-9+/]), bounded to at most MAX_BLOB_LEN
// chars. A match is only accepted as a genuine ConsoleNote blob if it
// terminates via one of three STRUCTURAL signals baked into the match
// itself (not merely asserted via a zero-width lookahead, except where
// noted below): double `==` padding; single `=` padding that is ALSO
// immediately followed by one of the traditionally-safe terminators
// (whitespace, ANSI escape, another `ha:////` occurrence, or
// end-of-string); or a trailing ANSI escape with no padding at all. Each
// padding alternative may optionally consume a trailing ANSI escape too.
//
// Bare whitespace and bare end-of-string are deliberately NOT accepted as
// unconditional termination signals (they used to be, via a lookahead
// alternative, until a MEDIUM secret-redaction-bypass finding on this
// exact regex). The base64 alphabet [A-Za-z0-9+/] is a superset of
// ordinary English letters and digits, so it cannot be distinguished from
// adjacent real text using only "where's the next whitespace/EOS" -- an
// unpadded, non-ANSI-wrapped blob immediately abutted by a real secret
// composed entirely of letters/digits (e.g. "ha:////AAAABearer
// sometoken123", or the same thing sitting at the very end of the
// currently-fetched log tail) let the greedy body class silently consume
// through the real word before downstream redaction ever got a chance to
// see it, deleting the secret's own redaction trigger along with the
// blob. ANSI escapes and double `==` padding are both structurally
// impossible inside ordinary prose (a raw ESC byte in particular can
// never be part of English text; two literal `=` characters back-to-back
// never occur in a real single-delimiter `KEY=value` string), so either
// alone is accepted as a self-sufficient terminator with no further
// check.
//
// A SINGLE `=`, however, is exactly the common `KEY=value` secret
// delimiter (see jenkins_observer.py's `_SECRET_TEXT_PATTERN`, which
// redacts both "key: value" and "key=value" forms) and is therefore
// genuinely indistinguishable from real single-char base64 padding using
// only local regex context -- e.g. "ha:////AAAtoken=abc123xyz" is exactly
// as plausible a real base64 blob ending in one padding char as it is a
// blob abutting a "token=" secret delimiter. To resolve the ambiguity, a
// lone `=` is only accepted as a real terminator when a lookahead
// confirms an ANSI escape (`\x1b[`) immediately follows it. Neither
// `ha:////` nor end-of-string (`$`) are accepted in this lookahead -- a
// following `ha:////` occurrence was independently verified to let the
// greedy body class consume through a `password=`/`token=` delimiter when
// the next blob's `ha:////` header coincidentally satisfies the
// lookahead, and `$` has Python/JS parity issues (Python `$` matches
// before a trailing `\n`; JS `$` without `m` flag matches only true
// end-of-input). Removing both closes the CRITICAL (cross-blob
// `password=` consumption) and HIGH (P/JS `$` parity split) findings
// fail-closed. If the lookahead fails, the whole match fails and the
// abutting secret text (including the "token=" delimiter) survives
// untouched for downstream redaction -- the same "leave ambiguous
// content alone" philosophy already applied throughout.
//
// Whitespace was DELIBERATELY REMOVED from that lookahead set (it used to
// be a member, until a MORE SERIOUS follow-on secret-redaction-bypass
// finding on this exact branch). Whitespace after a real `=` is not a
// rare, deliberately-constructed pattern the way an ANSI escape or a
// chained `ha:////` occurrence is -- it is the single most common,
// completely benign way a real secret is ever written in log output or
// config dumps ("KEY= value", "KEY=\nvalue"). Treating "followed by
// whitespace" as proof of genuine base64 padding was backwards: whitespace
// commonly follows a real `=` delimiter too, so its presence proves
// nothing about which case this is, and the old rule silently deleted the
// "token="/"password="/etc. delimiter along with the blob, defeating
// downstream redaction exactly like the un-lookahead-guarded version this
// branch was meant to fix.
//
// Accepted trade-off (narrower than the prior round's): a genuinely
// valid single-pad blob (`...=`) with no ANSI wrapper, whether at
// end-of-string, before whitespace, or immediately followed by another
// `ha:////`, is left as cosmetic noise. Adjacent blobs that use `==`
// padding still strip cleanly (the `==` alternative is unconditional).
// Fail-closed: never eat `password=` / `token=` / `Bearer ` by treating
// a following `ha:////` or `$` as proof of padding.
// Keep in sync with jenkins.py's _PIPELINE_ANNOTATION_RE.
const PIPELINE_ANNOTATION_RE = new RegExp(
  `(?:\\x1b\\[[0-9;]*m)?ha:\\/\\/\\/\\/(?<body>[A-Za-z0-9+\\/]{1,${MAX_BLOB_LEN}})(?:==(?:\\x1b\\[[0-9;]*m)?|=(?=\\x1b\\[)(?:\\x1b\\[[0-9;]*m)?|\\x1b\\[[0-9;]*m)`,
  'g',
);
// Post-match reject: if the blob body ends with a redaction-trigger keyword
// (case-insensitive), the match is returned unchanged so downstream secret
// redaction can still see the keyword. Closes the `==`-terminated and
// bare-ANSI-terminated variants of the secret-eating bug without removing
// those terminators. Accepted trade-off: a genuine ConsoleNote whose base64
// body happens to end with one of these English words will not strip
// (cosmetic leftover). Fail-closed.
// Keep in sync with jenkins.py's _REDACTION_TRIGGER_KEYWORDS.
const REDACTION_TRIGGER_KEYWORDS = [
  'password', 'passwd', 'token', 'secret', 'bearer', 'credential', 'authorization',
];

function annotationReplacer(match: string, body: string): string {
  const lower = body.toLowerCase();
  if (REDACTION_TRIGGER_KEYWORDS.some(kw => lower.endsWith(kw))) {
    return match;
  }
  return '';
}
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
    .replace(PIPELINE_ANNOTATION_RE, annotationReplacer)
    .replace(PIPELINE_BOUNDARY_RE, '')
    .replace(BLANK_RUN_RE, '\n\n')
    .trim();
}
