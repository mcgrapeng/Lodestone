import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'vitest-axe'
import * as React from 'react'
import { Input } from './input'

describe('Input', () => {
  it('renders with textbox role', () => {
    render(<Input aria-label="Email" />)
    expect(screen.getByRole('textbox', { name: 'Email' })).toBeInTheDocument()
  })

  it('accepts user typing', async () => {
    const user = userEvent.setup()
    render(<Input aria-label="Name" />)
    const input = screen.getByRole('textbox')
    await user.type(input, 'Roman')
    expect(input).toHaveValue('Roman')
  })

  it('calls onChange when typing in a controlled input', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    function Controlled() {
      const [value, setValue] = React.useState('')
      return (
        <Input
          aria-label="Controlled"
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            onChange(e.target.value)
          }}
        />
      )
    }

    render(<Controlled />)
    await user.type(screen.getByRole('textbox'), 'hi')
    expect(onChange).toHaveBeenCalledWith('hi')
    expect(screen.getByRole('textbox')).toHaveValue('hi')
  })

  it('is disabled when the disabled prop is set', async () => {
    const user = userEvent.setup()
    render(<Input aria-label="Disabled" disabled />)
    const input = screen.getByRole('textbox')
    expect(input).toBeDisabled()
    await user.type(input, 'x')
    expect(input).toHaveValue('')
  })

  it('applies size classes', () => {
    render(<Input aria-label="Large" inputSize="lg" />)
    expect(screen.getByRole('textbox').className).toContain('h-12')
  })

  it('applies variant classes', () => {
    render(<Input aria-label="Soft" variant="soft" />)
    expect(screen.getByRole('textbox').className).toContain('bg-background-muted')
  })

  it('forwards an outer ref', () => {
    const ref = React.createRef<HTMLInputElement>()
    render(<Input aria-label="Ref" ref={ref} />)
    expect(ref.current).toBeInstanceOf(HTMLInputElement)
  })

  it('renders the clear button when clearable and clears the value', async () => {
    const user = userEvent.setup()
    const onClear = vi.fn()
    render(<Input aria-label="Search" clearable onClear={onClear} />)

    const input = screen.getByRole('textbox')
    await user.type(input, 'query')
    expect(input).toHaveValue('query')

    await user.click(screen.getByRole('button', { name: 'Clear input' }))
    expect(input).toHaveValue('')
    expect(onClear).toHaveBeenCalledOnce()
  })

  it('renders startSlot and endSlot when provided', () => {
    render(
      <Input
        aria-label="With slots"
        startSlot={<span data-testid="start">$</span>}
        endSlot={<span data-testid="end">USD</span>}
      />,
    )
    expect(screen.getByTestId('start')).toBeInTheDocument()
    expect(screen.getByTestId('end')).toBeInTheDocument()
  })

  it('bridges aria-invalid to data-invalid on the bare input', () => {
    const { container } = render(<Input aria-label="Email" aria-invalid />)
    const input = container.querySelector('[data-slot="input"]')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAttribute('data-invalid')
  })

  it('bridges aria-invalid to data-invalid on the wrapper when slots are present', () => {
    const { container } = render(<Input aria-label="Email" aria-invalid endSlot={<span>@</span>} />)
    expect(container.querySelector('[data-slot="input-wrapper"]')).toHaveAttribute('data-invalid')
  })

  it('does not set data-invalid when valid', () => {
    const { container } = render(<Input aria-label="Email" />)
    expect(container.querySelector('[data-slot="input"]')).not.toHaveAttribute('data-invalid')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<Input aria-label="Email" />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
