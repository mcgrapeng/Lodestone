import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { axe } from 'vitest-axe'
import { Meter, MeterLabel, MeterValue, MeterProgress } from './meter'

describe('Meter', () => {
  it('renders with role="meter" and value/min/max attrs', () => {
    render(
      <Meter value={60}>
        <MeterProgress />
      </Meter>,
    )
    const el = screen.getByRole('meter')
    expect(el).toHaveAttribute('data-slot', 'meter')
    expect(el).toHaveAttribute('aria-valuenow', '60')
    expect(el).toHaveAttribute('aria-valuemin', '0')
    expect(el).toHaveAttribute('aria-valuemax', '100')
  })

  it('renders MeterProgress with Track and Indicator; indicator width set by Base UI', () => {
    const { container } = render(
      <Meter value={50}>
        <MeterProgress />
      </Meter>,
    )
    const track = container.querySelector('[data-slot=meter-progress]') as HTMLElement
    const indicator = container.querySelector('[data-slot=meter-indicator]') as HTMLElement
    expect(track).toBeInTheDocument()
    expect(indicator).toBeInTheDocument()
    expect(indicator.style.width).toBe('50%')
  })

  it('forwards className alongside the layout classes', () => {
    render(
      <Meter value={50} className="custom-class">
        <MeterProgress />
      </Meter>,
    )
    const root = screen.getByRole('meter')
    expect(root.className).toContain('custom-class')
    expect(root.className).toContain('grid')
  })

  it('links MeterLabel to root via aria-labelledby', () => {
    render(
      <Meter value={42}>
        <MeterLabel>Storage</MeterLabel>
        <MeterProgress />
      </Meter>,
    )
    const root = screen.getByRole('meter')
    const labelId = root.getAttribute('aria-labelledby')
    expect(labelId).toBeTruthy()
    expect(document.getElementById(labelId!)?.textContent).toBe('Storage')
  })

  it('renders the formatted value via MeterValue', () => {
    render(
      <Meter value={42}>
        <MeterValue />
        <MeterProgress />
      </Meter>,
    )
    expect(screen.getByText('42%')).toBeInTheDocument()
  })

  it('does not set data-status and uses bg-primary when no thresholds are provided', () => {
    const { container } = render(
      <Meter value={60}>
        <MeterProgress />
      </Meter>,
    )
    const root = screen.getByRole('meter')
    expect(root.hasAttribute('data-status')).toBe(false)
    const indicator = container.querySelector('[data-slot=meter-indicator]') as HTMLElement
    expect(indicator.className).toContain('bg-primary')
  })

  describe('threshold coloring (optimum in low region: optimum=10, low=30, high=70)', () => {
    it.each([
      { value: 20, status: 'optimum', bg: 'bg-success-emphasis' },
      { value: 50, status: 'suboptimum', bg: 'bg-warning-emphasis' },
      { value: 90, status: 'invalid', bg: 'bg-error-emphasis' },
    ])('value=$value → data-status=$status, indicator has $bg', ({ value, status, bg }) => {
      const { container } = render(
        <Meter value={value} low={30} high={70} optimum={10}>
          <MeterProgress />
        </Meter>,
      )
      expect(screen.getByRole('meter')).toHaveAttribute('data-status', status)
      const indicator = container.querySelector('[data-slot=meter-indicator]') as HTMLElement
      expect(indicator.className).toContain(bg)
    })
  })

  describe('threshold coloring (optimum in mid region: optimum=50, low=30, high=70)', () => {
    it.each([
      { value: 20, status: 'suboptimum', bg: 'bg-warning-emphasis' },
      { value: 50, status: 'optimum', bg: 'bg-success-emphasis' },
      { value: 90, status: 'suboptimum', bg: 'bg-warning-emphasis' },
    ])('value=$value → data-status=$status, indicator has $bg', ({ value, status, bg }) => {
      const { container } = render(
        <Meter value={value} low={30} high={70} optimum={50}>
          <MeterProgress />
        </Meter>,
      )
      expect(screen.getByRole('meter')).toHaveAttribute('data-status', status)
      const indicator = container.querySelector('[data-slot=meter-indicator]') as HTMLElement
      expect(indicator.className).toContain(bg)
    })
  })

  describe('threshold coloring (optimum in high region: optimum=90, low=30, high=70)', () => {
    it.each([
      { value: 20, status: 'invalid', bg: 'bg-error-emphasis' },
      { value: 50, status: 'suboptimum', bg: 'bg-warning-emphasis' },
      { value: 90, status: 'optimum', bg: 'bg-success-emphasis' },
    ])('value=$value → data-status=$status, indicator has $bg', ({ value, status, bg }) => {
      const { container } = render(
        <Meter value={value} low={30} high={70} optimum={90}>
          <MeterProgress />
        </Meter>,
      )
      expect(screen.getByRole('meter')).toHaveAttribute('data-status', status)
      const indicator = container.querySelector('[data-slot=meter-indicator]') as HTMLElement
      expect(indicator.className).toContain(bg)
    })
  })

  it('statusClassNames overrides the per-status default class', () => {
    const { container, rerender } = render(
      <Meter value={50} low={30} high={70} optimum={50} statusClassNames={{ optimum: 'bg-emerald-500' }}>
        <MeterProgress />
      </Meter>,
    )
    let indicator = container.querySelector('[data-slot=meter-indicator]') as HTMLElement
    expect(indicator.className).toContain('bg-emerald-500')
    expect(indicator.className).not.toContain('bg-success-emphasis')

    // Other statuses keep their defaults
    rerender(
      <Meter value={20} low={30} high={70} optimum={50} statusClassNames={{ optimum: 'bg-emerald-500' }}>
        <MeterProgress />
      </Meter>,
    )
    indicator = container.querySelector('[data-slot=meter-indicator]') as HTMLElement
    expect(indicator.className).toContain('bg-warning-emphasis')
    expect(indicator.className).not.toContain('bg-emerald-500')
  })

  it('statusClassNames.default overrides the no-threshold class', () => {
    const { container } = render(
      <Meter value={60} statusClassNames={{ default: 'bg-sky-500' }}>
        <MeterProgress />
      </Meter>,
    )
    const indicator = container.querySelector('[data-slot=meter-indicator]') as HTMLElement
    expect(indicator.className).toContain('bg-sky-500')
    expect(indicator.className).not.toContain('bg-primary')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <Meter value={60} low={30} high={70} optimum={50}>
        <MeterLabel>Score</MeterLabel>
        <MeterValue />
        <MeterProgress />
      </Meter>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
