import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { axe } from 'vitest-axe'
import { Spinner } from './spinner'

describe('Spinner', () => {
  it('exposes a status region with a default accessible name', () => {
    render(<Spinner />)
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Loading')
  })

  it('forwards a custom aria-label', () => {
    render(<Spinner aria-label="Fetching results" />)
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Fetching results')
  })

  it('renders the status region as a <span> so it nests inside <p> without invalid HTML', () => {
    render(<Spinner />)
    expect(screen.getByRole('status').tagName).toBe('SPAN')
  })

  it.each(['circular', 'dots', 'sparkle'] as const)('renders the %s variant without throwing', (variant) => {
    render(<Spinner variant={variant} />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('uses primary palette by default', () => {
    const { container } = render(<Spinner />)
    const svg = container.querySelector('svg')!
    expect(svg.getAttribute('class')).toContain('text-primary')
  })

  it('switches to currentColor when the prop is set', () => {
    const { container } = render(<Spinner currentColor />)
    const svg = container.querySelector('svg')!
    expect(svg.getAttribute('class')).toContain('text-current')
    expect(svg.getAttribute('class')).not.toContain('text-primary')
  })

  it('lets className override the default size via tailwind-merge', () => {
    render(<Spinner className="text-xl" />)
    const status = screen.getByRole('status')
    expect(status.className).toContain('text-xl')
    expect(status.className).not.toContain('text-[2.5rem]')
  })

  it('forwards arbitrary span props', () => {
    render(<Spinner data-testid="busy" id="spinner-1" />)
    const status = screen.getByTestId('busy')
    expect(status).toHaveAttribute('id', 'spinner-1')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<Spinner aria-label="Loading" />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
