import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { axe } from 'vitest-axe'
import { BorderBeam } from './border-beam'

const root = (container: HTMLElement) => container.querySelector('[data-slot="border-beam"]') as HTMLElement
const ring = (container: HTMLElement) => container.querySelector('[data-slot="border-beam-ring"]') as HTMLElement

describe('BorderBeam', () => {
  it('renders its children inside the wrapper', () => {
    render(
      <BorderBeam>
        <span>Content</span>
      </BorderBeam>,
    )
    expect(screen.getByText('Content').closest('[data-slot="border-beam"]')).not.toBeNull()
  })

  it('paints a decorative comet that fades into a transparent tail', () => {
    const { container } = render(<BorderBeam />)
    expect(ring(container)).toHaveAttribute('aria-hidden')
    expect(ring(container).style.background).toContain('conic-gradient(from var(--border-beam-angle), transparent')
  })

  it('maps color and length onto the gradient, and thickness onto the ring', () => {
    const { container } = render(<BorderBeam color="#8EC5FF" length={25} thickness={3} />)
    const style = ring(container).style
    expect(style.background).toContain('#8EC5FF 25%')
    expect(style.padding).toBe('3px')
  })

  it('forwards speed and delay as CSS variables', () => {
    const { container } = render(<BorderBeam speed={10} delay={-2} />)
    const style = root(container).style
    expect(style.getPropertyValue('--border-beam-duration')).toBe('10s')
    expect(style.getPropertyValue('--border-beam-delay')).toBe('-2s')
  })

  it('is always-on (no data-reveal) by default', () => {
    const { container } = render(<BorderBeam />)
    expect(root(container)).not.toHaveAttribute('data-reveal')
    expect(ring(container)).not.toHaveClass('opacity-0')
  })

  it('marks managed visibility via data-reveal for interaction triggers', () => {
    const { container } = render(<BorderBeam revealOn={['hover', 'press']} />)
    expect(root(container)).toHaveAttribute('data-reveal', 'hover press')
    expect(root(container)).not.toHaveAttribute('data-revealed')
    expect(ring(container)).toHaveClass('opacity-0', '[animation-play-state:paused]')
  })

  it('reflects the controlled reveal prop via data-revealed', () => {
    const { container, rerender } = render(<BorderBeam reveal={false} />)
    // Controlled mode is still "managed" so the beam can be hidden when false.
    expect(root(container)).toHaveAttribute('data-reveal', '')
    expect(root(container)).not.toHaveAttribute('data-revealed')

    rerender(<BorderBeam reveal />)
    expect(root(container)).toHaveAttribute('data-revealed')
    expect(ring(container)).toHaveClass('opacity-100')
  })

  it('opts into the touch fallback via data-show-on-touch', () => {
    const { container, rerender } = render(<BorderBeam revealOn="hover" />)
    expect(root(container)).not.toHaveAttribute('data-show-on-touch')

    rerender(<BorderBeam revealOn="hover" showOnTouch />)
    expect(root(container)).toHaveAttribute('data-show-on-touch')
  })

  it('groups and scales the ring on press when pressScale is set', () => {
    const { container } = render(<BorderBeam pressScale />)
    expect(root(container)).toHaveClass('group/beam')
    expect(ring(container)).toHaveClass('group-active/beam:scale-[0.97]')
  })

  it('merges a consumer className onto the wrapper', () => {
    const { container } = render(<BorderBeam className="rounded-full" />)
    expect(root(container)).toHaveClass('rounded-full')
    expect(root(container)).not.toHaveClass('rounded-xl')
  })

  it('has no accessibility violations (the beam is decorative)', async () => {
    const { container } = render(
      <BorderBeam>
        <p>Readable content</p>
      </BorderBeam>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
