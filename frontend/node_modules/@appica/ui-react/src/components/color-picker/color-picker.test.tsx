import * as React from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeAll } from 'vitest'
import { axe } from 'vitest-axe'
import { ColorPicker, ColorPickerInput } from './color-picker'
import { ColorArea } from '../color-area/color-area'
import { ColorSlider } from '../color-slider/color-slider'
import { ColorSwatch } from '../color-swatch/color-swatch'
import { ColorSwatchPicker, ColorSwatchPickerItem } from '../color-swatch-picker/color-swatch-picker'
import { type Color, getChannelValue } from '../../lib/color'

beforeAll(() => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    },
  )
})

const trigger = () => screen.getByTestId('trigger')
const hexField = () => screen.getByRole('textbox', { name: 'Hex' }) as HTMLInputElement
const swatch = () => screen.getByRole('img')
const triggerSwatch = () => trigger().querySelector('[data-slot=color-swatch]') as HTMLElement

describe('ColorPicker', () => {
  it('renders a swatch trigger showing the color, and opens the default panel', async () => {
    const user = userEvent.setup()
    render(<ColorPicker data-testid="trigger" defaultValue="#3b82f6" />)

    expect(trigger()).toHaveTextContent('#3b82f6')
    expect(trigger()).toHaveAccessibleName(/vivid blue/)
    expect(screen.queryByRole('slider')).not.toBeInTheDocument()

    await user.click(trigger())
    expect(screen.getByRole('group', { name: 'Saturation and brightness' })).toBeInTheDocument()
    expect(screen.getByRole('slider', { name: 'Hue' })).toBeInTheDocument()
    expect(hexField()).toHaveValue('#3b82f6')
  })

  it('adds an alpha slider and keeps the opacity in the value', async () => {
    const user = userEvent.setup()
    render(<ColorPicker data-testid="trigger" alpha defaultValue="#3b82f680" />)

    await user.click(trigger())
    expect(screen.getByRole('slider', { name: 'Alpha' })).toBeInTheDocument()
    expect(hexField()).toHaveValue('#3b82f680')
  })

  it('drops the alpha digits from an opaque color', async () => {
    const user = userEvent.setup()
    const { container } = render(<ColorPicker data-testid="trigger" alpha name="brand" defaultValue="#3b82f6" />)

    expect(trigger()).toHaveTextContent('#3b82f6')
    expect(container.querySelector('input[type=hidden]')).toHaveValue('#3b82f6')

    await user.click(trigger())
    expect(hexField()).toHaveValue('#3b82f6')

    await user.clear(hexField())
    await user.type(hexField(), '#3b82f680')
    expect(hexField()).toHaveValue('#3b82f680')
  })

  it('places the trigger swatch on either side of the label', () => {
    const { rerender } = render(<ColorPicker data-testid="trigger" label="Fill" defaultValue="#3b82f6" />)
    expect(trigger().firstElementChild).toBe(triggerSwatch())

    rerender(<ColorPicker data-testid="trigger" label="Fill" swatchPosition="end" defaultValue="#3b82f6" />)
    expect(trigger().querySelector('span + [data-slot=color-swatch]')).toBe(triggerSwatch())
  })

  it('previews the color in the panel only when there is no trigger to do it', async () => {
    const user = userEvent.setup()
    const { unmount } = render(<ColorPicker data-testid="trigger" defaultValue="#3b82f6" />)
    await user.click(trigger())
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    unmount()

    render(<ColorPicker inline defaultValue="#3b82f6" />)
    expect(swatch()).toHaveAccessibleName('vivid blue')
  })

  it('renders a panel with no trigger of its own', () => {
    render(<ColorPicker trigger={null} open name="brand" defaultValue="#3b82f6" popoverProps={{ keepMounted: true }} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByRole('slider', { name: 'Hue' })).toBeInTheDocument()
    expect(document.querySelector('input[type=hidden]')).toHaveValue('#3b82f6')
  })

  it('takes the button shell off the trigger when flush', () => {
    const { rerender } = render(<ColorPicker data-testid="trigger" label="Fill" defaultValue="#3b82f6" />)
    expect(trigger().className).toMatch(/\bpx-5\b/)

    rerender(<ColorPicker data-testid="trigger" label="Fill" variant="flush" defaultValue="#3b82f6" />)
    expect(trigger().className).not.toMatch(/\bpx-5\b/)
    expect(trigger().className).toMatch(/\bp-0\b/)
    // Nothing to pull the swatch out of, so it keeps its own box.
    expect(triggerSwatch().className).not.toMatch(/-ms-/)
  })

  it('keeps the text input from deciding how wide the panel is', () => {
    render(<ColorPicker inline defaultValue="#3b82f6" />)
    // Without this an <input> asks for 20 characters, which beats the area in `w-fit`.
    expect(hexField()).toHaveAttribute('size', '1')
  })

  it('leaves alpha out by default', async () => {
    const user = userEvent.setup()
    render(<ColorPicker data-testid="trigger" />)

    await user.click(trigger())
    expect(screen.queryByRole('slider', { name: 'Alpha' })).not.toBeInTheDocument()
  })

  it('renders the panel in place, with no trigger, when inline', () => {
    render(<ColorPicker inline defaultValue="#3b82f6" />)
    expect(screen.queryByRole('button', { name: /blue/ })).not.toBeInTheDocument()
    expect(screen.getByRole('slider', { name: 'Hue' })).toBeInTheDocument()
  })

  it('replaces the panel with custom children', () => {
    render(
      <ColorPicker inline defaultValue="#3b82f6">
        <ColorSlider channel="hue" />
      </ColorPicker>,
    )
    expect(screen.getByRole('slider', { name: 'Hue' })).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Saturation and brightness' })).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('shares one color between the composed controls', async () => {
    const user = userEvent.setup()
    render(
      <ColorPicker inline defaultValue="#ff0000">
        <ColorSwatch />
        <ColorSlider channel="hue" />
        <ColorSwatchPicker aria-label="Presets">
          <ColorSwatchPickerItem color="#00ff00" />
        </ColorSwatchPicker>
      </ColorPicker>,
    )

    expect(swatch()).toHaveAccessibleName('vivid red')
    expect(screen.getByRole('slider', { name: 'Hue' })).toHaveValue('0')

    await user.click(screen.getByRole('option'))
    expect(swatch()).toHaveAccessibleName('vivid green')
    expect(screen.getByRole('slider', { name: 'Hue' })).toHaveValue('120')
  })

  it('lets a control keep its own value inside a picker', async () => {
    const user = userEvent.setup()
    render(
      <ColorPicker inline defaultValue="#ff0000">
        <ColorSwatch />
        <ColorSwatchPicker aria-label="Presets" value="#ff0000">
          <ColorSwatchPickerItem color="#00ff00" />
        </ColorSwatchPicker>
      </ColorPicker>,
    )

    await user.click(screen.getByRole('option'))
    // The palette stayed on its own controlled value; the picker still took the pick.
    expect(screen.getByRole('option')).toHaveAttribute('aria-selected', 'false')
    expect(swatch()).toHaveAccessibleName('vivid green')
  })

  it('reports every change, and commits once a gesture settles', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn<(value: Color) => void>()
    const onValueCommitted = vi.fn<(value: Color) => void>()
    render(
      <ColorPicker inline defaultValue="#ff0000" onValueChange={onValueChange} onValueCommitted={onValueCommitted}>
        <ColorSlider channel="hue" />
      </ColorPicker>,
    )

    screen.getByRole('slider', { name: 'Hue' }).focus()
    await user.keyboard('{ArrowRight}{ArrowRight}')
    expect(onValueChange).toHaveBeenCalledTimes(2)
    expect(onValueCommitted).toHaveBeenCalledTimes(2)
    expect(getChannelValue(onValueCommitted.mock.calls[1]![0], 'hue')).toBe(2)
  })

  it('holds a controlled value until the consumer updates it', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn<(value: Color) => void>()
    render(
      <ColorPicker inline value="#ff0000" onValueChange={onValueChange}>
        <ColorSwatch />
        <ColorSwatchPicker aria-label="Presets">
          <ColorSwatchPickerItem color="#00ff00" />
        </ColorSwatchPicker>
      </ColorPicker>,
    )

    await user.click(screen.getByRole('option'))
    expect(onValueChange).toHaveBeenCalledOnce()
    expect(swatch()).toHaveAccessibleName('vivid red')
  })

  it('dims the trigger and every control when disabled', async () => {
    const user = userEvent.setup()
    render(<ColorPicker data-testid="trigger" disabled defaultValue="#3b82f6" />)
    expect(trigger()).toBeDisabled()

    await user.click(trigger())
    expect(screen.queryByRole('slider')).not.toBeInTheDocument()
  })

  it('names a hidden input for form submission', () => {
    const { container } = render(<ColorPicker inline name="brand" alpha defaultValue="#3b82f680" />)
    expect(container.querySelector('input[type=hidden]')).toHaveValue('#3b82f680')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<ColorPicker inline eyedropper alpha defaultValue="#3b82f6" />)
    expect(await axe(container)).toHaveNoViolations()
  })

  it('has no accessibility violations with the panel open', async () => {
    const user = userEvent.setup()
    render(<ColorPicker data-testid="trigger" alpha aria-label="Fill color" defaultValue="#3b82f6" />)
    await user.click(trigger())
    expect(await axe(document.body)).toHaveNoViolations()
  })
})

