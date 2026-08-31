// BlackBoard/tests/ts_parity_harness.mjs
// @ai-rules:
// 1. [Constraint]: Node harness for test_jenkins_noise_strip_parity.py -- do not add logic here
//    beyond importing stripJenkinsNoise and mapping the corpus. The harness must not implement
//    its own copy of the stripping behavior, or the parity test could pass while both engines
//    silently drift.
// 2. [Pattern]: Invoked via `node --experimental-strip-types` (Node 22.6+) so the real TS source
//    under test is executed directly, unmodified -- no separate build/transpile step to keep in
//    sync by hand.
import { stripJenkinsNoise } from '../ui/src/utils/stripAnsi.ts';

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { raw += chunk; });
process.stdin.on('end', () => {
  const corpus = JSON.parse(raw);
  const results = corpus.map((text) => stripJenkinsNoise(text));
  process.stdout.write(JSON.stringify(results));
});
