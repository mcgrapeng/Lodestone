import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { Navigation, NavigationList, NavigationItem } from './navigation'
import { type NavigationActiveLink, type NavigationSize } from './navigation-context'
import { NavigationLink } from './navigation-link'

function renderBasic(props?: { activeLink?: NavigationActiveLink; size?: NavigationSize }) {
  return render(
    <Navigation aria-label="Main" {...props}>
      <NavigationList>
        <NavigationItem>
          <NavigationLink href="#home" value="home">
            Home
          </NavigationLink>
        </NavigationItem>
        <NavigationItem>
          <NavigationLink href="#about" value="about">
            About
          </NavigationLink>
        </NavigationItem>
        <NavigationItem>
          <NavigationLink href="#contact" value="contact">
            Contact
          </NavigationLink>
        </NavigationItem>
      </NavigationList>
    </Navigation>,
  )
}

describe('Navigation', () => {
  it('renders as a <nav> with role and accessible name', () => {
    renderBasic()
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(nav.tagName).toBe('NAV')
    expect(nav).toHaveAttribute('data-slot', 'navigation')
  })

  it('defaults to horizontal orientation via data-orientation', () => {
    renderBasic()
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(nav).not.toHaveAttribute('aria-orientation')
    expect(nav).toHaveAttribute('data-orientation', 'horizontal')
  })

  it('marks vertical orientation with data-orientation', () => {
    render(
      <Navigation aria-label="Side" orientation="vertical" variant="line">
        <NavigationList>
          <NavigationItem>
            <NavigationLink href="#a" value="a">
              A
            </NavigationLink>
          </NavigationItem>
        </NavigationList>
      </Navigation>,
    )
    const nav = screen.getByRole('navigation', { name: 'Side' })
    expect(nav).toHaveAttribute('data-orientation', 'vertical')
  })

  it('renders <ul> for the list and <li> for items', () => {
    renderBasic()
    const list = screen.getByRole('list')
    expect(list.tagName).toBe('UL')
    expect(list).toHaveAttribute('data-slot', 'navigation-list')
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
  })

  it('activeLink matches the link with the corresponding value', () => {
    renderBasic({ activeLink: 'about' })
    const active = screen.getByRole('link', { current: 'page' })
    expect(active).toHaveTextContent('About')
    expect(active).toHaveAttribute('data-active')
  })

  it('per-link active={true} overrides activeLink mismatch', () => {
    render(
      <Navigation aria-label="Main" activeLink="home">
        <NavigationList>
          <NavigationItem>
            <NavigationLink href="#about" value="about" active>
              About
            </NavigationLink>
          </NavigationItem>
        </NavigationList>
      </Navigation>,
    )
    const link = screen.getByRole('link', { name: 'About' })
    expect(link).toHaveAttribute('aria-current', 'page')
  })

  it('per-link active={false} overrides activeLink match', () => {
    render(
      <Navigation aria-label="Main" activeLink="home">
        <NavigationList>
          <NavigationItem>
            <NavigationLink href="#home" value="home" active={false}>
              Home
            </NavigationLink>
          </NavigationItem>
        </NavigationList>
      </Navigation>,
    )
    const link = screen.getByRole('link', { name: 'Home' })
    expect(link).not.toHaveAttribute('aria-current')
    expect(link).not.toHaveAttribute('data-active')
  })

  it('disabled links carry aria-disabled and data-disabled', () => {
    render(
      <Navigation aria-label="Main">
        <NavigationList>
          <NavigationItem>
            <NavigationLink href="#" disabled>
              Disabled
            </NavigationLink>
          </NavigationItem>
        </NavigationList>
      </Navigation>,
    )
    const link = screen.getByRole('link', { name: 'Disabled' })
    expect(link).toHaveAttribute('aria-disabled', 'true')
    expect(link).toHaveAttribute('data-disabled')
  })

  it('forwards className alongside variant classes on the link', () => {
    render(
      <Navigation aria-label="Main">
        <NavigationList>
          <NavigationItem>
            <NavigationLink href="#" className="my-link">
              One
            </NavigationLink>
          </NavigationItem>
        </NavigationList>
      </Navigation>,
    )
    const link = screen.getByRole('link', { name: 'One' })
    expect(link.className).toContain('my-link')
  })

  it('renders the link as a different element via render prop', () => {
    const onClick = vi.fn()
    render(
      <Navigation aria-label="Main">
        <NavigationList>
          <NavigationItem>
            <NavigationLink render={<button type="button" onClick={onClick} />}>Btn</NavigationLink>
          </NavigationItem>
        </NavigationList>
      </Navigation>,
    )
    const el = screen.getByRole('button', { name: 'Btn' })
    expect(el.tagName).toBe('BUTTON')
  })

  it('fires onClick on the link', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(
      <Navigation aria-label="Main">
        <NavigationList>
          <NavigationItem>
            <NavigationLink href="#" onClick={onClick}>
              Click
            </NavigationLink>
          </NavigationItem>
        </NavigationList>
      </Navigation>,
    )
    await user.click(screen.getByRole('link', { name: 'Click' }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('renders NavigationLink standalone without a Navigation root', () => {
    render(<NavigationLink href="#solo">Solo</NavigationLink>)
    const link = screen.getByRole('link', { name: 'Solo' })
    expect(link).toHaveAttribute('data-slot', 'navigation-link')
  })

  it('indicator variant wraps children in a label slot and renders an indicator slot', () => {
    render(
      <Navigation aria-label="Side" orientation="vertical" variant="indicator">
        <NavigationList>
          <NavigationItem>
            <NavigationLink href="#one" value="one">
              One
            </NavigationLink>
          </NavigationItem>
        </NavigationList>
      </Navigation>,
    )
    const link = screen.getByRole('link', { name: 'One' })
    expect(link.querySelector('[data-slot="navigation-link-indicator"]')).not.toBeNull()
    const label = link.querySelector('[data-slot="navigation-link-label"]')
    expect(label).not.toBeNull()
    expect(label).toHaveTextContent('One')
  })

  it('indicator variant accepts a custom indicator node', () => {
    render(
      <NavigationLink variant="indicator" indicator={<span data-testid="custom-indicator" />}>
        Item
      </NavigationLink>,
    )
    expect(screen.getByTestId('custom-indicator')).toBeInTheDocument()
  })

  it('stamps data-orientation="horizontal" on links by default', () => {
    renderBasic()
    for (const link of screen.getAllByRole('link')) {
      expect(link).toHaveAttribute('data-orientation', 'horizontal')
    }
  })

  it('propagates vertical orientation to links via context', () => {
    render(
      <Navigation aria-label="Side" orientation="vertical" variant="line">
        <NavigationList>
          <NavigationItem>
            <NavigationLink href="#a" value="a">
              A
            </NavigationLink>
          </NavigationItem>
        </NavigationList>
      </Navigation>,
    )
    expect(screen.getByRole('link', { name: 'A' })).toHaveAttribute('data-orientation', 'vertical')
  })

  it('NavigationLink orientation prop overrides context', () => {
    render(
      <Navigation aria-label="Main">
        <NavigationList>
          <NavigationItem>
            <NavigationLink href="#a" orientation="vertical">
              A
            </NavigationLink>
          </NavigationItem>
        </NavigationList>
      </Navigation>,
    )
    expect(screen.getByRole('link', { name: 'A' })).toHaveAttribute('data-orientation', 'vertical')
  })

  it('has no accessibility violations', async () => {
    const { container } = renderBasic({ activeLink: 'home' })
    expect(await axe(container)).toHaveNoViolations()
  })
})
