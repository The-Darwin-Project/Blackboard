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

  // Handle node clicks
  const handleClick = useCallback(
    (event: Event) => {
      const target = event.target as Element;
      // Mermaid nodes have class "node" or are children of nodes
      const node = target.closest('.node');
      if (node && onNodeClick) {
        // Extract service name from node label
        const labelElement = node.querySelector('.nodeLabel');
        if (labelElement?.textContent) {
          onNodeClick(labelElement.textContent.trim());
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
