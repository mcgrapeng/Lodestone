import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { Field as BaseField } from '@base-ui/react/field'
import { Checkbox } from './checkbox'

describe('Checkbox', () => {
  it('renders with checkbox role', () => {
    render(<Checkbox aria-label="Subscribe" />)
    expect(screen.getByRole('checkbox', { name: 'Subscribe' })).toBeInTheDocument()
  })

  it('reflects defaultChecked', () => {
    render(<Checkbox defaultChecked aria-label="Default on" />)
    expect(screen.getByRole('checkbox')).toBeChecked()
  })

  it('bridges aria-invalid to data-invalid for error styling', () => {
    render(<Checkbox aria-invalid aria-label="Invalid" />)
    const cb = screen.getByRole('checkbox')
    expect(cb).toHaveAttribute('aria-invalid', 'true')
    expect(cb).toHaveAttribute('data-invalid')
  })

  it('does not set data-invalid when valid', () => {
    render(<Checkbox aria-label="Valid" />)
    expect(screen.getByRole('checkbox')).not.toHaveAttribute('data-invalid')
  })

  it('keeps Field-context data-invalid when no standalone aria-invalid is set', () => {
    render(
      <BaseField.Root invalid>
        <Checkbox aria-label="Field checkbox" />
      </BaseField.Root>,
    )
    expect(screen.getByRole('checkbox')).toHaveAttribute('data-invalid')
  })

  it('toggles when clicked', async () => {
    const user = userEvent.setup()
    const onCheckedChange = vi.fn()
    render(<Checkbox aria-label="Toggle" onCheckedChange={onCheckedChange} />)

    const cb = screen.getByRole('checkbox')
    expect(cb).not.toBeChecked()

    await user.click(cb)
    expect(onCheckedChange).toHaveBeenCalledWith(true, expect.anything())
    expect(cb).toBeChecked()
  })

  it('toggles via Space key', async () => {
    const user = userEvent.setup()
    const onCheckedChange = vi.fn()
    render(<Checkbox aria-label="Toggle" onCheckedChange={onCheckedChange} />)

    const cb = screen.getByRole('checkbox')
    cb.focus()
    await user.keyboard(' ')
    expect(onCheckedChange).toHaveBeenCalledOnce()
    expect(cb).toBeChecked()
  })

  it('does not toggle when disabled', async () => {
    const user = userEvent.setup()
    const onCheckedChange = vi.fn()
    render(<Checkbox disabled aria-label="Disabled" onCheckedChange={onCheckedChange} />)

    await user.click(screen.getByRole('checkbox'))
    expect(onCheckedChange).not.toHaveBeenCalled()
  })

  it('honors indeterminate prop', () => {
    render(<Checkbox indeterminate aria-label="Mixed" />)
    const cb = screen.getByRole('checkbox')
    expect(cb).toHaveAttribute('aria-checked', 'mixed')
  })

  it('honors controlled checked prop', async () => {
    const user = userEvent.setup()
    const onCheckedChange = vi.fn()
    render(<Checkbox checked={false} aria-label="Controlled" onCheckedChange={onCheckedChange} />)

    const cb = screen.getByRole('checkbox')
    await user.click(cb)
    expect(onCheckedChange).toHaveBeenCalledWith(true, expect.anything())
    expect(cb).not.toBeChecked()
  })

  it('forwards className to the root', () => {
    render(<Checkbox className="custom-class" aria-label="Styled" />)
    expect(screen.getByRole('checkbox').className).toContain('custom-class')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<Checkbox aria-label="Subscribe" />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
