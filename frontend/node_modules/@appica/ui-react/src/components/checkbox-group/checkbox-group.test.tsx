import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { Checkbox } from '../checkbox/checkbox'
import { CheckboxGroup } from './checkbox-group'

describe('CheckboxGroup', () => {
  it('renders with group role', () => {
    render(
      <CheckboxGroup aria-label="Toppings">
        <Checkbox name="cheese" aria-label="Cheese" />
      </CheckboxGroup>,
    )
    expect(screen.getByRole('group', { name: 'Toppings' })).toBeInTheDocument()
  })

  it('lays out vertically by default', () => {
    render(
      <CheckboxGroup aria-label="Toppings" data-testid="group">
        <Checkbox name="a" aria-label="A" />
        <Checkbox name="b" aria-label="B" />
      </CheckboxGroup>,
    )
    expect(screen.getByTestId('group').className).toContain('flex-col')
  })

  it('lays out horizontally when orientation="horizontal"', () => {
    render(
      <CheckboxGroup aria-label="Toppings" orientation="horizontal" data-testid="group">
        <Checkbox name="a" aria-label="A" />
        <Checkbox name="b" aria-label="B" />
      </CheckboxGroup>,
    )
    const group = screen.getByTestId('group')
    expect(group.className).toContain('flex-wrap')
    expect(group.className).not.toContain('flex-col')
  })

  it('reflects defaultValue across child checkboxes', () => {
    render(
      <CheckboxGroup aria-label="Toppings" defaultValue={['cheese']}>
        <Checkbox name="cheese" aria-label="Cheese" />
        <Checkbox name="bacon" aria-label="Bacon" />
      </CheckboxGroup>,
    )
    expect(screen.getByRole('checkbox', { name: 'Cheese' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Bacon' })).not.toBeChecked()
  })

  it('fires onValueChange with the new value array on toggle', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn()
    render(
      <CheckboxGroup aria-label="Toppings" defaultValue={[]} onValueChange={onValueChange}>
        <Checkbox name="cheese" aria-label="Cheese" />
        <Checkbox name="bacon" aria-label="Bacon" />
      </CheckboxGroup>,
    )

    await user.click(screen.getByRole('checkbox', { name: 'Cheese' }))
    expect(onValueChange).toHaveBeenCalledWith(['cheese'], expect.anything())
  })

  it('lets consumer className override default display via tailwind-merge', () => {
    render(
      <CheckboxGroup aria-label="Toppings" className="grid grid-cols-2" data-testid="group">
        <Checkbox name="a" aria-label="A" />
      </CheckboxGroup>,
    )
    const group = screen.getByTestId('group')
    expect(group.className).toContain('grid')
    expect(group.className).toContain('grid-cols-2')
    expect(group.className).not.toMatch(/(^|\s)flex(\s|$)/)
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <CheckboxGroup aria-label="Toppings" defaultValue={['cheese']}>
        <Checkbox name="cheese" aria-label="Cheese" />
        <Checkbox name="bacon" aria-label="Bacon" />
      </CheckboxGroup>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
