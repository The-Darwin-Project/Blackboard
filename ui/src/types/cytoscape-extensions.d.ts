// BlackBoard/ui/src/types/cytoscape-extensions.d.ts
/**
 * TypeScript declarations for Cytoscape.js extensions.
 * 
 * These packages don't have published types, so we declare them locally.
 */

declare module 'cytoscape-node-html-label' {
  import cytoscape from 'cytoscape';
  
  interface NodeHtmlLabelParams {
    query?: string;
    halign?: 'left' | 'center' | 'right';
    valign?: 'top' | 'center' | 'bottom';
    halignBox?: 'left' | 'center' | 'right';
    valignBox?: 'top' | 'center' | 'bottom';
    cssClass?: string;
    tpl?: (data: unknown) => string;
  }
  
  interface NodeHtmlLabelExtension {
    (cy: cytoscape.Core, params: NodeHtmlLabelParams[]): void;
  }
  
  const ext: cytoscape.Ext;
  export default ext;
}

declare module 'cytoscape-cose-bilkent' {
  import cytoscape from 'cytoscape';
  const ext: cytoscape.Ext;
  export default ext;
}

// Extend Cytoscape Core interface to include nodeHtmlLabel method
declare module 'cytoscape' {
  interface Core {
    nodeHtmlLabel(params: import('cytoscape-node-html-label').NodeHtmlLabelParams[]): void;
  }
}
