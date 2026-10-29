// BlackBoard/gemini-sidecar/tests/validate-mutations.test.js
// @ai-rules:
// 1. [Constraint]: 4-Layer Farley ATDD executable specification for PreToolUse hook tampering lock (T-2, T-3, T-7).
// 2. [Pattern]: Layer 1: Domain Scenarios, Layer 2: Domain DSL, Layer 3: Protocol Drivers (subprocess spawn + mock http), Layer 4: SUT Target.
// 3. [Contract]: Developer role under atdd_green is strictly denied from mutating test/spec files.
//               QE role under atdd_red is allowed. Non-test files are allowed. Legacy autonomous is allowed.
const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const http = require('node:http');
const path = require('node:path');

// =============================================================================
// Layer 4: SUT Target Path
// =============================================================================
const HOOK_PATH = path.resolve(__dirname, '..', 'hooks', 'validate-mutations.sh');

// =============================================================================
// Layer 3: Protocol Drivers
// =============================================================================
class HookProcessDriver {
    /**
     * Executes validate-mutations.sh hook with JSON payload over stdin and environment.
     */
    static async executeHook({ inputJson, env = {} }) {
        return new Promise((resolve) => {
            const hookEnv = {
                PATH: process.env.PATH,
                HOME: process.env.HOME,
                AGENT_CLI: 'agy',
                SIDECAR_PORT: '1', // default dummy port unless overridden
                ...env,
            };

            const proc = cp.spawn('bash', [HOOK_PATH], {
                env: hookEnv,
                stdio: ['pipe', 'pipe', 'pipe'],
            });

            let stdout = '';
            let stderr = '';

            proc.stdout.on('data', (d) => { stdout += d.toString('utf8'); });
            proc.stderr.on('data', (d) => { stderr += d.toString('utf8'); });

            proc.on('close', (code) => {
                let parsed = null;
                try {
                    parsed = JSON.parse(stdout.trim());
                } catch (e) {
                    // JSON parsing failed
                }
                resolve({ code, stdout, stderr, json: parsed });
            });

            proc.stdin.write(JSON.stringify(inputJson));
            proc.stdin.end();
        });
    }

    /**
     * Starts a transient HTTP mock server to simulate the sidecar /hook-status endpoint.
     */
    static async withMockSidecarServer(statusPayload, fn) {
        let tamperReported = false;
        const server = http.createServer((req, res) => {
            if (req.url === '/hook-status') {
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify(statusPayload));
            } else if (req.url === '/proxy/tamper') {
                tamperReported = true;
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ ok: true, strikes: 1 }));
            } else {
                res.writeHead(404);
                res.end();
            }
        });

        await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
        const port = server.address().port;

        try {
            return await fn({ port, didReportTamper: () => tamperReported });
        } finally {
            await new Promise((resolve) => server.close(resolve));
        }
    }
}

// =============================================================================
// Layer 2: Domain DSL Operations
// =============================================================================
class HookTamperDSL {
    constructor() {
        this.role = 'developer';
        this.workStyle = 'atdd_green';
        this.tool = 'Edit';
        this.targetPath = '';
        this.command = '';
        this.envOverrides = {};
        this.rawArgs = null;
        this.executionResult = null;
    }

    givenDeveloperWithAtddGreen(tool, targetPath) {
        this.role = 'developer';
        this.workStyle = 'atdd_green';
        this.tool = tool;
        this.targetPath = targetPath;
        this.command = '';
        return this;
    }

    givenDeveloperShellCommandWithAtddGreen(command) {
        this.role = 'developer';
        this.workStyle = 'atdd_green';
        this.tool = 'execute';
        this.targetPath = '';
        this.command = command;
        return this;
    }

    givenQEWithAtddRed(tool, targetPath) {
        this.role = 'qe';
        this.workStyle = 'atdd_red';
        this.tool = tool;
        this.targetPath = targetPath;
        this.command = '';
        return this;
    }