describe('ColorPickerInput', () => {
  it('takes any color string the library can parse', async () => {
    const user = userEvent.setup()
    render(
      <ColorPicker inline defaultValue="#ff0000">
        <ColorSlider channel="hue" />
        <ColorPickerInput />
      </ColorPicker>,
    )

    await user.clear(hexField())
    await user.type(hexField(), 'rgb(0, 255, 0)')
    expect(screen.getByRole('slider', { name: 'Hue' })).toHaveValue('120')

    await user.tab()
    expect(hexField()).toHaveValue('#00ff00')
  })

  it('accepts hex digits without the hash', async () => {
    const user = userEvent.setup()
    render(<ColorPicker inline defaultValue="#ff0000" />)

    await user.clear(hexField())
    await user.type(hexField(), '00f{Enter}')
    expect(hexField()).toHaveValue('#0000ff')
  })

  it('restores the color when the text is left unparseable', async () => {
    const user = userEvent.setup()
    render(<ColorPicker inline defaultValue="#ff0000" />)

    await user.clear(hexField())
    await user.type(hexField(), 'not a color')
    expect(hexField()).toHaveValue('not a color')

    await user.tab()
    expect(hexField()).toHaveValue('#ff0000')
  })

  it('writes the format it is given', () => {
    render(
      <ColorPicker inline defaultValue="#ff0000">
        <ColorPickerInput format="hsl" />
      </ColorPicker>,
    )
    expect(screen.getByRole('textbox', { name: 'HSL' })).toHaveValue('hsl(0, 100%, 50%)')
  })

  it('refuses to render outside a picker', () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<ColorPickerInput />)).toThrow(/within <ColorPicker>/)
    error.mockRestore()
  })
})
