import type * as React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectGroupLabel,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from './select'

type SelectArgs = {
  defaultValue?: string | null
  value?: string | null
  onValueChange?: (value: string | null) => void
  size?: 'sm' | 'md' | 'lg'
  variant?: 'outline' | 'soft'
  alignItemWithTrigger?: boolean
  clearable?: boolean
  placeholder?: string
  startSlot?: React.ReactNode
  endSlot?: React.ReactNode
}

function renderSelect({
  defaultValue,
  value,
  onValueChange,
  size,
  variant,
  alignItemWithTrigger,
  clearable,
  placeholder = 'Pick a fruit',
  startSlot,
  endSlot,
}: SelectArgs = {}) {
  return render(
    <Select
      {...(size !== undefined && { size })}
      {...(variant !== undefined && { variant })}
      {...(alignItemWithTrigger !== undefined && { alignItemWithTrigger })}
      {...(defaultValue != null && { defaultValue })}
      {...(value !== undefined && { value: value as never })}
      {...(onValueChange !== undefined && { onValueChange: onValueChange as never })}
    >
      <SelectTrigger
        {...(clearable !== undefined && { clearable })}
        {...(startSlot !== undefined && { startSlot })}
        {...(endSlot !== undefined && { endSlot })}
        aria-label={placeholder}
      >
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectGroupLabel>Citrus</SelectGroupLabel>
          <SelectItem value="orange">Orange</SelectItem>
          <SelectItem value="lemon">Lemon</SelectItem>
        </SelectGroup>
        <SelectSeparator />
        <SelectGroup>
          <SelectGroupLabel>Berries</SelectGroupLabel>
          <SelectItem value="strawberry">Strawberry</SelectItem>
          <SelectItem value="blueberry" disabled>
            Blueberry
          </SelectItem>
        </SelectGroup>
      </SelectContent>
    </Select>,
  )
}

// Base UI's popup animation toggles pointer-events while entering, which
// trips user-event's default safety check. Disable the check across tests.
const setupUser = () => userEvent.setup({ pointerEventsCheck: 0 })

