import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { axe } from 'vitest-axe'
import { Progress, ProgressLabel, ProgressValue } from './progress'

describe('Progress', () => {
  it('renders bar variant by default with role and value', () => {
    render(<Progress value={40} />)
    const el = screen.getByRole('progressbar')
    expect(el).toHaveAttribute('data-slot', 'progress')
    expect(el).toHaveAttribute('data-variant', 'bar')
    expect(el).toHaveAttribute('aria-valuenow', '40')
    expect(el).toHaveAttribute('aria-valuemin', '0')
    expect(el).toHaveAttribute('aria-valuemax', '100')
  })

  it('renders bar Track and Indicator with width applied by Base UI', () => {
    const { container } = render(<Progress value={50} />)
    const track = container.querySelector('[data-slot=progress-track]') as HTMLElement
    const indicator = container.querySelector('[data-slot=progress-indicator]') as HTMLElement
    expect(track).toBeInTheDocument()
    expect(indicator).toBeInTheDocument()
    expect(indicator.style.width).toBe('50%')
  })

  it('applies thickness to bar track height', () => {
    const { container } = render(<Progress value={20} thickness={10} />)
    const track = container.querySelector('[data-slot=progress-track]') as HTMLElement
    expect(track.style.height).toBe('10px')
  })

  it('renders circular variant with an SVG', () => {
    const { container } = render(<Progress value={75} variant="circular" />)
    const root = screen.getByRole('progressbar')
    expect(root).toHaveAttribute('data-variant', 'circular')
    const svg = container.querySelector('svg[data-slot=progress-circular]') as SVGElement
    expect(svg).toBeInTheDocument()
    expect(svg.getAttribute('width')).toBe('56')
    expect(svg.getAttribute('height')).toBe('56')
  })

  it('respects size and thickness on circular variant', () => {
    const { container } = render(<Progress value={50} variant="circular" size={80} thickness={6} />)
    const svg = container.querySelector('svg[data-slot=progress-circular]') as SVGElement
    expect(svg.getAttribute('width')).toBe('80')
    const indicator = container.querySelector('svg [data-slot=progress-indicator]') as SVGCircleElement
    expect(indicator.getAttribute('stroke-width')).toBe('6')
  })

  it('passes indicatorColor through via the --progress-color CSS variable', () => {
    render(<Progress value={50} indicatorColor="oklch(0.7 0.2 30)" />)
    const root = screen.getByRole('progressbar')
    expect(root.style.getPropertyValue('--progress-color')).toBe('oklch(0.7 0.2 30)')
  })

  it('links ProgressLabel to the root via aria-labelledby', () => {
    render(
      <Progress value={10}>
        <ProgressLabel>Uploading</ProgressLabel>
      </Progress>,
    )
    const root = screen.getByRole('progressbar')
    const labelId = root.getAttribute('aria-labelledby')
    expect(labelId).toBeTruthy()
    expect(document.getElementById(labelId!)?.textContent).toBe('Uploading')
  })

  it('renders the formatted value via ProgressValue', () => {
    render(
      <Progress value={42}>
        <ProgressValue />
      </Progress>,
    )
    expect(screen.getByText('42%')).toBeInTheDocument()
  })

  it('marks complete state on parts when value reaches max', () => {
    const { container } = render(<Progress value={100} />)
    const indicator = container.querySelector('[data-slot=progress-indicator]') as HTMLElement
    expect(indicator).toHaveAttribute('data-complete')
  })

  it('forwards className alongside the layout classes', () => {
    render(<Progress value={50} className="custom-class" />)
    const root = screen.getByRole('progressbar')
    expect(root.className).toContain('custom-class')
    expect(root.className).toContain('grid')
  })

  it('has no accessibility violations (bar)', async () => {
    const { container } = render(
      <Progress value={60}>
        <ProgressLabel>Loading</ProgressLabel>
        <ProgressValue />
      </Progress>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })

  it('has no accessibility violations (circular)', async () => {
    const { container } = render(
      <Progress value={60} variant="circular">
        <ProgressLabel>Loading</ProgressLabel>
        <ProgressValue />
      </Progress>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
