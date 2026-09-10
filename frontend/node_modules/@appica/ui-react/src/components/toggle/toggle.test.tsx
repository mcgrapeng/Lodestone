import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { Toggle } from './toggle'
import { Button } from '../button/button'

describe('Toggle', () => {
  it('renders as a button', () => {
    render(<Toggle aria-label="Bold">B</Toggle>)
    const el = screen.getByRole('button', { name: 'Bold' })
    expect(el.tagName).toBe('BUTTON')
    expect(el).toHaveAttribute('aria-pressed', 'false')
  })

  it('composes with Button via render and propagates data-pressed', async () => {
    const user = userEvent.setup()
    render(<Toggle aria-label="Bold" render={<Button variant="primary">Bold</Button>} />)
    const btn = screen.getByRole('button', { name: 'Bold' })
    expect(btn.className).toContain('bg-primary')
    expect(btn).toHaveAttribute('aria-pressed', 'false')

    await user.click(btn)
    expect(btn).toHaveAttribute('aria-pressed', 'true')
    expect(btn).toHaveAttribute('data-pressed')
  })

  it('reflects defaultPressed', () => {
    render(
      <Toggle defaultPressed aria-label="Bold">
        B
      </Toggle>,
    )
    expect(screen.getByRole('button', { name: 'Bold' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('toggles when clicked', async () => {
    const user = userEvent.setup()
    const onPressedChange = vi.fn()
    render(
      <Toggle aria-label="Bold" onPressedChange={onPressedChange}>
        B
      </Toggle>,
    )

    const btn = screen.getByRole('button', { name: 'Bold' })
    await user.click(btn)
    expect(onPressedChange).toHaveBeenCalledWith(true, expect.anything())
    expect(btn).toHaveAttribute('aria-pressed', 'true')
  })

  it('toggles via keyboard (Space)', async () => {
    const user = userEvent.setup()
    const onPressedChange = vi.fn()
    render(
      <Toggle aria-label="Bold" onPressedChange={onPressedChange}>
        B
      </Toggle>,
    )

    const btn = screen.getByRole('button', { name: 'Bold' })
    btn.focus()
    await user.keyboard(' ')
    expect(onPressedChange).toHaveBeenCalledOnce()
    expect(btn).toHaveAttribute('aria-pressed', 'true')
  })

  it('does not toggle when disabled', async () => {
    const user = userEvent.setup()
    const onPressedChange = vi.fn()
    render(
      <Toggle disabled aria-label="Bold" onPressedChange={onPressedChange}>
        B
      </Toggle>,
    )

    await user.click(screen.getByRole('button', { name: 'Bold' }))
    expect(onPressedChange).not.toHaveBeenCalled()
  })

  it('honors controlled pressed prop', async () => {
    const user = userEvent.setup()
    const onPressedChange = vi.fn()
    render(
      <Toggle pressed={false} aria-label="Bold" onPressedChange={onPressedChange}>
        B
      </Toggle>,
    )

    const btn = screen.getByRole('button', { name: 'Bold' })
    await user.click(btn)
    expect(onPressedChange).toHaveBeenCalledWith(true, expect.anything())
    expect(btn).toHaveAttribute('aria-pressed', 'false')
  })

  it('forwards className', () => {
    render(
      <Toggle className="custom-class" aria-label="Bold">
        B
      </Toggle>,
    )
    expect(screen.getByRole('button', { name: 'Bold' }).className).toContain('custom-class')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<Toggle aria-label="Bold">B</Toggle>)
    expect(await axe(container)).toHaveNoViolations()
  })
})
