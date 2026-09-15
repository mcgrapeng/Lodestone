import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { axe } from 'vitest-axe'
import { Field as BaseField } from '@base-ui/react/field'
import { Fieldset, FieldsetLegend } from './fieldset'
import { Field, FieldLabel } from '../field/field'

describe('Fieldset', () => {
  it('renders a fieldset with an associated legend', () => {
    render(
      <Fieldset>
        <FieldsetLegend>Account</FieldsetLegend>
        <Field>
          <FieldLabel>Email</FieldLabel>
          <BaseField.Control type="email" defaultValue="" />
        </Field>
      </Fieldset>,
    )

    const group = screen.getByRole('group', { name: 'Account' })
    expect(group.tagName).toBe('FIELDSET')
  })

  it('forwards className to the root and legend', () => {
    render(
      <Fieldset className="root-x">
        <FieldsetLegend className="legend-x">Account</FieldsetLegend>
      </Fieldset>,
    )

    const legend = screen.getByText('Account')
    expect(legend.className).toContain('legend-x')
    expect(screen.getByRole('group').className).toContain('root-x')
  })

  it('disables descendant controls when disabled', () => {
    render(
      <Fieldset disabled>
        <FieldsetLegend>Account</FieldsetLegend>
        <Field>
          <FieldLabel>Email</FieldLabel>
          <BaseField.Control type="email" defaultValue="" />
        </Field>
      </Fieldset>,
    )

    expect(screen.getByLabelText('Email')).toBeDisabled()
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <Fieldset>
        <FieldsetLegend>Account</FieldsetLegend>
        <Field>
          <FieldLabel>Email</FieldLabel>
          <BaseField.Control type="email" defaultValue="" />
        </Field>
      </Fieldset>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