describe('Select', () => {
  it('tags the trigger with data-slot', () => {
    renderSelect({ size: 'lg', variant: 'soft' })
    const trigger = screen.getByRole('combobox')
    expect(trigger.getAttribute('data-slot')).toBe('select-trigger')
  })

  it('does not render content before being opened', () => {
    renderSelect()
    expect(screen.queryByText('Orange')).toBeNull()
  })

  it('opens on click and renders popup with size-driven radius', async () => {
    const user = setupUser()
    renderSelect({ size: 'sm' })

    await user.click(screen.getByRole('combobox'))
    const item = await screen.findByText('Orange')
    const popup = item.closest('[data-slot="select-content"]') as HTMLElement
    expect(popup).not.toBeNull()
    expect(popup.className).toContain('rounded-md')
    expect(popup.className).toContain('bg-background')
    expect(popup.className).toContain('border-border-overlay')
  })

  it('selects an item, closes the popup, and fires onValueChange', async () => {
    const user = setupUser()
    const onValueChange = vi.fn()
    renderSelect({ onValueChange })

    await user.click(screen.getByRole('combobox'))
    await user.click(await screen.findByRole('option', { name: 'Lemon' }))

    expect(onValueChange).toHaveBeenCalledWith('lemon', expect.anything())
    await waitFor(() => {
      expect(screen.queryByRole('option', { name: 'Strawberry' })).toBeNull()
    })
  })

  it('renders the check indicator on the selected item', async () => {
    const user = setupUser()
    renderSelect({ defaultValue: 'orange' })
    await user.click(screen.getByRole('combobox'))

    const items = await screen.findAllByRole('option')
    const selected = items.find((item) => item.getAttribute('data-selected') !== null)
    expect(selected).toBeDefined()
    expect(selected!.querySelector('[data-slot="select-item-indicator"] svg')).not.toBeNull()
  })

  it('renders chevron-down (with rotate on open) when alignItemWithTrigger=false', async () => {
    const user = setupUser()
    renderSelect({ alignItemWithTrigger: false })
    const trigger = screen.getByRole('combobox')
    const icon = trigger.querySelector('[data-slot="select-icon"]') as SVGElement
    expect(icon).not.toBeNull()
    expect(icon.getAttribute('class') ?? '').toContain('data-popup-open:rotate-180')

    await user.click(trigger)
    await screen.findByRole('option', { name: 'Orange' })
    expect(trigger.getAttribute('data-popup-open')).toBe('')
  })

  it('renders the chevrons icon when alignItemWithTrigger=true', () => {
    renderSelect({ alignItemWithTrigger: true })
    const trigger = screen.getByRole('combobox')
    const icon = trigger.querySelector('[data-slot="select-icon"]') as SVGElement
    expect(icon).not.toBeNull()
    expect(icon.getAttribute('class') ?? '').not.toContain('rotate-180')
    // The two-arrow icon has two <path> elements (up + down chevrons combined as one path).
    expect(icon.querySelector('path')).not.toBeNull()
  })

  it('shows the clear control only when a value is present and clears on click', async () => {
    const user = setupUser()
    const onValueChange = vi.fn()
    renderSelect({ defaultValue: 'orange', clearable: true, onValueChange })

    const clearControl = document.querySelector('[data-slot="select-clear"]') as HTMLElement
    expect(clearControl).toBeTruthy()

    await user.click(clearControl)
    expect(onValueChange).toHaveBeenCalledWith(null, expect.anything())

    await waitFor(() => {
      expect(document.querySelector('[data-slot="select-clear"]')).toBeNull()
    })
  })

  it('clears via Delete/Backspace on the trigger without remounting or losing focus', async () => {
    const user = setupUser()
    const onValueChange = vi.fn()
    renderSelect({ defaultValue: 'orange', clearable: true, onValueChange })

    const trigger = screen.getByRole('combobox')
    trigger.focus()
    expect(document.activeElement).toBe(trigger)

    await user.keyboard('{Backspace}')
    expect(onValueChange).toHaveBeenCalledWith(null, expect.anything())

    await waitFor(() => {
      expect(document.querySelector('[data-slot="select-clear"]')).toBeNull()
    })
    expect(screen.getByRole('combobox')).toBe(trigger)
    expect(document.activeElement).toBe(trigger)
  })

  it('does not render the clear control when there is no value', () => {
    renderSelect({ clearable: true })
    expect(document.querySelector('[data-slot="select-clear"]')).toBeNull()
  })

  it('closes on Escape', async () => {
    const user = setupUser()
    renderSelect()
    await user.click(screen.getByRole('combobox'))
    await screen.findByRole('option', { name: 'Orange' })

    await user.keyboard('{Escape}')
    await waitFor(() => {
      expect(screen.queryByRole('option', { name: 'Orange' })).toBeNull()
    })
  })

  it('renders startSlot and endSlot inside the trigger', () => {
    renderSelect({
      startSlot: <span data-testid="start">@</span>,
      endSlot: <span data-testid="end">↗</span>,
    })
    const trigger = screen.getByRole('combobox')
    expect(trigger.querySelector('[data-slot="select-trigger-start"]')).not.toBeNull()
    expect(trigger.querySelector('[data-slot="select-trigger-end"]')).not.toBeNull()
    expect(screen.getByTestId('start')).toBeTruthy()
    expect(screen.getByTestId('end')).toBeTruthy()
  })

  it('omits slot wrappers when slots are not provided', () => {
    renderSelect()
    const trigger = screen.getByRole('combobox')
    expect(trigger.querySelector('[data-slot="select-trigger-start"]')).toBeNull()
    expect(trigger.querySelector('[data-slot="select-trigger-end"]')).toBeNull()
  })

  it('mirrors a standalone aria-invalid to data-invalid on the trigger', () => {
    render(
      <Select>
        <SelectTrigger aria-invalid aria-label="Pick a fruit">
          <SelectValue placeholder="Pick a fruit" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="orange">Orange</SelectItem>
        </SelectContent>
      </Select>,
    )
    const trigger = screen.getByRole('combobox')
    expect(trigger.getAttribute('data-invalid')).toBe('')
    expect(trigger.getAttribute('aria-invalid')).toBe('true')
  })

  it('does not set data-invalid when aria-invalid is absent', () => {
    renderSelect()
    expect(screen.getByRole('combobox').getAttribute('data-invalid')).toBeNull()
  })

  it('has no accessibility violations (closed state)', async () => {
    const { container } = renderSelect()
    expect(await axe(container)).toHaveNoViolations()
  })
})
