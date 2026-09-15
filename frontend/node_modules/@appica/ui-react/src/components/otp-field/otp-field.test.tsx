import * as React from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { OTPField, OTPFieldInput, OTPFieldSeparator } from './otp-field'

const LENGTH = 4

function renderField(props: Partial<React.ComponentProps<typeof OTPField>> = {}) {
  return render(
    <OTPField length={LENGTH} aria-label="Verification code" {...props}>
      {Array.from({ length: LENGTH }, (_, index) => (
        <OTPFieldInput key={index} aria-label={`Character ${index + 1} of ${LENGTH}`} />
      ))}
    </OTPField>,
  )
}

describe('OTPField', () => {
  it('renders the requested number of input slots', () => {
    renderField()
    expect(screen.getAllByRole('textbox')).toHaveLength(LENGTH)
  })

  it('accepts user typing across slots and updates the value', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn()
    renderField({ onValueChange })

    screen.getAllByRole('textbox')[0]!.focus()
    await user.keyboard('1234')

    expect(onValueChange).toHaveBeenLastCalledWith('1234', expect.objectContaining({ reason: expect.any(String) }))
  })

  it('fires onValueComplete when all slots are filled', async () => {
    const user = userEvent.setup()
    const onValueComplete = vi.fn()
    renderField({ onValueComplete })

    screen.getAllByRole('textbox')[0]!.focus()
    await user.keyboard('9876')

    expect(onValueComplete).toHaveBeenCalledWith('9876', expect.any(Object))
  })

  it('disables every slot when disabled', () => {
    renderField({ disabled: true })
    for (const input of screen.getAllByRole('textbox')) {
      expect(input).toBeDisabled()
    }
  })

  it('applies the size class to inputs', () => {
    renderField({ size: 'lg' })
    const first = screen.getAllByRole('textbox')[0]!
    expect(first.className).toContain('h-12')
    expect(first.className).toContain('w-12')
  })

  it('applies the variant class to inputs', () => {
    renderField({ variant: 'soft' })
    expect(screen.getAllByRole('textbox')[0]!.className).toContain('bg-background-muted')
  })

  it('bridges a standalone aria-invalid to data-invalid on the input', () => {
    render(
      <OTPField>
        <OTPFieldInput aria-label="Character 1 of 1" aria-invalid />
      </OTPField>,
    )
    const input = screen.getAllByRole('textbox')[0]!
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAttribute('data-invalid')
  })

  it('does not set data-invalid when valid', () => {
    render(
      <OTPField>
        <OTPFieldInput aria-label="Character 1 of 1" />
      </OTPField>,
    )
    expect(screen.getAllByRole('textbox')[0]!).not.toHaveAttribute('data-invalid')
  })

  it('renders a separator between groups', () => {
    render(
      <OTPField length={4} aria-label="Code">
        <OTPFieldInput aria-label="Character 1 of 4" />
        <OTPFieldInput aria-label="Character 2 of 4" />
        <OTPFieldSeparator data-testid="separator" />
        <OTPFieldInput aria-label="Character 3 of 4" />
        <OTPFieldInput aria-label="Character 4 of 4" />
      </OTPField>,
    )
    expect(screen.getByTestId('separator')).toBeInTheDocument()
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <>
        <label htmlFor="otp">Verification code</label>
        <OTPField id="otp" length={LENGTH}>
          {Array.from({ length: LENGTH }, (_, index) => (
            <OTPFieldInput key={index} aria-label={`Character ${index + 1} of ${LENGTH}`} />
          ))}
        </OTPField>
      </>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
