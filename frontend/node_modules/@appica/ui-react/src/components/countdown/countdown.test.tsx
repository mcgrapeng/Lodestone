import { render, screen, act } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { axe } from 'vitest-axe'
import { Countdown, CountdownSegment } from './countdown'

const BASE = new Date('2026-06-19T00:00:00.000Z').getTime()
const SECOND = 1000

function offset({ d = 0, h = 0, m = 0, s = 0 }) {
  return ((d * 24 + h) * 60 + m) * 60 * SECOND + s * SECOND
}

afterEach(() => {
  vi.useRealTimers()
})

describe('Countdown', () => {
  it('breaks a future targetDate into day/hour/minute/second segments', () => {
    vi.useFakeTimers()
    vi.setSystemTime(BASE)
    render(
      <Countdown targetDate={BASE + offset({ d: 2, h: 5, m: 10, s: 30 })}>
        <CountdownSegment unit="days" />
        <CountdownSegment unit="hours" />
        <CountdownSegment unit="minutes" />
        <CountdownSegment unit="seconds" />
      </Countdown>,
    )

    expect(screen.getByText('02')).toBeInTheDocument()
    expect(screen.getByText('05')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('30')).toBeInTheDocument()
  })

  it('counts down as time passes', () => {
    vi.useFakeTimers()
    vi.setSystemTime(BASE)
    render(
      <Countdown targetDate={BASE + offset({ d: 2, h: 5, m: 10, s: 30 })}>
        <CountdownSegment unit="seconds" />
      </Countdown>,
    )

    expect(screen.getByText('30')).toBeInTheDocument()
    act(() => {
      vi.advanceTimersByTime(SECOND)
    })
    expect(screen.getByText('29')).toBeInTheDocument()
  })

  it('fires onComplete once when it reaches zero', () => {
    vi.useFakeTimers()
    vi.setSystemTime(BASE)
    const onComplete = vi.fn()
    render(
      <Countdown duration={3} onComplete={onComplete}>
        <CountdownSegment unit="seconds" />
      </Countdown>,
    )

    expect(onComplete).not.toHaveBeenCalled()
    act(() => {
      vi.advanceTimersByTime(3 * SECOND)
    })
    expect(onComplete).toHaveBeenCalledOnce()

    act(() => {
      vi.advanceTimersByTime(5 * SECOND)
    })
    expect(onComplete).toHaveBeenCalledOnce()
  })

  it('exposes a timer role', () => {
    render(
      <Countdown duration={60} aria-label="Sale ends in">
        <CountdownSegment unit="minutes" />
      </Countdown>,
    )
    expect(screen.getByRole('timer', { name: 'Sale ends in' })).toBeInTheDocument()
  })

  it('forwards className to the root', () => {
    render(
      <Countdown duration={60} className="custom-class" aria-label="Timer">
        <CountdownSegment unit="seconds" />
      </Countdown>,
    )
    expect(screen.getByRole('timer').className).toContain('custom-class')
  })

  it('passes the parts to a render-prop child', () => {
    vi.useFakeTimers()
    vi.setSystemTime(BASE)
    render(<Countdown duration={5}>{(parts) => <span>{parts.seconds}s left</span>}</Countdown>)
    expect(screen.getByText('5s left')).toBeInTheDocument()
  })
})

describe('CountdownSegment', () => {
  it('renders a standalone value without a Countdown parent', () => {
    render(<CountdownSegment value={7} aria-label="Items" />)
    expect(screen.getByText('07')).toBeInTheDocument()
  })

  it('zero-pads to minDigits', () => {
    render(<CountdownSegment value={5} minDigits={3} />)
    expect(screen.getByText('005')).toBeInTheDocument()
  })

  it('keeps digits in left-to-right order regardless of layout direction', () => {
    const { container } = render(<CountdownSegment value={195} />)
    // The digit roller row is pinned to LTR so numbers never mirror under dir="rtl".
    expect(container.querySelector('[data-slot="countdown-segment"] [aria-hidden="true"]')).toHaveAttribute(
      'dir',
      'ltr',
    )
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <Countdown duration={3600} aria-label="Offer ends in">
        <CountdownSegment unit="hours" />
        <CountdownSegment unit="minutes" />
        <CountdownSegment unit="seconds" />
      </Countdown>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
