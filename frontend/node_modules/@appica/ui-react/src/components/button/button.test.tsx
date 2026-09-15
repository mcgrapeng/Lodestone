import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { Button } from './button'

describe('Button', () => {
  it('renders as a button by default', () => {
    render(<Button>Click me</Button>)
    const el = screen.getByRole('button', { name: 'Click me' })
    expect(el.tagName).toBe('BUTTON')
    expect(el).toHaveAttribute('data-slot', 'button')
  })

  it('renders as a different element via render prop', () => {
    render(<Button render={<a href="/x" />}>Link button</Button>)
    const el = screen.getByRole('link', { name: 'Link button' })
    expect(el.tagName).toBe('A')
    expect(el).toHaveAttribute('href', '/x')
  })

  it('forwards className alongside variant classes', () => {
    render(<Button className="my-button">Hi</Button>)
    const el = screen.getByRole('button', { name: 'Hi' })
    expect(el.className).toContain('my-button')
    expect(el.className).toContain('bg-primary')
    expect(el.className).toContain('text-primary-foreground')
  })

  it('applies size and variant classes', () => {
    render(
      <Button variant="destructive" size="lg">
        Delete
      </Button>,
    )
    const el = screen.getByRole('button', { name: 'Delete' })
    expect(el.className).toContain('bg-error')
    expect(el.className).toContain('text-error-foreground')
    expect(el.className).toContain('h-12')
  })

  it('fires onClick when clicked', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Press</Button>)

    await user.click(screen.getByRole('button', { name: 'Press' }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('does not fire onClick when disabled', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(
      <Button disabled onClick={onClick}>
        Press
      </Button>,
    )

    await user.click(screen.getByRole('button', { name: 'Press' }))
    expect(onClick).not.toHaveBeenCalled()
  })

  it('activates on keyboard (Enter)', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Press</Button>)

    const btn = screen.getByRole('button', { name: 'Press' })
    btn.focus()
    await user.keyboard('{Enter}')
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<Button>Accessible</Button>)
    expect(await axe(container)).toHaveNoViolations()
  })
})
