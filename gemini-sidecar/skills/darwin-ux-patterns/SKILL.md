---
name: darwin-ux-patterns
description: UI/UX design patterns for frontend plans. Use when designing user-facing features, tabs, modals, or interaction flows.
roles: [architect]
---

# UI/UX Design Patterns

Apply these principles when your plan includes frontend or user-facing changes.

## User Experience (UX)

### Task Flow

- **Map the user journey first**: Before any UI design, answer: What is the user trying to accomplish? What's the shortest path to get there?
- **Reduce steps to completion**: Every click, scroll, or page switch is friction. If 3 clicks can become 1, do it.
- **Don't make the user remember**: Show context inline. If an order references a product, show the product name -- don't make the user cross-reference another tab.
- **Match the mental model**: Group related information the way users think about it, not how the database stores it. Orders group by date, not by UUID.

### Cognitive Load

- **One primary action per view**: Every screen/section has ONE thing the user is supposed to do. Make it visually dominant.
- **Progressive complexity**: Start with the most common case. Advanced/rare options are secondary (collapsed, smaller, further down).
- **Sensible defaults**: Pre-fill, pre-select, auto-detect where possible. The user corrects, not constructs.
- **Reduce decision fatigue**: If there are 10 filters, show the top 3. Let power users expand.

### Feedback & Trust

- **Immediate feedback**: Every user action gets a visible response within 100ms (button state change, spinner, highlight).
- **Explain "why"**: If something is disabled, say why ("Minimum order $20 for this coupon"). Don't just grey it out.
- **Undo over confirm**: Prefer reversible actions with undo over "Are you sure?" dialogs. Reserve confirmation for truly destructive operations.
- **Show system status**: If a background process is running (deployment, pipeline), show a live indicator. Don't leave the user guessing.

### Information Architecture

- **Proximity = relationship**: Related data lives together. Order total next to line items, not in a separate panel.
- **Hierarchy = importance**: The most-used data is visible by default. Less-used data is one interaction away (expand, tab, tooltip).
- **Consistency across views**: If products show name+price+stock, orders show name+qty+price. Same data, same presentation pattern.

## Interaction Patterns (UI)

- **Progressive disclosure**: Show summary first, details on demand (expand/collapse, drill-down).
- **Inline expansion over modals**: For detail views within lists, expand inline rather than opening a modal. Reserve modals for confirmations and destructive actions.
- **Click targets**: Minimum 44x44px touch target. Entire row clickable for expand, action buttons use `event.stopPropagation()`.
- **Visual affordance**: Clickable rows need a hover state change AND a chevron/caret icon indicating expandability.
- **Collapse on re-click**: Toggling the same row closes it. Opening a new row should close the previous one (accordion pattern).

## State Handling (every view needs all four)

1. **Loading**: Skeleton or spinner while data fetches. Never show empty content during load.
2. **Empty**: Friendly message with suggested action ("No orders yet. Visit the catalog to get started.").
3. **Error**: Inline error with retry option. Never silently fail.
4. **Success**: Transient feedback (toast/flash) for mutations. Persist for navigation-worthy results.

## Visual Hierarchy

- **Typography scale**: Use existing CSS variables. Headers > subheaders > body > metadata. Don't invent new font sizes.
- **Spacing**: Consistent padding within cards/rows. Detail sections indented or visually nested under their parent.
- **Color coding**: Use existing theme variables (`--success`, `--danger`, `--text-secondary`). Status badges use semantic colors.
- **Data density**: Tables for structured data, cards for summaries. Don't mix. Align columns. Right-align numbers and currency.

## Accessibility Basics

- All interactive elements keyboard-navigable (tab order, Enter/Space to activate).
- Expanded/collapsed state communicated via `aria-expanded` attribute.
- Color is never the SOLE indicator -- pair with icons or text labels.
- Form inputs have associated `<label>` elements.

## Responsive Considerations

- Tables: hide low-priority columns on narrow viewports or switch to card layout.
- Touch: no hover-only interactions. Hover enhances, click activates.
- Scroll: detail expansion should scroll the expanded content into view if it's below the fold.

## Plan Checklist

When your plan includes UI changes, verify each step addresses:

**UX**

- [ ] What is the user's goal and what's the shortest path to it?
- [ ] Does the user need to cross-reference another view to understand this data?
- [ ] Is the primary action obvious and visually dominant?

**UI States**

- [ ] What happens on first load (loading state)?
- [ ] What happens with zero data (empty state)?
- [ ] What happens on API failure (error state)?
- [ ] Is the interaction reversible (collapse, undo, cancel)?

**Accessibility**

- [ ] Does it work with keyboard only?
- [ ] Is state change communicated beyond just color?
