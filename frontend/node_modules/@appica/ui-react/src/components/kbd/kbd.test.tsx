import * as React from 'react'
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'
import { Kbd, KbdGroup } from './kbd'

describe('Kbd', () => {
  it('renders a <kbd> with data-slot and default md size classes', () => {
    const { container } = render(<Kbd>K</Kbd>)
    const el = container.querySelector('[data-slot="kbd"]') as HTMLElement
    expect(el).not.toBeNull()
    expect(el.tagName).toBe('KBD')
    expect(el.className).toContain('text-sm')
    expect(el.className).toContain('min-w-6')
  })

  it.each([
    ['sm', 'min-w-5', 'text-xs'],
    ['md', 'min-w-6', 'text-sm'],
    ['lg', 'min-w-7', 'text-base'],
  ] as const)('applies size="%s" classes', (size, minW, text) => {
    const { container } = render(<Kbd size={size}>K</Kbd>)
    const el = container.querySelector('[data-slot="kbd"]') as HTMLElement
    expect(el.className).toContain(minW)
    expect(el.className).toContain(text)
  })

  it('merges caller className', () => {
    const { container } = render(<Kbd className="my-kbd">K</Kbd>)
    const el = container.querySelector('[data-slot="kbd"]') as HTMLElement
    expect(el.className).toContain('my-kbd')
  })

  it('forwards extra props to the kbd element', () => {
    const { container } = render(<Kbd aria-label="key">K</Kbd>)
    const el = container.querySelector('[data-slot="kbd"]') as HTMLElement
    expect(el.getAttribute('aria-label')).toBe('key')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<Kbd>K</Kbd>)
    expect(await axe(container)).toHaveNoViolations()
  })
})

describe('KbdGroup', () => {
  it('renders a data-slot wrapper', () => {
    const { container } = render(
      <KbdGroup>
        <Kbd>⌘</Kbd>
        <Kbd>K</Kbd>
      </KbdGroup>,
    )
    const group = container.querySelector('[data-slot="kbd-group"]') as HTMLElement
    expect(group).not.toBeNull()
    expect(group.className).toContain('inline-flex')
  })

  it('propagates size to child Kbd elements', () => {
    const { container } = render(
      <KbdGroup size="lg">
        <Kbd data-testid="a">⌘</Kbd>
        <Kbd data-testid="b">K</Kbd>
      </KbdGroup>,
    )
    const a = container.querySelector('[data-testid="a"]') as HTMLElement
    const b = container.querySelector('[data-testid="b"]') as HTMLElement
    expect(a.className).toContain('min-w-7')
    expect(b.className).toContain('min-w-7')
  })

  it('lets an explicit size on an inner Kbd override the group default', () => {
    const { container } = render(
      <KbdGroup size="lg">
        <Kbd size="sm" data-testid="overridden">
          ⌘
        </Kbd>
        <Kbd data-testid="inherits">K</Kbd>
      </KbdGroup>,
    )
    const overridden = container.querySelector('[data-testid="overridden"]') as HTMLElement
    const inherits = container.querySelector('[data-testid="inherits"]') as HTMLElement
    expect(overridden.className).toContain('min-w-5')
    expect(inherits.className).toContain('min-w-7')
  })

  it('leaves non-Kbd children untouched', () => {
    const { container } = render(
      <KbdGroup size="lg">
        <span data-testid="plus">+</span>
        <Kbd data-testid="k">K</Kbd>
      </KbdGroup>,
    )
    const plus = container.querySelector('[data-testid="plus"]') as HTMLElement
    expect(plus.tagName).toBe('SPAN')
    const k = container.querySelector('[data-testid="k"]') as HTMLElement
    expect(k.className).toContain('min-w-7')
  })

  it('merges caller className on the wrapper', () => {
    const { container } = render(
      <KbdGroup className="my-group">
        <Kbd>K</Kbd>
      </KbdGroup>,
    )
    const group = container.querySelector('[data-slot="kbd-group"]') as HTMLElement
    expect(group.className).toContain('my-group')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <KbdGroup size="md">
        <Kbd>⌘</Kbd>
        <Kbd>K</Kbd>
      </KbdGroup>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