    givenDeveloperWithAutonomous(tool, targetPath) {
        this.role = 'developer';
        this.workStyle = 'autonomous';
        this.tool = tool;
        this.targetPath = targetPath;
        this.command = '';
        return this;
    }

    givenDeveloperMutationWithRawArgs(tool, rawArgs) {
        this.role = 'developer';
        this.workStyle = 'atdd_green';
        this.tool = tool;
        this.targetPath = '';
        this.command = '';
        this.rawArgs = rawArgs;
        return this;
    }

    withCustomEnv(env) {
        this.envOverrides = { ...this.envOverrides, ...env };
        return this;
    }

    async whenHookEvaluated() {
        const inputJson = {
            toolCall: {
                name: this.tool,
                args: this.rawArgs
                    ? this.rawArgs
                    : this.command
                        ? { CommandLine: this.command, command: this.command }
                        : { TargetFile: this.targetPath, file_path: this.targetPath, path: this.targetPath },
            },
        };

        const env = {
            AGENT_ROLE: this.role,
            DARWIN_WORK_STYLE: this.workStyle,
            ...this.envOverrides,
        };

        this.executionResult = await HookProcessDriver.executeHook({ inputJson, env });
    }

    thenDecisionIsDeny(expectedReasonSubstr = 'Tampering Guard') {
        assert.ok(this.executionResult, 'No execution result available');
        assert.equal(
            this.executionResult.code, 0,
            `Hook exited with code ${this.executionResult.code}, stderr: ${this.executionResult.stderr}`
        );
        assert.ok(this.executionResult.json, `Expected JSON output, got: ${this.executionResult.stdout}`);
        assert.equal(
            this.executionResult.json.decision, 'deny',
            `Expected decision "deny", got "${this.executionResult.json.decision}"`
        );
        if (expectedReasonSubstr) {
            assert.match(
                this.executionResult.json.reason || '',
                new RegExp(expectedReasonSubstr, 'i'),
                `Reason ${this.executionResult.json.reason} should match ${expectedReasonSubstr}`
            );
        }
    }

    thenDecisionIsAllow() {
        assert.ok(this.executionResult, 'No execution result available');
        assert.equal(
            this.executionResult.code, 0,
            `Hook exited with code ${this.executionResult.code}, stderr: ${this.executionResult.stderr}`
        );
        assert.ok(this.executionResult.json, `Expected JSON output, got: ${this.executionResult.stdout}`);
        assert.equal(
            this.executionResult.json.decision, 'allow',
            `Expected decision "allow", got "${this.executionResult.json.decision}"`
        );
    }
}

