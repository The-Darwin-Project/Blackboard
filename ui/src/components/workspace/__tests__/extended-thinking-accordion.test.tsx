import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ExtendedThinkingAccordion from '../ExtendedThinkingAccordion';

describe('ExtendedThinkingAccordion (T-9)', () => {
  const sampleThoughts = `### Step 1: Initial Investigation
Examined log traces and discovered latency in database query.

### Step 2: Resolution Strategy
Apply caching layer to mitigate contention.`;

  it('renders collapsed state with summary and step counter or time indicator', () => {
    render(
      <ExtendedThinkingAccordion
        thoughts={sampleThoughts}
        timestamp={1700000000}
        isStreaming={false}
      />
    );

    // Collapsed header should display thinking indicator
    expect(screen.getByText(/thinking/i)).toBeInTheDocument();

    // Body content should not be visible initially when collapsed
    expect(screen.queryByText(/Initial Investigation/i)).not.toBeInTheDocument();
  });

  it('expands on click to reveal full markdown reasoning and collapses when clicked again', () => {
    render(
      <ExtendedThinkingAccordion
        thoughts={sampleThoughts}
        timestamp={1700000000}
        isStreaming={false}
      />
    );

    const toggleButton = screen.getByRole('button', { name: /thinking/i }) || screen.getByText(/thinking/i);
    fireEvent.click(toggleButton);

    // Body content should now be visible
    expect(screen.getByText(/Initial Investigation/i)).toBeInTheDocument();
    expect(screen.getByText(/Resolution Strategy/i)).toBeInTheDocument();

    // Clicking again collapses it
    fireEvent.click(toggleButton);
    expect(screen.queryByText(/Initial Investigation/i)).not.toBeInTheDocument();
  });

  it('renders live pulse indicator during streaming state', () => {
    const { container } = render(
      <ExtendedThinkingAccordion
        thoughts="Still thinking..."
        timestamp={1700000000}
        isStreaming={true}
      />
    );

    // Live pulsing element (e.g., animate-pulse or pulse indicator)
    const pulseElement = container.querySelector('.animate-pulse');
    expect(pulseElement).toBeTruthy();
  });

  it('handles empty thoughts gracefully without throwing', () => {
    expect(() => {
      render(
        <ExtendedThinkingAccordion
          thoughts=""
          timestamp={1700000000}
          isStreaming={false}
        />
      );
    }).not.toThrow();
  });
});
