import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { axe } from 'vitest-axe'
import { BackgroundPattern } from './background-pattern'

describe('BackgroundPattern', () => {
  it('renders its children inside a labeled wrapper', () => {
    render(
      <BackgroundPattern>
        <span>Content</span>
      </BackgroundPattern>,
    )
    expect(screen.getByText('Content')).toBeInTheDocument()
    expect(screen.getByText('Content').closest('[data-slot="background-pattern"]')).not.toBeNull()
  })

  it('paints a single decorative pattern layer when static', () => {
    const { container } = render(<BackgroundPattern variant="grid" />)
    const layers = container.querySelectorAll('[data-slot="background-pattern-layer"]')
    expect(layers).toHaveLength(1)
    layers.forEach((layer) => expect(layer).toHaveAttribute('aria-hidden'))
    expect(container.querySelector('[data-slot="background-pattern-highlight"]')).toBeNull()
  })

  it('mounts a cursor-following highlight when spotlight is enabled', () => {
    const { container } = render(<BackgroundPattern spotlight />)
    const highlight = container.querySelector('[data-slot="background-pattern-highlight"]')
    expect(highlight).not.toBeNull()
    expect(highlight).toHaveAttribute('aria-hidden')
    expect(container.querySelectorAll('[data-slot="background-pattern-layer"]')).toHaveLength(2)
  })

  it('marks the highlight persistent only when requested', () => {
    const { container, rerender } = render(<BackgroundPattern spotlight />)
    expect(container.querySelector('[data-slot="background-pattern-highlight"]')).not.toHaveAttribute('data-persistent')

    rerender(<BackgroundPattern spotlight={{ persistent: true }} />)
    expect(container.querySelector('[data-slot="background-pattern-highlight"]')).toHaveAttribute('data-persistent')
  })

  it('treats the highlight as persistent under prefers-reduced-motion', () => {
    const original = window.matchMedia
    window.matchMedia = ((query: string) =>
      ({
        matches: query.includes('prefers-reduced-motion'),
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList) as typeof window.matchMedia

    try {
      const { container } = render(<BackgroundPattern spotlight />)
      // No `persistent` prop, but reduced motion forces the steady, fade-free path.
      expect(container.querySelector('[data-slot="background-pattern-highlight"]')).toHaveAttribute('data-persistent')
    } finally {
      window.matchMedia = original
    }
  })

  it('resolves the spotlight size from a number, string, or object', () => {
    const { container, rerender } = render(<BackgroundPattern spotlight={300} />)
    const root = () => container.querySelector('[data-slot="background-pattern"]') as HTMLElement
    expect(root().style.getPropertyValue('--spotlight-size')).toBe('300px')

    rerender(<BackgroundPattern spotlight="10rem" />)
    expect(root().style.getPropertyValue('--spotlight-size')).toBe('10rem')

    rerender(<BackgroundPattern spotlight={{ size: 18, persistent: true }} />)
    expect(root().style.getPropertyValue('--spotlight-size')).toBe('18px')
  })

  it('merges a consumer className over the default surface', () => {
    const { container } = render(<BackgroundPattern className="bg-white" />)
    const root = container.querySelector('[data-slot="background-pattern"]')!
    expect(root).toHaveClass('bg-white')
    expect(root).not.toHaveClass('bg-background-subtle')
  })

  it('forwards cellSize as a CSS variable', () => {
    const { container } = render(<BackgroundPattern cellSize={20} />)
    const root = container.querySelector('[data-slot="background-pattern"]') as HTMLElement
    expect(root.style.getPropertyValue('--pattern-cell')).toBe('20px')
  })

  it('has no accessibility violations (decorative layers are hidden)', async () => {
    const { container } = render(
      <BackgroundPattern spotlight>
        <p>Readable content</p>
      </BackgroundPattern>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
