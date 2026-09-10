import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { axe } from 'vitest-axe'
import { Separator } from './separator'

describe('Separator', () => {
  it('renders with separator role', () => {
    render(<Separator />)
    expect(screen.getByRole('separator')).toBeInTheDocument()
  })

  it('is horizontal by default', () => {
    render(<Separator />)
    expect(screen.getByRole('separator')).toHaveAttribute('aria-orientation', 'horizontal')
  })

  it('renders as vertical when orientation is set', () => {
    render(<Separator orientation="vertical" />)
    expect(screen.getByRole('separator')).toHaveAttribute('aria-orientation', 'vertical')
  })

  it('forwards className to the root', () => {
    render(<Separator className="my-separator" />)
    expect(screen.getByRole('separator').className).toContain('my-separator')
  })

  const variants = ['solid', 'dashed', 'dotted', 'double', 'gradient', 'wave', 'zigzag'] as const

  it.each(variants)('renders the %s variant in both orientations', (variant) => {
    const { rerender } = render(<Separator variant={variant} />)
    expect(screen.getByRole('separator')).toHaveAttribute('aria-orientation', 'horizontal')

    rerender(<Separator variant={variant} orientation="vertical" />)
    expect(screen.getByRole('separator')).toHaveAttribute('aria-orientation', 'vertical')
  })

  it('forwards a consumer style on a decorative variant', () => {
    render(<Separator variant="wave" style={{ opacity: 0.5 }} />)
    expect(screen.getByRole('separator')).toHaveStyle({ opacity: '0.5' })
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<Separator />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
