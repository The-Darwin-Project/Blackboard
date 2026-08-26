// BlackBoard/ui/src/utils/stripAnsi.ts
// @ai-rules:
// 1. [Constraint]: Pure function, zero deps. Strips ANSI escape sequences from terminal output.
// 2. [Pattern]: Used by CiContextCard for console_tail rendering.

export function stripAnsi(text: string): string {
  return text.replace(
    /[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g,
    '',
  );
}
