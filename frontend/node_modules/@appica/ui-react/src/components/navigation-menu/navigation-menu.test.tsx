import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuIcon,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
} from './navigation-menu'

const setupUser = () => userEvent.setup({ pointerEventsCheck: 0 })

interface BasicNavProps {
  variant?: 'pill' | 'line'
  size?: 'sm' | 'md' | 'lg'
  icon?: 'chevron' | 'caret' | 'plus' | false
  orientation?: 'horizontal' | 'vertical'
  backdrop?: boolean
  viewport?: boolean
  morph?: boolean
}

function BasicNav({ variant, size, icon, orientation, backdrop, viewport, morph }: BasicNavProps = {}) {
  return (
    <NavigationMenu
      {...(variant && { variant })}
      {...(size && { size })}
      {...(icon !== undefined && { icon })}
      {...(orientation && { orientation })}
      {...(backdrop !== undefined && { backdrop })}
      {...(viewport !== undefined && { viewport })}
      {...(morph !== undefined && { morph })}
      aria-label="Main"
    >
      <NavigationMenuList>
        <NavigationMenuItem>
          <NavigationMenuTrigger>
            Products
            <NavigationMenuIcon />
          </NavigationMenuTrigger>
          <NavigationMenuContent>
            <NavigationMenuLink href="/p/one">Product One</NavigationMenuLink>
            <NavigationMenuLink href="/p/two">Product Two</NavigationMenuLink>
          </NavigationMenuContent>
        </NavigationMenuItem>
        <NavigationMenuItem>
          <NavigationMenuTrigger>
            Company
            <NavigationMenuIcon />
          </NavigationMenuTrigger>
          <NavigationMenuContent>
            <NavigationMenuLink href="/about">About</NavigationMenuLink>
          </NavigationMenuContent>
        </NavigationMenuItem>
      </NavigationMenuList>
    </NavigationMenu>
  )
}