// =============================================================================
// Layer 1: Domain Scenarios (ATDD Executable Acceptance Tests)
// =============================================================================
describe('PreToolUse Hook Tampering Guard (T-2, T-3, T-7)', () => {

    describe('T-2: Developer role under atdd_green mutating test specifications', () => {
        const testMutationCases = [
            { tool: 'Edit', path: 'tests/test_feature.py', label: 'native Edit on tests/ path' },
            { tool: 'write_to_file', path: 'tests/unit/test_worker.py', label: 'native write_to_file in tests/unit' },
            { tool: 'replace_file_content', path: 'specs/domain_spec.js', label: 'native replace_file_content in specs/' },
            { tool: 'Write', path: 'src/components/PlanProgress.test.tsx', label: 'native Write on *.test.tsx' },
            { tool: 'edit_file', path: 'test_calculator.py', label: 'native edit_file on test_*.py' },
        ];

        for (const tc of testMutationCases) {
            it(`denies native ${tc.label}`, async () => {
                const dsl = new HookTamperDSL();
                dsl.givenDeveloperWithAtddGreen(tc.tool, tc.path);
                await dsl.whenHookEvaluated();
                dsl.thenDecisionIsDeny('Tampering Guard');
            });
        }

        const shellMutationCases = [
            { cmd: 'rm tests/test_feature.py', label: 'shell rm on tests/' },
            { cmd: "sed -i 's/assert False/assert True/' tests/test_foo.py", label: 'shell sed -i on tests/' },
            { cmd: 'echo "def test_ok(): pass" > tests/test_bar.py', label: 'shell redirection > targeting test file' },
            { cmd: 'echo "assert True" >> tests/test_bar.py', label: 'shell append >> targeting test file' },
            { cmd: 'cat new_test.py | tee tests/test_bar.py', label: 'shell tee targeting test file' },
        ];

        for (const tc of shellMutationCases) {
            it(`denies ${tc.label}`, async () => {
                const dsl = new HookTamperDSL();
                dsl.givenDeveloperShellCommandWithAtddGreen(tc.cmd);
                await dsl.whenHookEvaluated();
                dsl.thenDecisionIsDeny('Tampering Guard');
            });
        }

        it('allows developer to mutate production/SUT files under atdd_green', async () => {
            const dsl = new HookTamperDSL();
            dsl.givenDeveloperWithAtddGreen('Write', 'src/routes/queue.py');
            await dsl.whenHookEvaluated();
            dsl.thenDecisionIsAllow();
        });
    });

    describe('T-3: QE role under atdd_red authoring test specifications', () => {
        it('allows QE agent to author and edit test files under atdd_red', async () => {
            const dsl = new HookTamperDSL();
            dsl.givenQEWithAtddRed('Write', 'tests/test_feature.py');
            await dsl.whenHookEvaluated();
            dsl.thenDecisionIsAllow();
        });
    });

    describe('Backward Compatibility: Developer role under autonomous mode', () => {
        it('allows developer to edit test files when work_style is autonomous', async () => {
            const dsl = new HookTamperDSL();
            dsl.givenDeveloperWithAutonomous('Edit', 'tests/test_feature.py');
            await dsl.whenHookEvaluated();
            dsl.thenDecisionIsAllow();
        });
    });

    describe('T-7: Ephemeral pod with empty env vars querying /hook-status', () => {
        it('resolves work_style from sidecar /hook-status HTTP server and denies test edits', async () => {
            await HookProcessDriver.withMockSidecarServer(
                { role: 'developer', workStyle: 'atdd_green', boundEventId: 'evt-456' },
                async ({ port, didReportTamper }) => {
                    const dsl = new HookTamperDSL();
                    dsl.givenDeveloperWithAtddGreen('Write', 'tests/test_foo.py');
                    // Omit DARWIN_WORK_STYLE and AGENT_ROLE from env; supply SIDECAR_PORT
                    dsl.withCustomEnv({
                        AGENT_ROLE: '',
                        DARWIN_WORK_STYLE: '',
                        SIDECAR_PORT: String(port),
                    });

                    await dsl.whenHookEvaluated();
                    dsl.thenDecisionIsDeny('Tampering Guard');
                    assert.ok(didReportTamper(), 'Expected /proxy/tamper to be invoked when tampering intercepted');
                }
            );
        });
    });
    describe('T-2b: test-path matching (H2/A2) -- specific test globs, no over-blocking', () => {
        const denied = [
            { tool: 'Edit', path: 'src/__tests__/foo.js', label: '__tests__/ directory' },
            { tool: 'Write', path: 'conftest.py', label: 'conftest.py' },
            { tool: 'Write', path: 'pkg/sub/conftest.py', label: 'nested conftest.py' },
            { tool: 'Edit', path: 'b_test.go', label: '*_test.go' },
            { tool: 'Edit', path: 'tests/foo.py', label: 'tests/ directory' },
            { tool: 'Edit', path: 'ui/src/App.spec.tsx', label: '*.spec.tsx' },
        ];
        for (const tc of denied) {
            it(`denies ${tc.label} (${tc.path})`, async () => {
                const dsl = new HookTamperDSL();
                dsl.givenDeveloperWithAtddGreen(tc.tool, tc.path);
                await dsl.whenHookEvaluated();
                dsl.thenDecisionIsDeny('Tampering Guard');
            });
        }

        for (const p of ['latest_version.py', 'attestation_service.py', 'src/contest_rules.py', 'src/latest/handler.py']) {
            it(`allows production file ${p} whose name merely contains "test"`, async () => {
                const dsl = new HookTamperDSL();
                dsl.givenDeveloperWithAtddGreen('Write', p);
                await dsl.whenHookEvaluated();
                dsl.thenDecisionIsAllow();
            });
        }

        it('developer-permissions.json no longer carries the over-broad *test* globs', () => {
            const fs = require('node:fs');
            const settings = JSON.parse(fs.readFileSync(
                path.resolve(__dirname, '..', 'claude-settings', 'developer-permissions.json'), 'utf8'));
            const deny = settings.permissions.deny;
            assert.ok(!deny.includes('Edit(**/*test*)') && !deny.includes('Write(**/*test*)'), 'over-broad *test* glob still present');
            for (const g of ['**/test_*.py', '**/*_test.py', '**/*_test.go', '**/*.test.*', '**/*.spec.*',
                '**/test/**', '**/tests/**', '**/__tests__/**', '**/conftest.py']) {
                assert.ok(deny.includes(`Edit(${g})`) && deny.includes(`Write(${g})`), `missing Edit/Write deny for ${g}`);
            }
        });
    });

    describe('T-2c: fail-closed on unresolved work style and unrecognized mutation targets (H4/H5)', () => {
        it('developer with /hook-status unreachable and DARWIN_WORK_STYLE unset is denied (not defaulted to autonomous)', async () => {
            const dsl = new HookTamperDSL();
            dsl.givenDeveloperWithAtddGreen('Write', 'src/routes/queue.py');
            dsl.withCustomEnv({ DARWIN_WORK_STYLE: '', SIDECAR_PORT: '1' });
            await dsl.whenHookEvaluated();
            dsl.thenDecisionIsDeny('failing closed');
        });

        it('a non-developer role with an unresolved work style is not subject to the lock', async () => {
            const dsl = new HookTamperDSL();
            dsl.givenQEWithAtddRed('Write', 'tests/test_feature.py');
            dsl.withCustomEnv({ DARWIN_WORK_STYLE: '', SIDECAR_PORT: '1' });
            await dsl.whenHookEvaluated();
            dsl.thenDecisionIsAllow();
        });

        it('a mutation with no recognizable path key under atdd_green is denied', async () => {
            for (const args of [{}, { unknown_key: 'tests/test_x.py' }, { content: 'x' }]) {
                const dsl = new HookTamperDSL();
                dsl.givenDeveloperMutationWithRawArgs('Write', args);
                await dsl.whenHookEvaluated();
                dsl.thenDecisionIsDeny('failing closed');
            }
        });

        it('alternate path keys (filePath, target_file, notebook_path) are honored', async () => {
            for (const key of ['filePath', 'target_file', 'notebook_path']) {
                const dsl = new HookTamperDSL();
                dsl.givenDeveloperMutationWithRawArgs('Edit', { [key]: 'tests/test_x.py' });
                await dsl.whenHookEvaluated();
                dsl.thenDecisionIsDeny('Tampering Guard');
            }
            const ok = new HookTamperDSL();
            ok.givenDeveloperMutationWithRawArgs('Edit', { filePath: 'src/app.py' });
            await ok.whenHookEvaluated();
            ok.thenDecisionIsAllow();
        });

        it('a test path hidden in edits[] (or alongside a benign path) is still caught', async () => {
            const dsl = new HookTamperDSL();
            dsl.givenDeveloperMutationWithRawArgs('MultiEdit', {
                file_path: 'src/app.py',
                edits: [{ old_string: 'a', new_string: 'b' }, { path: 'tests/test_x.py' }],
            });
            await dsl.whenHookEvaluated();
            dsl.thenDecisionIsDeny('Tampering Guard');
        });
    });

    describe('T-2d: shell tamper vectors beyond sed/rm/redirect (M1)', () => {
        const denyCmds = [
            ['python3 -c', `python3 -c "open('tests/test_x.py','w').write('')"`],
            ['perl -pi', "perl -pi -e 's/False/True/' tests/test_x.py"],
            ['node -e', `node -e "require('fs').unlinkSync('tests/a.test.js')"`],
            ['ruby -e', `ruby -e "File.write('tests/x_spec.rb','')" `],
            ['git checkout --', 'git checkout -- tests/'],
            ['git restore', 'git restore tests'],
            ['git apply targeting tests', 'git apply --include=tests/ change.patch'],
            ['rm -r tests (no trailing slash)', 'rm -r tests'],
            ['rm -f -r tests/ (trailing slash)', 'rm -f -r tests/'],
            ['cp into tests', 'cp /tmp/x.py tests/test_x.py'],
            ['mv into tests', 'mv /tmp/x.py tests/test_x.py'],
            ['install into tests', 'install -m 644 /tmp/x.py tests/test_x.py'],
            ['ln into tests', 'ln -sf /tmp/x.py tests/test_x.py'],
            ['dd of=', 'dd if=/dev/zero of=tests/test_x.py'],
            ['awk -i inplace', "awk -i inplace '{print}' tests/test_x.py"],
        ];
        for (const [label, cmd] of denyCmds) {
            it(`denies ${label}`, async () => {
                const dsl = new HookTamperDSL();
                dsl.givenDeveloperShellCommandWithAtddGreen(cmd);
                await dsl.whenHookEvaluated();
                dsl.thenDecisionIsDeny('Tampering Guard');
            });
        }

        const allowCmds = [
            'pytest tests/', 'python3 -m pytest tests/ -q', 'cat tests/test_x.py', 'git diff', 'git status',
            'git checkout main', 'ls tests/', 'rm -r build/', 'ls latest/', 'npm test',
        ];
        for (const cmd of allowCmds) {
            it(`allows read-only/unrelated command: ${cmd}`, async () => {
                const dsl = new HookTamperDSL();
                dsl.givenDeveloperShellCommandWithAtddGreen(cmd);
                await dsl.whenHookEvaluated();
                dsl.thenDecisionIsAllow();
            });
        }
    });

    describe('Round-2 hardening (R2-1..R2-3)', () => {
        const denyCmds = [
            'rm te""sts/te""st_foo.py', 'rm t\\ests/x.py', "sed -i s/a/b/ 'tests'/x.py",
            'echo x>tests/helper.py', 'git reset --hard', 'git clean -fdx', 'git stash pop',
            'rsync a tests/', 'curl -o tests/x.py u', 'wget -O tests/x.py u',
            'rm test.py', 'rm spec.js', 'rm app/tests.py',
        ];
        for (const cmd of denyCmds) {
            it(`denies ${cmd}`, async () => {
                const dsl = new HookTamperDSL();
                dsl.givenDeveloperShellCommandWithAtddGreen(cmd);
                await dsl.whenHookEvaluated();
                dsl.thenDecisionIsDeny('Tampering Guard');
            });
        }
        const allowCmds = [
            'pytest tests/', 'git status', 'git diff tests/', 'curl -s http://x',
            'rm latest.py', 'rm contest.py', 'rm testing_utils.py',
        ];
        for (const cmd of allowCmds) {
            it(`allows ${cmd}`, async () => {
                const dsl = new HookTamperDSL();
                dsl.givenDeveloperShellCommandWithAtddGreen(cmd);
                await dsl.whenHookEvaluated();
                dsl.thenDecisionIsAllow();
            });
        }
        for (const f of ['test.py', 'spec.js', 'app/tests.py']) {
            it(`denies native Edit of ${f}`, async () => {
                const dsl = new HookTamperDSL();
                dsl.givenDeveloperWithAtddGreen('Edit', f);
                await dsl.whenHookEvaluated();
                dsl.thenDecisionIsDeny('Tampering Guard');
            });
        }
        for (const f of ['latest.py', 'contest.py', 'testing_utils.py']) {
            it(`allows native Edit of ${f}`, async () => {
                const dsl = new HookTamperDSL();
                dsl.givenDeveloperWithAtddGreen('Edit', f);
                await dsl.whenHookEvaluated();
                dsl.thenDecisionIsAllow();
            });
        }
    });
});
