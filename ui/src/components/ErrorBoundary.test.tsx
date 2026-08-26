import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import ErrorBoundary from './ErrorBoundary';

function Bomb(): never {
  throw new Error('boom');
}

describe('ErrorBoundary', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // React logs the caught error to console.error; silence it for a clean test run.
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    cleanup();
    consoleErrorSpy.mockRestore();
  });

  it('renders children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <div>safe content</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText('safe content')).toBeTruthy();
  });

  it('renders the default fallback when a child throws during render', () => {
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Something went wrong. Try refreshing.')).toBeTruthy();
  });

  it('renders a custom fallback when provided, instead of crashing the tree above it', () => {
    render(
      <ErrorBoundary fallback={<div>custom fallback</div>}>
        <Bomb />
      </ErrorBoundary>,
    );
    expect(screen.getByText('custom fallback')).toBeTruthy();
    expect(screen.queryByText('Something went wrong. Try refreshing.')).toBeNull();
  });

  it('isolates the failure to the boundary — a sibling outside it still renders', () => {
    render(
      <div>
        <span>sibling content</span>
        <ErrorBoundary>
          <Bomb />
        </ErrorBoundary>
      </div>,
    );
    expect(screen.getByText('sibling content')).toBeTruthy();
    expect(screen.getByText('Something went wrong. Try refreshing.')).toBeTruthy();
  });

  it('resets when remounted under a new key (regression: event selection must not leave the panel permanently tripped)', () => {
    const { rerender } = render(
      <ErrorBoundary key="event-1">
        <Bomb />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Something went wrong. Try refreshing.')).toBeTruthy();

    // Simulates Layout.tsx keying the boundary on selectedEventId: selecting a
    // different event changes the key, forcing React to remount a fresh instance
    // instead of reusing the tripped one.
    rerender(
      <ErrorBoundary key="event-2">
        <div>fresh event content</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText('fresh event content')).toBeTruthy();
    expect(screen.queryByText('Something went wrong. Try refreshing.')).toBeNull();
  });

  it('stays tripped across a rerender with the same key, even once the child stops throwing', () => {
    const { rerender } = render(
      <ErrorBoundary key="event-1">
        <Bomb />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Something went wrong. Try refreshing.')).toBeTruthy();

    rerender(
      <ErrorBoundary key="event-1">
        <div>fresh event content</div>
      </ErrorBoundary>,
    );
    expect(screen.queryByText('fresh event content')).toBeNull();
    expect(screen.getByText('Something went wrong. Try refreshing.')).toBeTruthy();
  });
});
