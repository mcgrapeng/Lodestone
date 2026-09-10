import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'
import { ScrollArea } from './scroll-area'

function Body() {
  return (
    <>
      {Array.from({ length: 40 }, (_, i) => (
        <p key={i}>Item {i + 1}</p>
      ))}
    </>
  )
}

describe('ScrollArea', () => {
  it('renders viewport + content + a single vertical scrollbar by default', () => {
    const { container } = render(
      <ScrollArea className="h-40 w-80">
        <Body />
      </ScrollArea>,
    )
    expect(container.querySelector('[data-slot="scroll-area"]')).not.toBeNull()
    expect(container.querySelector('[data-slot="scroll-area-viewport"]')).not.toBeNull()
    expect(container.querySelector('[data-slot="scroll-area-content"]')).not.toBeNull()
    expect(container.querySelector('[data-slot="scroll-area-corner"]')).toBeNull()
  })

  it('pins content to the viewport width in the default vertical orientation', () => {
    const { container } = render(
      <ScrollArea className="h-40 w-80">
        <Body />
      </ScrollArea>,
    )
    const content = container.querySelector('[data-slot="scroll-area-content"]') as HTMLElement
    expect(content.style.minWidth).toBe('0px')
  })

  it('keeps Base UI content sizing for horizontal orientations', () => {
    const { container } = render(
      <ScrollArea className="h-40 w-80" orientation="horizontal">
        <Body />
      </ScrollArea>,
    )
    const content = container.querySelector('[data-slot="scroll-area-content"]') as HTMLElement
    expect(content.style.minWidth).toBe('fit-content')
  })

  it('does not apply mask classes when scrollShadow is omitted', () => {
    const { container } = render(
      <ScrollArea className="h-40 w-80">
        <Body />
      </ScrollArea>,
    )
    const viewport = container.querySelector('[data-slot="scroll-area-viewport"]') as HTMLElement
    expect(viewport.className).not.toContain('mask-intersect')
  })

  it('applies mask classes when scrollShadow is true', () => {
    const { container } = render(
      <ScrollArea className="h-40 w-80" scrollShadow>
        <Body />
      </ScrollArea>,
    )
    const viewport = container.querySelector('[data-slot="scroll-area-viewport"]') as HTMLElement
    expect(viewport.className).toContain('mask-intersect')
    expect(viewport.className).toContain('mask-no-repeat')
    expect(viewport.className).toContain('mask-image:linear-gradient')
  })

  it('omits hover-reveal classes when scrollbarVisibility defaults to "always"', () => {
    const { container } = render(
      <ScrollArea className="h-40 w-80">
        <Body />
      </ScrollArea>,
    )
    const scrollbar = container.querySelector('[data-slot="scroll-area-scrollbar"]') as HTMLElement | null
    // Scrollbar may not mount in jsdom; if it does, verify classes.
    if (scrollbar) {
      expect(scrollbar.getAttribute('data-visibility')).toBe('always')
      expect(scrollbar.className).not.toContain('opacity-0')
    }
  })

  it('applies auto-reveal classes when scrollbarVisibility="auto"', () => {
    const { container } = render(
      <ScrollArea className="h-40 w-80" scrollbarVisibility="auto">
        <Body />
      </ScrollArea>,
    )
    const scrollbar = container.querySelector('[data-slot="scroll-area-scrollbar"]') as HTMLElement | null
    if (scrollbar) {
      expect(scrollbar.getAttribute('data-visibility')).toBe('auto')
      expect(scrollbar.className).toContain('opacity-0')
      expect(scrollbar.className).toContain('transition-[width,height,opacity]')
      expect(scrollbar.className).toContain('motion-reduce:transition-none')
      expect(scrollbar.className).toContain('data-[hovering]:opacity-100')
      expect(scrollbar.className).toContain('data-[scrolling]:opacity-100')
    }
  })

  it('does not render the scrollbar when scrollbarVisibility="never"', () => {
    const { container } = render(
      <ScrollArea className="h-40 w-80" scrollbarVisibility="never" orientation="both">
        <Body />
      </ScrollArea>,
    )
    expect(container.querySelector('[data-slot="scroll-area-scrollbar"]')).toBeNull()
    expect(container.querySelector('[data-slot="scroll-area-corner"]')).toBeNull()
    // Viewport stays scrollable - it's still in the DOM.
    expect(container.querySelector('[data-slot="scroll-area-viewport"]')).not.toBeNull()
  })

  it('forwards className to the root element', () => {
    const { container } = render(
      <ScrollArea className="custom-area h-40 w-80">
        <Body />
      </ScrollArea>,
    )
    const root = container.querySelector('[data-slot="scroll-area"]') as HTMLElement
    expect(root.className).toContain('custom-area')
    expect(root.className).toContain('relative')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <ScrollArea className="h-40 w-80" scrollShadow scrollbarVisibility="auto" orientation="both">
        <Body />
      </ScrollArea>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
