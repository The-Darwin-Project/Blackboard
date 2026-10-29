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

    withCustomEnv(env) {
        this.envOverrides = { ...this.envOverrides, ...env };
        return this;
    }

    async whenHookEvaluated() {
        const inputJson = {
            toolCall: {
                name: this.tool,
                args: this.command
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
});