describe('NavigationMenu', () => {
  it('renders with the navigation-menu data-slot and horizontal orientation by default', () => {
    const { container } = render(<BasicNav />)
    const root = container.querySelector('[data-slot="navigation-menu"]') as HTMLElement
    expect(root).not.toBeNull()
    expect(root.getAttribute('data-orientation')).toBe('horizontal')
  })

  it('applies the pill gap to the list by default', () => {
    const { container } = render(<BasicNav />)
    const list = container.querySelector('[data-slot="navigation-menu-list"]') as HTMLElement
    expect(list.className).toContain('gap-0.5')
  })

  it('applies the line gap to the list when variant is line', () => {
    const { container } = render(<BasicNav variant="line" />)
    const list = container.querySelector('[data-slot="navigation-menu-list"]') as HTMLElement
    expect(list.className).toContain('gap-7')
  })

  it('stacks the list vertically when orientation is vertical', () => {
    const { container } = render(<BasicNav orientation="vertical" />)
    const list = container.querySelector('[data-slot="navigation-menu-list"]') as HTMLElement
    expect(list.className).toContain('flex-col')
  })

  it('styles triggers with the pill variant by default', () => {
    const { container } = render(<BasicNav />)
    const trigger = container.querySelector('[data-slot="navigation-menu-trigger"]') as HTMLElement
    expect(trigger.className).toContain('before:bg-background-muted')
  })

  it('styles triggers with the line variant when requested', () => {
    const { container } = render(<BasicNav variant="line" />)
    const trigger = container.querySelector('[data-slot="navigation-menu-trigger"]') as HTMLElement
    expect(trigger.className).toContain('after:bg-no-repeat')
  })

  it('mirrors the root orientation onto each trigger', () => {
    const { container } = render(<BasicNav orientation="vertical" />)
    const trigger = container.querySelector('[data-slot="navigation-menu-trigger"]') as HTMLElement
    expect(trigger.getAttribute('data-orientation')).toBe('vertical')
  })

  it('propagates size to the trigger text class', () => {
    const { container } = render(<BasicNav size="lg" />)
    const trigger = container.querySelector('[data-slot="navigation-menu-trigger"]') as HTMLElement
    expect(trigger.className).toContain('text-base')
  })

  it('renders a chevron icon by default and sizes it by the root size', () => {
    const { container } = render(<BasicNav size="md" />)
    const icon = container.querySelector('[data-slot="navigation-menu-icon"]') as HTMLElement
    expect(icon).not.toBeNull()
    const svg = icon.querySelector('svg') as SVGElement
    expect(svg.getAttribute('viewBox')).toBe('0 0 16 16')
    expect(svg.getAttribute('class') ?? '').toContain('size-4')
  })

  it('renders a caret icon when icon="caret"', () => {
    const { container } = render(<BasicNav icon="caret" />)
    const svg = container.querySelector('[data-slot="navigation-menu-icon"] svg') as SVGElement
    expect(svg.getAttribute('viewBox')).toBe('0 0 24 24')
  })

  it('renders the plus icon with two rects (so the morph animation works) when icon="plus"', () => {
    const { container } = render(<BasicNav icon="plus" />)
    const svg = container.querySelector('[data-slot="navigation-menu-icon"] svg') as SVGElement
    const rects = svg.querySelectorAll('rect')
    expect(rects).toHaveLength(2)
    // The plus morphs into an ✕ when open: the svg rotates and the vertical bar spins.
    expect(svg.getAttribute('class') ?? '').toContain('group-data-popup-open/navigation-menu-icon:rotate-180')
    expect(rects[1]?.getAttribute('class') ?? '').toContain('group-data-popup-open/navigation-menu-icon:rotate-90')
  })

  it('renders nothing for the icon when icon={false} at the root', () => {
    const { container } = render(<BasicNav icon={false} />)
    expect(container.querySelector('[data-slot="navigation-menu-icon"]')).toBeNull()
  })

  it('per-icon override beats the root', () => {
    const { container } = render(
      <NavigationMenu icon="chevron" aria-label="Main">
        <NavigationMenuList>
          <NavigationMenuItem>
            <NavigationMenuTrigger>
              Solo <NavigationMenuIcon icon={false} />
            </NavigationMenuTrigger>
            <NavigationMenuContent>
              <NavigationMenuLink href="/x">X</NavigationMenuLink>
            </NavigationMenuContent>
          </NavigationMenuItem>
        </NavigationMenuList>
      </NavigationMenu>,
    )
    expect(container.querySelector('[data-slot="navigation-menu-icon"]')).toBeNull()
  })

  it('applies the smaller icon size class when size="sm"', () => {
    const { container } = render(<BasicNav size="sm" />)
    const svg = container.querySelector('[data-slot="navigation-menu-icon"] svg') as SVGElement
    expect(svg.getAttribute('class') ?? '').toContain('size-3.5')
  })

  it('opens the menu on trigger click and shows the link inside the popup', async () => {
    const user = setupUser()
    render(<BasicNav />)
    await user.click(screen.getByRole('button', { name: /Products/ }))
    expect(await screen.findByRole('link', { name: 'Product One' })).toBeInTheDocument()
  })

  it('closes the menu on Escape', async () => {
    const user = setupUser()
    render(<BasicNav />)
    await user.click(screen.getByRole('button', { name: /Products/ }))
    await screen.findByRole('link', { name: 'Product One' })
    await user.keyboard('{Escape}')
    await waitFor(() => {
      expect(screen.queryByRole('link', { name: 'Product One' })).toBeNull()
    })
  })

  it('moves focus between triggers with the arrow keys', async () => {
    const user = setupUser()
    render(<BasicNav />)
    const products = screen.getByRole('button', { name: /Products/ })
    products.focus()
    expect(products).toHaveFocus()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('button', { name: /Company/ })).toHaveFocus()
  })

  it('renders the backdrop when backdrop={true} after opening', async () => {
    const user = setupUser()
    const { baseElement } = render(<BasicNav backdrop />)
    await user.click(screen.getByRole('button', { name: /Products/ }))
    await screen.findByRole('link', { name: 'Product One' })
    expect(baseElement.querySelector('[data-slot="navigation-menu-backdrop"]')).not.toBeNull()
  })

  it('applies the popup size CSS vars by default so the popup morphs', async () => {
    const user = setupUser()
    const { baseElement } = render(<BasicNav />)
    await user.click(screen.getByRole('button', { name: /Products/ }))
    await screen.findByRole('link', { name: 'Product One' })
    const popup = baseElement.querySelector('[data-slot="navigation-menu-popup"]') as HTMLElement
    expect(popup.className).toContain('w-(--popup-width)')
    expect(popup.className).toContain('h-(--popup-height)')
  })

  it('drops the size CSS vars and size transition when morph={false}', async () => {
    const user = setupUser()
    const { baseElement } = render(<BasicNav morph={false} />)
    await user.click(screen.getByRole('button', { name: /Products/ }))
    await screen.findByRole('link', { name: 'Product One' })
    const popup = baseElement.querySelector('[data-slot="navigation-menu-popup"]') as HTMLElement
    expect(popup.className).not.toContain('w-(--popup-width)')
    expect(popup.className).not.toContain('h-(--popup-height)')
    const positioner = baseElement.querySelector('[data-slot="navigation-menu-positioner"]') as HTMLElement
    expect(positioner.className).not.toContain('w-(--positioner-width)')
  })

  it('omits the backdrop by default', async () => {
    const user = setupUser()
    const { baseElement } = render(<BasicNav />)
    await user.click(screen.getByRole('button', { name: /Products/ }))
    await screen.findByRole('link', { name: 'Product One' })
    expect(baseElement.querySelector('[data-slot="navigation-menu-backdrop"]')).toBeNull()
  })

  it('skips the auto-rendered viewport when viewport={false}', async () => {
    const user = setupUser()
    const { baseElement } = render(<BasicNav viewport={false} />)
    await user.click(screen.getByRole('button', { name: /Products/ }))
    // No popup means no link from the active content appears.
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(baseElement.querySelector('[data-slot="navigation-menu-popup"]')).toBeNull()
    expect(screen.queryByRole('link', { name: 'Product One' })).toBeNull()
  })

  it('opens the popup to inline-end when orientation is vertical', async () => {
    const user = setupUser()
    const { baseElement } = render(<BasicNav orientation="vertical" />)
    await user.click(screen.getByRole('button', { name: /Products/ }))
    await screen.findByRole('link', { name: 'Product One' })
    const positioner = baseElement.querySelector('[data-slot="navigation-menu-popup"]')?.parentElement as HTMLElement
    // Base UI resolves logical sides; data-side reports the physical side. In LTR vertical, inline-end == right.
    expect(['right', 'inline-end']).toContain(positioner.getAttribute('data-side'))
  })

  it('has no a11y violations in the closed state', async () => {
    const { container } = render(<BasicNav />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
