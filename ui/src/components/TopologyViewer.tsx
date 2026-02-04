// BlackBoard/ui/src/components/TopologyViewer.tsx
/**
 * Mermaid-based topology viewer with service status.
 * Uses /topology/mermaid endpoint directly.
 */
import { useEffect, useRef, useCallback } from 'react';
import mermaid from 'mermaid';
import { Loader2, Network } from 'lucide-react';
import { useTopologyMermaid } from '../hooks';

// Initialize Mermaid with dark theme
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    primaryColor: '#6366f1',
    primaryTextColor: '#f8fafc',
    primaryBorderColor: '#334155',
    lineColor: '#64748b',
    secondaryColor: '#1e293b',
    tertiaryColor: '#0f172a',
  },
  flowchart: {
    curve: 'basis',
    padding: 20,
  },
});

interface TopologyViewerProps {
  onNodeClick?: (serviceName: string) => void;
}

function TopologyViewer({ onNodeClick }: TopologyViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { data, isLoading, isError } = useTopologyMermaid();

  // Handle node clicks - uses multiple fallback strategies for robustness
  const handleClick = useCallback(
    (event: Event) => {
      const target = event.target as Element;
      
      // Strategy 1: Find closest node group (most reliable)
      const nodeGroup = target.closest('.node, .nodeGroup, [class*="node"]');
      if (!nodeGroup || !onNodeClick) return;

      // Strategy 2: Try to extract from node ID (format: flowchart-nodeName-123)
      const nodeId = nodeGroup.id || nodeGroup.getAttribute('data-id');
      if (nodeId) {
        const match = nodeId.match(/flowchart-([^-]+)-/);
        if (match) {
          // Convert back from sanitized name (underscores to hyphens)
          const serviceName = match[1].replace(/_/g, '-');
          onNodeClick(serviceName);
          return;
        }
      }

      // Strategy 3: Fallback to text content with multiple selectors
      const labelSelectors = ['.nodeLabel', '.label', 'text', 'tspan', '[class*="label"]'];
      for (const selector of labelSelectors) {
        const labelElement = nodeGroup.querySelector(selector);
        const text = labelElement?.textContent?.trim();
        if (text && text.length > 0 && !text.includes('→')) {
          onNodeClick(text);
          return;
        }
      }
    },
    [onNodeClick]
  );

  useEffect(() => {
    if (!containerRef.current || !data?.mermaid) return;

    const container = containerRef.current;

    // Render Mermaid diagram
    const renderDiagram = async () => {
      try {
        // Clear previous content
        container.innerHTML = '';
        
        // Generate unique ID for this render
        const id = `mermaid-${Date.now()}`;
        
        // Render the diagram
        const { svg } = await mermaid.render(id, data.mermaid);
        container.innerHTML = svg;

        // Add click handlers to nodes
        container.addEventListener('click', handleClick);
      } catch (error) {
        console.error('Mermaid render error:', error);
        container.innerHTML = `
          <div class="flex items-center justify-center h-full text-text-muted">
            <p>Failed to render diagram</p>
          </div>
        `;
      }
    };

    renderDiagram();

    return () => {
      container.removeEventListener('click', handleClick);
    };
  }, [data, handleClick]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 text-accent animate-spin" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-muted gap-2">
        <Network className="w-12 h-12" />
        <p className="text-sm">Unable to load topology</p>
        <p className="text-xs">Check API connection</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="w-full h-full overflow-auto p-4 [&_svg]:max-w-full [&_.node]:cursor-pointer [&_.node:hover]:opacity-80"
    />
  );
}

export default TopologyViewer;
