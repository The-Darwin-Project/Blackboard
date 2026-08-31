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
// confirms one of the traditionally-safe delimiters immediately follows
// it (whitespace, ANSI escape, another `ha:////`, or end-of-string). If
// that lookahead fails, this alternative does not match at this position,
// the whole match fails, and the abutting secret text (including the
// "token=" delimiter) survives untouched for downstream redaction -- the
// same "leave ambiguous content alone" philosophy already applied
// throughout this fix. This closes the gap without reintroducing the F3
// (adjacent-blobs) or F4 (colon-delimited abutment, already safe since
// `:` is outside the base64 alphabet) cases: each blob is still matched
// independently once it has its own valid terminator, so no separate "or
// another ha:////" alternative is needed outside the single-`=`
// lookahead itself.
//
// Accepted trade-off (narrower than the prior round's): a genuinely valid
// blob needing exactly one padding character, NOT followed by
// whitespace/ANSI/EOS/another blob (i.e. directly abutting more real log
// content with no separator), will no longer be recognized and will show
// through as literal noise instead of being stripped -- narrower still
// than the previous trade-off (which covered all unpadded/non-ANSI-wrapped
// blobs), but still cosmetic-only. Keep in sync with jenkins.py's
// _PIPELINE_ANNOTATION_RE.
const PIPELINE_ANNOTATION_RE = new RegExp(
  `(?:\\x1b\\[[0-9;]*m)?ha:\\/\\/\\/\\/[A-Za-z0-9+\\/]{1,${MAX_BLOB_LEN}}(?:==(?:\\x1b\\[[0-9;]*m)?|=(?=[\\s\\x1b]|ha:\\/\\/\\/\\/|$)(?:\\x1b\\[[0-9;]*m)?|\\x1b\\[[0-9;]*m)`,
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
