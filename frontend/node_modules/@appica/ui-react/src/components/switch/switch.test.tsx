import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { Field as BaseField } from '@base-ui/react/field'
import { Switch } from './switch'

describe('Switch', () => {
  it('renders with switch role', () => {
    render(<Switch aria-label="Notifications" />)
    expect(screen.getByRole('switch', { name: 'Notifications' })).toBeInTheDocument()
  })

  it('reflects defaultChecked', () => {
    render(<Switch defaultChecked aria-label="On" />)
    expect(screen.getByRole('switch')).toBeChecked()
  })

  it('bridges aria-invalid to data-invalid for error styling', () => {
    render(<Switch aria-invalid aria-label="Invalid" />)
    const sw = screen.getByRole('switch')
    expect(sw).toHaveAttribute('aria-invalid', 'true')
    expect(sw).toHaveAttribute('data-invalid')
  })

  it('does not set data-invalid when valid', () => {
    render(<Switch aria-label="Valid" />)
    expect(screen.getByRole('switch')).not.toHaveAttribute('data-invalid')
  })

  it('keeps Field-context data-invalid when no standalone aria-invalid is set', () => {
    render(
      <BaseField.Root invalid>
        <Switch aria-label="Field switch" />
      </BaseField.Root>,
    )
    expect(screen.getByRole('switch')).toHaveAttribute('data-invalid')
  })

  it('toggles when clicked', async () => {
    const user = userEvent.setup()
    const onCheckedChange = vi.fn()
    render(<Switch aria-label="Toggle" onCheckedChange={onCheckedChange} />)

    const sw = screen.getByRole('switch')
    expect(sw).not.toBeChecked()

    await user.click(sw)
    expect(onCheckedChange).toHaveBeenCalledWith(true, expect.anything())
    expect(sw).toBeChecked()
  })

  it('toggles via keyboard (Space)', async () => {
    const user = userEvent.setup()
    const onCheckedChange = vi.fn()
    render(<Switch aria-label="Toggle" onCheckedChange={onCheckedChange} />)

    const sw = screen.getByRole('switch')
    sw.focus()
    await user.keyboard(' ')
    expect(onCheckedChange).toHaveBeenCalledOnce()
    expect(sw).toBeChecked()
  })

  it('does not toggle when disabled', async () => {
    const user = userEvent.setup()
    const onCheckedChange = vi.fn()
    render(<Switch disabled aria-label="Disabled" onCheckedChange={onCheckedChange} />)

    await user.click(screen.getByRole('switch'))
    expect(onCheckedChange).not.toHaveBeenCalled()
  })

  it('honors controlled checked prop', async () => {
    const user = userEvent.setup()
    const onCheckedChange = vi.fn()
    render(<Switch checked={false} aria-label="Controlled" onCheckedChange={onCheckedChange} />)

    const sw = screen.getByRole('switch')
    await user.click(sw)
    expect(onCheckedChange).toHaveBeenCalledWith(true, expect.anything())
    // Stays unchecked because parent never updates
    expect(sw).not.toBeChecked()
  })

  it('applies size styles to the root', () => {
    render(<Switch size="lg" aria-label="Large" />)
    expect(screen.getByRole('switch').className).toContain('h-6')
  })

  it('forwards className to the root', () => {
    render(<Switch className="custom-class" aria-label="Styled" />)
    expect(screen.getByRole('switch').className).toContain('custom-class')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<Switch aria-label="Notifications" />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
