import { render, screen, act } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { axe } from 'vitest-axe'
import { TextAnimate, type TextAnimateUnitContext } from './text-animate'
import { ReducedMotionProvider } from '../../providers/reduced-motion-provider'

afterEach(() => {
  vi.useRealTimers()
})

describe('TextAnimate', () => {
  it('always exposes the full text to assistive tech via an sr-only copy', () => {
    render(
      <TextAnimate autoPlay={false} progress={0}>
        Hello world
      </TextAnimate>,
    )
    // The visual layer is aria-hidden; the sr-only node carries the real text.
    expect(screen.getByText('Hello world')).toHaveClass('sr-only')
  })

  it('splits into per-character units at full progress', () => {
    const { container } = render(
      <TextAnimate effect="flip" progress={1}>
        abc
      </TextAnimate>,
    )
    const units = container.querySelectorAll('[data-slot="text-animate-unit"]')
    expect(units).toHaveLength(3)
    expect(Array.from(units, (u) => u.textContent).join('')).toBe('abc')
  })

  it('splits by word when the effect/level calls for it', () => {
    const { container } = render(
      <TextAnimate by="word" effect="highlight" progress={1}>
        one two three
      </TextAnimate>,
    )
    const units = container.querySelectorAll('[data-slot="text-animate-unit"]')
    expect(units).toHaveLength(3)
    expect(units[0]).toHaveTextContent('one')
    expect(units[2]).toHaveTextContent('three')
  })

  it('sweeps the shimmer glare across the whole string and returns to the same frame at both ends of the loop', () => {
    const { container, rerender } = render(
      <TextAnimate effect="shimmer" progress={0}>
        Generating response
      </TextAnimate>,
    )
    const visual = () => container.querySelector('[aria-hidden="true"]') as HTMLElement

    // The gradient paints one band over the whole string, so it lives on the wrapper, not the units.
    expect(visual().style.backgroundClip).toBe('text')
    expect(visual().style.backgroundImage).toContain('linear-gradient')
    // Band parked off the leading edge.
    expect(visual().style.backgroundPosition).toBe('100% 0px')

    rerender(
      <TextAnimate effect="shimmer" progress={0.5}>
        Generating response
      </TextAnimate>,
    )
    expect(visual().style.backgroundPosition).toBe('50% 0px')

    // Parked off the trailing edge, which paints identically to progress 0.
    rerender(
      <TextAnimate effect="shimmer" progress={1}>
        Generating response
      </TextAnimate>,
    )
    expect(visual().style.backgroundPosition).toBe('0% 0px')
  })

  it('keeps the shimmer glare identical however the text is split, so `by` stays orthogonal', () => {
    const positions = (['line', 'word', 'char'] as const).map((by) => {
      const { container, unmount } = render(
        <TextAnimate effect="shimmer" by={by} progress={0.4}>
          Generating a response
        </TextAnimate>,
      )
      const visual = container.querySelector('[aria-hidden="true"]') as HTMLElement
      const units = container.querySelectorAll('[data-slot="text-animate-unit"]').length
      const result = { by, units, position: visual.style.backgroundPosition, image: visual.style.backgroundImage }
      unmount()
      return result
    })

    // Splitting finer must change the unit count without touching the glare.
    expect(positions.map((p) => p.units)).toEqual([1, 3, 19])
    expect(new Set(positions.map((p) => p.position)).size).toBe(1)
    expect(new Set(positions.map((p) => p.image)).size).toBe(1)
  })

  it('drops the shimmer gradient under reduced motion so the text keeps its own color', () => {
    const { container } = render(
      <ReducedMotionProvider disableAnimations>
        <TextAnimate effect="shimmer">Generating response</TextAnimate>
      </ReducedMotionProvider>,
    )
    const visual = container.querySelector('[aria-hidden="true"]') as HTMLElement
    expect(visual.style.backgroundImage).toBe('')
    expect(visual.style.webkitTextFillColor).toBe('')
    expect(visual).toHaveTextContent('Generating response')
  })

  it('drives the animation from a controlled progress value', () => {
    const { container, rerender } = render(
      <TextAnimate effect="typewriter" progress={0}>
        Hi
      </TextAnimate>,
    )
    const visual = container.querySelector('[aria-hidden="true"]')!
    // Nothing typed yet (aside from the caret element which has no text).
    expect(visual.textContent).toBe('')

    rerender(
      <TextAnimate effect="typewriter" progress={1}>
        Hi
      </TextAnimate>,
    )
    expect(visual.textContent).toContain('Hi')
  })

  it('passes a custom effect function the local progress and unit context', () => {
    const effect = vi.fn((p: number, _ctx: TextAnimateUnitContext) => ({ style: { opacity: p } }))
    render(
      <TextAnimate effect={effect} by="char" stagger={0} progress={0.5}>
        ab
      </TextAnimate>,
    )
    expect(effect).toHaveBeenCalled()
    const [, ctx] = effect.mock.calls[0]!
    expect(ctx).toMatchObject({ total: 2, by: 'char', globalProgress: 0.5 })
  })

  it('advances the built-in clock with requestAnimationFrame to reveal text over time', async () => {
    // Each frame ticks the mock clock forward, so elapsed time actually grows.
    let t = 0
    vi.spyOn(performance, 'now').mockImplementation(() => t)
    const rafSpy = vi.spyOn(globalThis, 'requestAnimationFrame').mockImplementation((cb: FrameRequestCallback) => {
      t += 700
      return setTimeout(() => cb(t), 0) as unknown as number
    })

    const { container } = render(
      <TextAnimate effect="typewriter" duration={1}>
        Hi
      </TextAnimate>,
    )
    const visual = container.querySelector('[aria-hidden="true"]')!
    expect(visual.textContent).toBe('')

    for (let i = 0; i < 6; i++) {
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0))
      })
    }
    expect(visual.textContent).toContain('Hi')

    rafSpy.mockRestore()
  })

  it('renders the final, fully-revealed frame under reduced motion', () => {
    const { container } = render(
      <ReducedMotionProvider disableAnimations>
        <TextAnimate effect="typewriter" duration={5}>
          Hello
        </TextAnimate>
      </ReducedMotionProvider>,
    )
    const visual = container.querySelector('[aria-hidden="true"]')!
    // reduced motion snaps the internal clock's output straight to the last frame.
    expect(visual.textContent).toContain('Hello')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <p>
        <TextAnimate effect="highlight" progress={1}>
          Accessible animated text
        </TextAnimate>
      </p>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
