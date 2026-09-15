import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { axe } from 'vitest-axe'
import { Badge } from './badge'

describe('Badge', () => {
  it('renders as a span by default', () => {
    render(<Badge>New</Badge>)
    const el = screen.getByText('New')
    expect(el.tagName).toBe('SPAN')
    expect(el).toHaveAttribute('data-slot', 'badge')
  })

  it('renders as a different element via render prop', () => {
    render(<Badge render={<a href="/x" />}>Link badge</Badge>)
    const el = screen.getByRole('link', { name: 'Link badge' })
    expect(el.tagName).toBe('A')
    expect(el).toHaveAttribute('href', '/x')
  })

  it('forwards className alongside variant classes', () => {
    render(<Badge className="my-badge">Hi</Badge>)
    const el = screen.getByText('Hi')
    expect(el.className).toContain('my-badge')
    expect(el.className).toContain('bg-primary')
  })

  it('applies size and variant classes', () => {
    render(
      <Badge variant="error" size="lg">
        Err
      </Badge>,
    )
    const el = screen.getByText('Err')
    expect(el.className).toContain('bg-error-muted')
    expect(el.className).toContain('h-7')
  })

  it('exposes state to render callback', () => {
    render(
      <Badge
        variant="success"
        size="sm"
        render={(props, state) => <span {...props} data-test-variant={state.variant} data-test-size={state.size} />}
      >
        Done
      </Badge>,
    )
    const el = screen.getByText('Done')
    expect(el).toHaveAttribute('data-test-variant', 'success')
    expect(el).toHaveAttribute('data-test-size', 'sm')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<Badge>Accessible</Badge>)
    expect(await axe(container)).toHaveNoViolations()
  })
})
