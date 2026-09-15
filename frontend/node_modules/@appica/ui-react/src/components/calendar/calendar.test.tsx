import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { Calendar } from './calendar'

const MAY_15_2026 = new Date(2026, 4, 15)

describe('Calendar', () => {
  it('renders a grid with day buttons for the given month', () => {
    render(<Calendar mode="single" month={MAY_15_2026} />)
    expect(screen.getByRole('grid')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /May 15th, 2026/ })).toBeInTheDocument()
  })

  it('selects a date when a day is clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(<Calendar mode="single" month={MAY_15_2026} onSelect={onSelect} />)
    await user.click(screen.getByRole('button', { name: /May 20th, 2026/ }))
    expect(onSelect).toHaveBeenCalled()
    const [selected] = onSelect.mock.calls[0]!
    expect(selected).toBeInstanceOf(Date)
    expect((selected as Date).getDate()).toBe(20)
  })

  it('reflects the controlled selected date with aria-selected', () => {
    render(<Calendar mode="single" month={MAY_15_2026} selected={new Date(2026, 4, 15)} />)
    const cell = screen.getByRole('gridcell', { selected: true })
    expect(cell).toHaveAttribute('data-day', '2026-05-15')
  })

  it('keeps focus on the focused day across a controlled selected update', () => {
    const { rerender } = render(<Calendar mode="single" month={MAY_15_2026} selected={new Date(2026, 4, 10)} />)
    const day15 = screen.getByRole('button', { name: /May 15th, 2026/ })
    day15.focus()
    expect(document.activeElement).toBe(day15)

    rerender(<Calendar mode="single" month={MAY_15_2026} selected={new Date(2026, 4, 20)} />)

    const day15After = screen.getByRole('button', { name: /May 15th, 2026/ })
    expect(day15After).toBe(day15)
    expect(document.activeElement).toBe(day15)
  })

  it('applies size variant via --cell-size CSS variable on the root', () => {
    const { container, rerender } = render(<Calendar mode="single" month={MAY_15_2026} size="sm" />)
    expect(container.querySelector('[data-slot="calendar"]')?.className).toContain('--cell-size:--spacing(6)')

    rerender(<Calendar mode="single" month={MAY_15_2026} size="lg" />)
    expect(container.querySelector('[data-slot="calendar"]')?.className).toContain('--cell-size:--spacing(10)')
  })

  it('renders prev/next navigation buttons that change months', async () => {
    const user = userEvent.setup()
    const onMonthChange = vi.fn()
    render(<Calendar month={MAY_15_2026} onMonthChange={onMonthChange} />)

    await user.click(screen.getByRole('button', { name: /next month/i }))
    expect(onMonthChange).toHaveBeenCalled()
    const [nextMonth] = onMonthChange.mock.calls[0]!
    expect((nextMonth as Date).getMonth()).toBe(5)
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<Calendar mode="single" month={MAY_15_2026} />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
