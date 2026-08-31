// BlackBoard/ui/src/utils/stripAnsi.ts
// @ai-rules:
// 1. [Constraint]: Pure function, zero deps. Strips ANSI escape sequences from terminal output.
// 2. [Pattern]: Used by CiContextCard for console_tail rendering.
// 3. [Pattern]: stripJenkinsNoise removes Jenkins-specific noise (ha://// blobs, [Pipeline] boundaries).

export function stripAnsi(text: string): string {
  return text.replace(
    /[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g,
    '',
  );
}

const PIPELINE_ANNOTATION_RE = /ha:\/\/\/\/[A-Za-z0-9+\/=]+/g;
const PIPELINE_BOUNDARY_RE = /^\[Pipeline\]\s*(?:\/\/\s*\w+|End of Pipeline|\{|\}|stage).*?(?:\r?\n|$)/gm;
const BLANK_RUN_RE = /(?:\r?\n){3,}/g;

export function stripJenkinsNoise(text: string): string {
  return text
    .replace(PIPELINE_ANNOTATION_RE, '')
    .replace(PIPELINE_BOUNDARY_RE, '')
    .replace(BLANK_RUN_RE, '\n\n')
    .trim();
}
