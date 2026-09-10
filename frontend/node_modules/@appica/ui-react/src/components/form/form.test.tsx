import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { Field as BaseField } from '@base-ui/react/field'
import { Form } from './form'
import { Field, FieldLabel, FieldError } from '../field/field'

describe('Form', () => {
  it('renders a native form element', () => {
    render(
      <Form aria-label="signup">
        <Field>
          <FieldLabel>Email</FieldLabel>
          <BaseField.Control type="email" defaultValue="" />
        </Field>
      </Form>,
    )

    const form = screen.getByRole('form', { name: 'signup' })
    expect(form.tagName).toBe('FORM')
  })

  it('forwards onSubmit', async () => {
    const onSubmit = vi.fn((event: React.FormEvent<HTMLFormElement>) => event.preventDefault())
    render(
      <Form onSubmit={onSubmit}>
        <button type="submit">Submit</button>
      </Form>,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Submit' }))
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it('renders server errors via the errors prop', () => {
    render(
      <Form errors={{ email: 'Email already in use' }}>
        <Field name="email">
          <FieldLabel>Email</FieldLabel>
          <BaseField.Control type="email" defaultValue="" />
          <FieldError />
        </Field>
      </Form>,
    )

    expect(screen.getByText('Email already in use')).toBeInTheDocument()
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <Form aria-label="signup">
        <Field>
          <FieldLabel>Email</FieldLabel>
          <BaseField.Control type="email" defaultValue="" />
        </Field>
      </Form>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
