import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'vitest-axe'
import * as React from 'react'
import { Textarea } from './textarea'
import { Field, FieldLabel } from '../field/field'

describe('Textarea', () => {
  it('associates with a Field label (matching for/id, like Input)', () => {
    render(
      <Field>
        <FieldLabel>Bio</FieldLabel>
        <Textarea />
      </Field>,
    )
    // getByLabelText only resolves when the label's `for` matches the control id.
    const textarea = screen.getByLabelText('Bio')
    expect(textarea.tagName).toBe('TEXTAREA')
    expect(textarea.id).not.toBe('')
  })

  it('associates with a Field label when wrapped (slots/clearable)', () => {
    render(
      <Field>
        <FieldLabel>Notes</FieldLabel>
        <Textarea clearable />
      </Field>,
    )
    expect(screen.getByLabelText('Notes').tagName).toBe('TEXTAREA')
  })

  it('renders with textbox role', () => {
    render(<Textarea aria-label="Bio" />)
    expect(screen.getByRole('textbox', { name: 'Bio' })).toBeInTheDocument()
  })

  it('accepts user typing across multiple lines', async () => {
    const user = userEvent.setup()
    render(<Textarea aria-label="Notes" />)
    const textarea = screen.getByRole('textbox')
    await user.type(textarea, 'line one{enter}line two')
    expect(textarea).toHaveValue('line one\nline two')
  })

  it('calls onChange when typing in a controlled textarea', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    function Controlled() {
      const [value, setValue] = React.useState('')
      return (
        <Textarea
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
    render(<Textarea aria-label="Disabled" disabled />)
    const textarea = screen.getByRole('textbox')
    expect(textarea).toBeDisabled()
    await user.type(textarea, 'x')
    expect(textarea).toHaveValue('')
  })

  it('applies size padding-y classes', () => {
    render(<Textarea aria-label="Large" inputSize="lg" />)
    expect(screen.getByRole('textbox').className).toContain('py-3')
  })

  it('applies variant classes', () => {
    render(<Textarea aria-label="Soft" variant="soft" />)
    expect(screen.getByRole('textbox').className).toContain('bg-background-muted')
  })

  it('overrides h-X from inputVariants so rows controls height', () => {
    render(<Textarea aria-label="Rows" rows={5} />)
    const textarea = screen.getByRole('textbox')
    expect(textarea).toHaveAttribute('rows', '5')
    expect(textarea.className).toContain('h-auto')
    expect(textarea.className).not.toMatch(/(?:^|\s)h-(?:8|10|12)(?:\s|$)/)
  })

  it('enforces a per-size min-height floor on the textarea', () => {
    render(<Textarea aria-label="Min height" inputSize="md" />)
    expect(screen.getByRole('textbox').className).toContain('min-h-20')
  })

  it('wrapper owns the resize handle and seeds height from rows', () => {
    render(<Textarea aria-label="Wrapped" rows={6} startSlot={<span data-testid="s">@</span>} />)
    const wrapper = screen.getByTestId('s').closest('[data-slot="textarea-wrapper"]') as HTMLElement
    expect(wrapper.className).toContain('resize-y')
    expect(wrapper.className).toContain('h-(--textarea-h)')
    expect(wrapper.className).toContain('min-h-20')
    expect(wrapper.className).not.toMatch(/(?:^|\s)h-(?:8|10|12)(?:\s|$)/)
    expect(wrapper.style.getPropertyValue('--textarea-h')).toBe('calc(6 * 1lh + 2 * 0.625rem + 2px)')

    const textarea = screen.getByRole('textbox')
    expect(textarea.className).toContain('resize-none')
    expect(textarea.className).toContain('self-stretch')
  })

  it('bare disabled textarea carries data-disabled so it picks up data-disabled: classes from inputVariants', () => {
    render(<Textarea aria-label="Disabled style" disabled />)
    const textarea = screen.getByRole('textbox')
    expect(textarea).toHaveAttribute('data-disabled')
    expect(textarea.className).toContain('data-disabled:border-dashed')
  })

  it('bare textarea omits data-disabled when not disabled', () => {
    render(<Textarea aria-label="Enabled" />)
    expect(screen.getByRole('textbox')).not.toHaveAttribute('data-disabled')
  })

  it('bridges aria-invalid to data-invalid on the bare textarea', () => {
    render(<Textarea aria-label="Notes" aria-invalid />)
    const textarea = screen.getByRole('textbox')
    expect(textarea).toHaveAttribute('aria-invalid', 'true')
    expect(textarea).toHaveAttribute('data-invalid')
  })

  it('bridges aria-invalid to data-invalid on the wrapper when slots are present', () => {
    const { container } = render(<Textarea aria-label="Notes" aria-invalid endSlot={<span>@</span>} />)
    expect(container.querySelector('[data-slot="textarea-wrapper"]')).toHaveAttribute('data-invalid')
  })

  it('bare textarea omits data-invalid when valid', () => {
    render(<Textarea aria-label="Enabled" />)
    expect(screen.getByRole('textbox')).not.toHaveAttribute('data-invalid')
  })

  it('forwards an outer ref', () => {
    const ref = React.createRef<HTMLTextAreaElement>()
    render(<Textarea aria-label="Ref" ref={ref} />)
    expect(ref.current).toBeInstanceOf(HTMLTextAreaElement)
  })

  it('renders the clear button when clearable and clears the value', async () => {
    const user = userEvent.setup()
    const onClear = vi.fn()
    render(<Textarea aria-label="Notes" clearable onClear={onClear} />)

    const textarea = screen.getByRole('textbox')
    await user.type(textarea, 'hello')
    expect(textarea).toHaveValue('hello')

    await user.click(screen.getByRole('button', { name: 'Clear input' }))
    expect(textarea).toHaveValue('')
    expect(onClear).toHaveBeenCalledOnce()
  })

  it('renders startSlot and endSlot when provided', () => {
    render(
      <Textarea
        aria-label="With slots"
        startSlot={<span data-testid="start">@</span>}
        endSlot={<span data-testid="end">md</span>}
      />,
    )
    expect(screen.getByTestId('start')).toBeInTheDocument()
    expect(screen.getByTestId('end')).toBeInTheDocument()
  })

  it('aligns slots to the top with line-height matched wrapper', () => {
    render(<Textarea aria-label="Slot align" startSlot={<span data-testid="start">@</span>} />)
    const startWrapper = screen.getByTestId('start').parentElement
    expect(startWrapper?.className).toContain('h-lh')
    expect(startWrapper?.className).toContain('items-center')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<Textarea aria-label="Bio" />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
