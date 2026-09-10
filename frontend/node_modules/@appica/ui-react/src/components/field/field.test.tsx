import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { axe } from 'vitest-axe'
import { Field as BaseField } from '@base-ui/react/field'
import { Field, FieldLabel, FieldDescription, FieldError, FieldValidity } from './field'

describe('Field', () => {
  it('renders label associated with the control', () => {
    render(
      <Field>
        <FieldLabel>Email</FieldLabel>
        <BaseField.Control type="email" defaultValue="" />
      </Field>,
    )

    expect(screen.getByLabelText('Email')).toBeInTheDocument()
  })

  it('renders a description that describes the control', () => {
    render(
      <Field>
        <FieldLabel>Email</FieldLabel>
        <BaseField.Control type="email" defaultValue="" />
        <FieldDescription>We never share your email.</FieldDescription>
      </Field>,
    )

    const control = screen.getByLabelText('Email')
    const description = screen.getByText('We never share your email.')
    expect(control).toHaveAttribute('aria-describedby', expect.stringContaining(description.id))
  })

  it('shows an error message when the field is invalid', () => {
    render(
      <Field invalid>
        <FieldLabel>Email</FieldLabel>
        <BaseField.Control type="email" defaultValue="" />
        <FieldError match>Email is required</FieldError>
      </Field>,
    )

    expect(screen.getByText('Email is required')).toBeInTheDocument()
  })

  it('exposes validity state via FieldValidity render prop', () => {
    render(
      <Field invalid>
        <FieldLabel>Email</FieldLabel>
        <BaseField.Control type="email" defaultValue="" />
        <FieldValidity>{(state) => <span data-testid="valid">{String(state.validity.valid)}</span>}</FieldValidity>
      </Field>,
    )

    expect(screen.getByTestId('valid')).toBeInTheDocument()
  })

  it('forwards className to each sub-component', () => {
    render(
      <Field className="root-x">
        <FieldLabel className="label-x">Email</FieldLabel>
        <BaseField.Control type="email" defaultValue="" />
        <FieldDescription className="desc-x">Hint</FieldDescription>
        <FieldError className="err-x" match>
          Bad
        </FieldError>
      </Field>,
    )

    expect(screen.getByText('Email').className).toContain('label-x')
    expect(screen.getByText('Hint').className).toContain('desc-x')
    expect(screen.getByText('Bad').className).toContain('err-x')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <Field>
        <FieldLabel>Email</FieldLabel>
        <BaseField.Control type="email" defaultValue="" />
        <FieldDescription>We never share your email.</FieldDescription>
      </Field>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
