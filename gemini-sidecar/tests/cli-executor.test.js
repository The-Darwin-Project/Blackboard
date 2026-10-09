const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const { buildCLICommand, executeCLI } = require('../cli-executor');

describe('CLI Executor', () => {
    it('T-14: resolves Explorer model from EPHEMERAL_MODEL_EXPLORER', () => {
        process.env.EPHEMERAL_MODEL_EXPLORER = 'gemini-test-model';
        const { args } = buildCLICommand('prompt', { role: 'explorer' });
        const modelIndex = args.indexOf('--model');
        assert.ok(modelIndex !== -1, '--model flag should be present');
        assert.equal(args[modelIndex + 1], 'gemini-test-model');
        delete process.env.EPHEMERAL_MODEL_EXPLORER;
    });

    it('T-17: falls back to gemini-2.5-flash on invalid model error', async (t) => {
        // Mock spawn to simulate failure then success
        t.mock.method(cp, 'spawn', (cmd, args) => {
            const EventEmitter = require('node:events');
            const child = new EventEmitter();
            child.stdout = new EventEmitter();
            child.stderr = new EventEmitter();
            
            // Check if it's using the invalid model
            if (args.includes('invalid-model-that-fails')) {
                setTimeout(() => {
                    child.stderr.emit('data', Buffer.from('INVALID_ARGUMENT: model not found'));
                    child.emit('close', 1);
                }, 10);
            } else {
                setTimeout(() => {
                    child.stdout.emit('data', Buffer.from('success'));
                    child.emit('close', 0);
                }, 10);
            }
            return child;
        });

        process.env.EPHEMERAL_MODEL_EXPLORER = 'invalid-model-that-fails';
        // Depending on executeCLI implementation, we assume it returns a result object containing usedModel
        const result = await executeCLI('test', { role: 'explorer' });
        // The implementation should realize the first failed, and retry with gemini-2.5-flash
        assert.equal(result.usedModel, 'gemini-2.5-flash');
        delete process.env.EPHEMERAL_MODEL_EXPLORER;
    });
});
