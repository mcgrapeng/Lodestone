import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { RadioGroup } from '@base-ui/react/radio-group'
import { Field as BaseField } from '@base-ui/react/field'
import { Radio } from './radio'

function Group({ children, ...props }: React.ComponentProps<typeof RadioGroup>) {
  return <RadioGroup {...props}>{children}</RadioGroup>
}

describe('Radio', () => {
  it('renders with radio role', () => {
    render(
      <Group>
        <Radio value="a" aria-label="Option A" />
      </Group>,
    )
    expect(screen.getByRole('radio', { name: 'Option A' })).toBeInTheDocument()
  })

  it('reflects defaultValue from the group', () => {
    render(
      <Group defaultValue="b">
        <Radio value="a" aria-label="Option A" />
        <Radio value="b" aria-label="Option B" />
      </Group>,
    )
    expect(screen.getByRole('radio', { name: 'Option A' })).not.toBeChecked()
    expect(screen.getByRole('radio', { name: 'Option B' })).toBeChecked()
  })

  it('bridges aria-invalid to data-invalid for error styling', () => {
    render(
      <Group>
        <Radio value="a" aria-invalid aria-label="Invalid" />
      </Group>,
    )
    const radio = screen.getByRole('radio', { name: 'Invalid' })
    expect(radio).toHaveAttribute('aria-invalid', 'true')
    expect(radio).toHaveAttribute('data-invalid')
  })

  it('does not set data-invalid when valid', () => {
    render(
      <Group>
        <Radio value="a" aria-label="Valid" />
      </Group>,
    )
    expect(screen.getByRole('radio', { name: 'Valid' })).not.toHaveAttribute('data-invalid')
  })

  it('keeps Field-context data-invalid when no standalone aria-invalid is set', () => {
    render(
      <BaseField.Root invalid>
        <Group>
          <Radio value="a" aria-label="Field radio" />
        </Group>
      </BaseField.Root>,
    )
    expect(screen.getByRole('radio', { name: 'Field radio' })).toHaveAttribute('data-invalid')
  })

  it('selects when clicked', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn()
    render(
      <Group onValueChange={onValueChange}>
        <Radio value="a" aria-label="Option A" />
        <Radio value="b" aria-label="Option B" />
      </Group>,
    )

    await user.click(screen.getByRole('radio', { name: 'Option B' }))
    expect(onValueChange).toHaveBeenCalledWith('b', expect.anything())
    expect(screen.getByRole('radio', { name: 'Option B' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Option A' })).not.toBeChecked()
  })

  it('moves selection with ArrowDown (composite roving focus)', async () => {
    const user = userEvent.setup()
    render(
      <Group defaultValue="a">
        <Radio value="a" aria-label="Option A" />
        <Radio value="b" aria-label="Option B" />
      </Group>,
    )
    screen.getByRole('radio', { name: 'Option A' }).focus()
    await user.keyboard('{ArrowDown}')
    expect(screen.getByRole('radio', { name: 'Option B' })).toBeChecked()
  })

  it('does not select when disabled', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn()
    render(
      <Group onValueChange={onValueChange}>
        <Radio value="a" aria-label="Option A" disabled />
      </Group>,
    )

    await user.click(screen.getByRole('radio', { name: 'Option A' }))
    expect(onValueChange).not.toHaveBeenCalled()
  })

  it('honors controlled value', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn()
    render(
      <Group value="a" onValueChange={onValueChange}>
        <Radio value="a" aria-label="Option A" />
        <Radio value="b" aria-label="Option B" />
      </Group>,
    )

    await user.click(screen.getByRole('radio', { name: 'Option B' }))
    expect(onValueChange).toHaveBeenCalledWith('b', expect.anything())
    // Value is controlled; without parent updating, A stays selected.
    expect(screen.getByRole('radio', { name: 'Option A' })).toBeChecked()
  })

  it('forwards className to the root', () => {
    render(
      <Group>
        <Radio value="a" className="custom-class" aria-label="Styled" />
      </Group>,
    )
    expect(screen.getByRole('radio').className).toContain('custom-class')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <Group>
        <Radio value="a" aria-label="Option A" />
        <Radio value="b" aria-label="Option B" />
      </Group>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
