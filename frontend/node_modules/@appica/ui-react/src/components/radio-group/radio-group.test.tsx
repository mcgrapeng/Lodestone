import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { Radio } from '../radio/radio'
import { RadioGroup } from './radio-group'

describe('RadioGroup', () => {
  it('renders with radiogroup role', () => {
    render(
      <RadioGroup aria-label="Channel">
        <Radio value="a" aria-label="A" />
      </RadioGroup>,
    )
    expect(screen.getByRole('radiogroup', { name: 'Channel' })).toBeInTheDocument()
  })

  it('lays out vertically by default', () => {
    render(
      <RadioGroup aria-label="Channel" data-testid="group">
        <Radio value="a" aria-label="A" />
        <Radio value="b" aria-label="B" />
      </RadioGroup>,
    )
    const group = screen.getByTestId('group')
    expect(group.className).toContain('flex-col')
    expect(group).toHaveAttribute('aria-orientation', 'vertical')
  })

  it('lays out horizontally when orientation="horizontal"', () => {
    render(
      <RadioGroup aria-label="Channel" orientation="horizontal" data-testid="group">
        <Radio value="a" aria-label="A" />
        <Radio value="b" aria-label="B" />
      </RadioGroup>,
    )
    const group = screen.getByTestId('group')
    expect(group.className).toContain('flex-wrap')
    expect(group.className).not.toContain('flex-col')
    expect(group).toHaveAttribute('aria-orientation', 'horizontal')
  })

  it('selects on click and fires onValueChange', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn()
    render(
      <RadioGroup aria-label="Channel" onValueChange={onValueChange}>
        <Radio value="email" aria-label="Email" />
        <Radio value="sms" aria-label="SMS" />
      </RadioGroup>,
    )

    await user.click(screen.getByRole('radio', { name: 'SMS' }))
    expect(onValueChange).toHaveBeenCalledWith('sms', expect.anything())
    expect(screen.getByRole('radio', { name: 'SMS' })).toBeChecked()
  })

  it('lets consumer className override default display via tailwind-merge', () => {
    render(
      <RadioGroup aria-label="Channel" className="grid grid-cols-2" data-testid="group">
        <Radio value="a" aria-label="A" />
      </RadioGroup>,
    )
    const group = screen.getByTestId('group')
    // tailwind-merge dedupes conflicting display utilities - `grid` wins over `flex`.
    expect(group.className).toContain('grid')
    expect(group.className).toContain('grid-cols-2')
    expect(group.className).not.toMatch(/(^|\s)flex(\s|$)/)
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <RadioGroup aria-label="Channel" defaultValue="a">
        <Radio value="a" aria-label="A" />
        <Radio value="b" aria-label="B" />
      </RadioGroup>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
