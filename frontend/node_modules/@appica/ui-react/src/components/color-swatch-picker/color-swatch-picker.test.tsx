import * as React from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeAll } from 'vitest'
import { axe } from 'vitest-axe'
import { ColorSwatchPicker, ColorSwatchPickerItem } from './color-swatch-picker'
import { type Color, formatColor, parseColor } from '../../lib/color'
import { DirectionProvider } from '../../providers/direction-provider'

const PALETTE = ['#ef4444', '#f59e0b', '#22c55e', '#3b82f6']

beforeAll(() => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    },
  )
})

const options = () => screen.getAllByRole('option')
const indicator = () => document.querySelector('[data-slot=color-swatch-picker-indicator]')

describe('ColorSwatchPicker', () => {
  it('exposes the palette as a single-select listbox', () => {
    render(
      <ColorSwatchPicker aria-label="Brand color" defaultValue="#3b82f6">
        {PALETTE.map((color) => (
          <ColorSwatchPickerItem key={color} color={color} />
        ))}
      </ColorSwatchPicker>,
    )
    expect(screen.getByRole('listbox')).toHaveAccessibleName('Brand color')
    expect(options()).toHaveLength(4)
    expect(options()[3]).toHaveAttribute('aria-selected', 'true')
    expect(options()[0]).toHaveAttribute('aria-selected', 'false')
  })

  it('names each swatch from its color, and takes an override', () => {
    render(
      <ColorSwatchPicker aria-label="Brand color">
        <ColorSwatchPickerItem color="#3b82f6" />
        <ColorSwatchPickerItem color="#ef4444" colorName="Fire truck red" />
      </ColorSwatchPicker>,
    )
    expect(options()[0]).toHaveAccessibleName('vivid blue')
    expect(options()[1]).toHaveAccessibleName('Fire truck red')
  })

  it('selects on click and reports the color', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn<(value: Color) => void>()
    render(
      <ColorSwatchPicker aria-label="Brand color" defaultValue="#ef4444" onValueChange={onValueChange}>
        {PALETTE.map((color) => (
          <ColorSwatchPickerItem key={color} color={color} />
        ))}
      </ColorSwatchPicker>,
    )

    await user.click(options()[2]!)
    expect(formatColor(onValueChange.mock.lastCall![0], 'hex')).toBe('#22c55e')
    expect(options()[2]).toHaveAttribute('aria-selected', 'true')
    expect(options()[0]).toHaveAttribute('aria-selected', 'false')
  })

  it('matches the same color written in another space', () => {
    render(
      <ColorSwatchPicker aria-label="Brand color" value={parseColor('hsl(0, 100%, 50%)')}>
        <ColorSwatchPickerItem color="#ff0000" />
        <ColorSwatchPickerItem color="#00ff00" />
      </ColorSwatchPicker>,
    )
    // Keyed on hexa, so hsl(0, 100%, 50%) and #ff0000 are one entry.
    expect(options()[0]).toHaveAttribute('aria-selected', 'true')
  })

  it('stays put when controlled and the value does not change', async () => {
    const user = userEvent.setup()
    render(
      <ColorSwatchPicker aria-label="Brand color" value="#ef4444" onValueChange={() => {}}>
        {PALETTE.map((color) => (
          <ColorSwatchPickerItem key={color} color={color} />
        ))}
      </ColorSwatchPicker>,
    )
    await user.click(options()[2]!)
    expect(options()[0]).toHaveAttribute('aria-selected', 'true')
  })

  it('keeps one tab stop, on the selected swatch', () => {
    render(
      <ColorSwatchPicker aria-label="Brand color" defaultValue="#22c55e">
        {PALETTE.map((color) => (
          <ColorSwatchPickerItem key={color} color={color} />
        ))}
      </ColorSwatchPicker>,
    )
    expect(options().map((option) => option.tabIndex)).toEqual([-1, -1, 0, -1])
  })

  it('falls back to the first swatch when nothing is selected', () => {
    render(
      <ColorSwatchPicker aria-label="Brand color">
        {PALETTE.map((color) => (
          <ColorSwatchPickerItem key={color} color={color} />
        ))}
      </ColorSwatchPicker>,
    )
    expect(options().map((option) => option.tabIndex)).toEqual([0, -1, -1, -1])
    expect(indicator()).not.toBeInTheDocument()
  })

  it('moves selection with the arrow keys, and wraps', async () => {
    const user = userEvent.setup()
    render(
      <ColorSwatchPicker aria-label="Brand color" defaultValue="#ef4444">
        {PALETTE.map((color) => (
          <ColorSwatchPickerItem key={color} color={color} />
        ))}
      </ColorSwatchPicker>,
    )

    options()[0]!.focus()
    await user.keyboard('{ArrowRight}')
    expect(options()[1]).toHaveAttribute('aria-selected', 'true')
    expect(options()[1]).toHaveFocus()

    await user.keyboard('{End}')
    expect(options()[3]).toHaveAttribute('aria-selected', 'true')

    await user.keyboard('{ArrowRight}')
    expect(options()[0]).toHaveAttribute('aria-selected', 'true')

    await user.keyboard('{Home}')
    expect(options()[0]).toHaveAttribute('aria-selected', 'true')
  })

  it('reverses the horizontal arrows in RTL', async () => {
    const user = userEvent.setup()
    render(
      <DirectionProvider dir="rtl">
        <ColorSwatchPicker aria-label="Brand color" defaultValue="#f59e0b">
          {PALETTE.map((color) => (
            <ColorSwatchPickerItem key={color} color={color} />
          ))}
        </ColorSwatchPicker>
      </DirectionProvider>,
    )

    options()[1]!.focus()
    await user.keyboard('{ArrowRight}')
    expect(options()[0]).toHaveAttribute('aria-selected', 'true')
  })

  it('walks a stack with the vertical arrows', async () => {
    const user = userEvent.setup()
    render(
      <ColorSwatchPicker aria-label="Brand color" layout="stack" defaultValue="#ef4444">
        {PALETTE.map((color) => (
          <ColorSwatchPickerItem key={color} color={color} />
        ))}
      </ColorSwatchPicker>,
    )
    expect(screen.getByRole('listbox')).toHaveAttribute('aria-orientation', 'vertical')

    options()[0]!.focus()
    await user.keyboard('{ArrowDown}')
    expect(options()[1]).toHaveAttribute('aria-selected', 'true')

    await user.keyboard('{ArrowUp}')
    expect(options()[0]).toHaveAttribute('aria-selected', 'true')
  })

  it('jumps a row at a time in a wrapped grid', async () => {
    const user = userEvent.setup()
    render(
      <ColorSwatchPicker aria-label="Brand color" defaultValue="#ef4444">
        {PALETTE.map((color) => (
          <ColorSwatchPickerItem key={color} color={color} />
        ))}
      </ColorSwatchPicker>,
    )

    // jsdom lays nothing out, so stand in two rows of two.
    const boxes = [
      [0, 0],
      [50, 0],
      [0, 50],
      [50, 50],
    ]
    options().forEach((option, index) => {
      Object.defineProperty(option, 'offsetLeft', { value: boxes[index]![0], configurable: true })
      Object.defineProperty(option, 'offsetTop', { value: boxes[index]![1], configurable: true })
    })

    options()[1]!.focus()
    await user.keyboard('{ArrowDown}')
    // Straight down, not the next in source order.
    expect(options()[3]).toHaveAttribute('aria-selected', 'true')

    await user.keyboard('{ArrowUp}')
    expect(options()[1]).toHaveAttribute('aria-selected', 'true')
  })

  it('skips a disabled swatch and refuses to select it', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn<(value: Color) => void>()
    render(
      <ColorSwatchPicker aria-label="Brand color" defaultValue="#ef4444" onValueChange={onValueChange}>
        <ColorSwatchPickerItem color="#ef4444" />
        <ColorSwatchPickerItem color="#f59e0b" disabled />
        <ColorSwatchPickerItem color="#22c55e" />
      </ColorSwatchPicker>,
    )

    expect(options()[1]).toBeDisabled()
    // The shared treatment: the swatch drops its color for the flat muted fill.
    expect(options()[1]!.querySelector('[data-slot=color-swatch]')).toHaveAttribute('data-disabled')
    expect(options()[1]!.querySelector<HTMLElement>('[data-slot=color-swatch]')!.style.backgroundColor).toBe('')
    await user.click(options()[1]!)
    expect(onValueChange).not.toHaveBeenCalled()

    options()[0]!.focus()
    await user.keyboard('{ArrowRight}')
    expect(options()[2]).toHaveAttribute('aria-selected', 'true')
  })

  it('disables every swatch from the root', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn<(value: Color) => void>()
    render(
      <ColorSwatchPicker aria-label="Brand color" disabled onValueChange={onValueChange}>
        {PALETTE.map((color) => (
          <ColorSwatchPickerItem key={color} color={color} />
        ))}
      </ColorSwatchPicker>,
    )
    expect(screen.getByRole('listbox')).toHaveAttribute('data-disabled')
    await user.click(options()[1]!)
    expect(onValueChange).not.toHaveBeenCalled()
  })

  it('sizes the swatch off the button, so the ring gap scales with it', () => {
    render(
      <ColorSwatchPicker aria-label="Brand color" size="lg">
        <ColorSwatchPickerItem color="#3b82f6" />
      </ColorSwatchPicker>,
    )
    expect(screen.getByRole('listbox')).toHaveClass('text-[3rem]')
    // The swatch's own preset has to lose to the 0.8em the item asks for, or the
    // gap between ring and swatch would be fixed instead of proportional.
    const swatch = document.querySelector('[data-slot=color-swatch]')!
    expect(swatch.className).toContain('text-[0.8em]')
    expect(swatch.className).not.toContain('text-[2.5rem]')
  })

  it('draws one indicator, not a border per swatch', () => {
    render(
      <ColorSwatchPicker aria-label="Brand color" defaultValue="#3b82f6">
        {PALETTE.map((color) => (
          <ColorSwatchPickerItem key={color} color={color} />
        ))}
      </ColorSwatchPicker>,
    )
    expect(document.querySelectorAll('[data-slot=color-swatch-picker-indicator]')).toHaveLength(1)
    expect(indicator()).toHaveAttribute('aria-hidden', 'true')
  })

  it('throws when an item is rendered outside a picker', () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<ColorSwatchPickerItem color="#3b82f6" />)).toThrow(/within <ColorSwatchPicker>/)
    error.mockRestore()
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <ColorSwatchPicker aria-label="Brand color" defaultValue="#3b82f6">
        {PALETTE.map((color) => (
          <ColorSwatchPickerItem key={color} color={color} />
        ))}
      </ColorSwatchPicker>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
