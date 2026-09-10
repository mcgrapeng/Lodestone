import { render, screen, waitFor } from '@testing-library/react'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'
import { Avatar, AvatarBadge, AvatarFallback, AvatarGroup, AvatarImage } from './avatar'

// jsdom does not actually load images. Base UI Avatar uses a pre-loader that
// listens for `load`/`error` on a probe Image - without this stub the Image
// never transitions out of "loading", and Avatar.Image is never mounted.
const ORIGINAL_SRC_DESCRIPTOR = Object.getOwnPropertyDescriptor(window.Image.prototype, 'src')
beforeAll(() => {
  Object.defineProperty(window.Image.prototype, 'src', {
    configurable: true,
    set(value: string) {
      this.setAttribute('src', value)
      queueMicrotask(() => {
        this.dispatchEvent(new Event('load'))
        this.onload?.(new Event('load') as Event)
      })
    },
    get() {
      return this.getAttribute('src') ?? ''
    },
  })
})
afterAll(() => {
  if (ORIGINAL_SRC_DESCRIPTOR) {
    Object.defineProperty(window.Image.prototype, 'src', ORIGINAL_SRC_DESCRIPTOR)
  }
})

const ROUNDED_RADIUS_CLASS = 'rounded-[calc(tan(atan2(var(--radius-md),2.5rem))*100%)]'

describe('Avatar', () => {
  it('renders a root with data-slot and default md size + circle shape', () => {
    const { container } = render(
      <Avatar>
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    )

    const root = container.querySelector('[data-slot="avatar"]') as HTMLElement
    expect(root).not.toBeNull()
    expect(root.className).toContain('size-[1em]')
    expect(root.className).toContain('text-[2.5rem]')
    expect(root.className).toContain('rounded-full')
    expect(root.className).toContain('bg-background-strong')
    expect(root.className).toContain('relative')
  })

  it('applies the per-preset font-size class', () => {
    const { container } = render(
      <Avatar size="lg" shape="rounded">
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    )

    const root = container.querySelector('[data-slot="avatar"]') as HTMLElement
    expect(root.className).toContain('text-[3rem]')
    expect(root.className).toContain(ROUNDED_RADIUS_CLASS)
  })

  it('uses rounded-full when shape="circle"', () => {
    const { container } = render(
      <Avatar shape="circle" size="md">
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    )

    const root = container.querySelector('[data-slot="avatar"]') as HTMLElement
    expect(root.className).toContain('rounded-full')
    expect(root.className).not.toContain(ROUNDED_RADIUS_CLASS)
  })

  it('drives numeric size via inline font-size (no preset text class)', () => {
    const { container } = render(
      <Avatar size={56} shape="rounded">
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    )

    const root = container.querySelector('[data-slot="avatar"]') as HTMLElement
    expect(root.style.fontSize).toBe('56px')
    expect(root.className).toContain('size-[1em]')
    expect(root.className).toContain(ROUNDED_RADIUS_CLASS)
    expect(root.className).not.toContain('text-[2.5rem]')
  })

  it('lets a caller-provided style override numeric defaults', () => {
    const { container } = render(
      <Avatar size={56} style={{ fontSize: '80px' }}>
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    )

    const root = container.querySelector('[data-slot="avatar"]') as HTMLElement
    expect(root.style.fontSize).toBe('80px')
  })

  it('renders the fallback content when no image is provided', () => {
    render(
      <Avatar>
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    )

    expect(screen.getByText('JD')).toBeTruthy()
  })

  it('shrinks textual fallback content to 0.4em', () => {
    const { container } = render(
      <Avatar>
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    )

    const fb = container.querySelector('[data-slot="avatar-fallback"]') as HTMLElement
    expect(fb.className).toContain('text-[0.4em]')
    expect(fb.className).toContain('has-[svg]:text-[1em]')
  })

  it('renders AvatarImage as an <img> with src/alt and data-slot', async () => {
    const { container } = render(
      <Avatar>
        <AvatarImage src="https://example.com/jane.jpg" alt="Jane Doe" />
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    )

    const img = await waitFor(() => {
      const el = container.querySelector('[data-slot="avatar-image"]') as HTMLImageElement | null
      if (!el) throw new Error('avatar-image not mounted')
      return el
    })
    expect(img.tagName).toBe('IMG')
    expect(img.getAttribute('src')).toBe('https://example.com/jane.jpg')
    expect(img.getAttribute('alt')).toBe('Jane Doe')
    expect(img.className).toContain('object-cover')
    expect(img.className).toContain('rounded-[inherit]')
  })

  it('lifts src from the render element so Base UI mounts without redeclaring it', async () => {
    // No `src` on AvatarImage - only on the render element. The wrapper should
    // lift it across so Base UI's pre-loader fires and the cloned element mounts.
    render(
      <Avatar>
        <AvatarImage alt="Jane" render={<img src="https://example.com/jane.jpg" data-testid="lifted-img" />} />
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    )

    const lifted = await screen.findByTestId('lifted-img')
    expect(lifted.getAttribute('src')).toBe('https://example.com/jane.jpg')
    expect(lifted.getAttribute('data-slot')).toBe('avatar-image')
  })

  it('lets AvatarImage swap the underlying element via render prop', async () => {
    render(
      <Avatar>
        <AvatarImage
          src="https://example.com/jane.jpg"
          alt="Jane Doe"
          render={(props) => <div data-testid="custom-image" {...props} />}
        />
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    )

    const custom = await screen.findByTestId('custom-image')
    expect(custom.tagName).toBe('DIV')
    expect(custom.getAttribute('data-slot')).toBe('avatar-image')
    expect(custom.className).toContain('object-cover')
    expect(custom.className).toContain('rounded-[inherit]')
  })

  it('AvatarBadge renders a dot without ping span by default', () => {
    const { container } = render(
      <Avatar>
        <AvatarFallback>JD</AvatarFallback>
        <AvatarBadge />
      </Avatar>,
    )

    const badge = container.querySelector('[data-slot="avatar-badge"]') as HTMLElement
    expect(badge).not.toBeNull()
    expect(badge.className).toContain('size-[30%]')
    expect(badge.className).toContain('rounded-full')
    expect(badge.querySelectorAll('span').length).toBe(1)
    expect(badge.querySelector('.animate-ping-paced')).toBeNull()
  })

  it('AvatarBadge adds the ping span when animate is true', () => {
    const { container } = render(
      <Avatar>
        <AvatarFallback>JD</AvatarFallback>
        <AvatarBadge animate />
      </Avatar>,
    )

    const badge = container.querySelector('[data-slot="avatar-badge"]') as HTMLElement
    expect(badge.querySelector('.animate-ping-paced')).not.toBeNull()
  })

  it('AvatarBadge merges a caller className', () => {
    const { container } = render(
      <Avatar>
        <AvatarFallback>JD</AvatarFallback>
        <AvatarBadge className="text-error-emphasis" />
      </Avatar>,
    )

    const badge = container.querySelector('[data-slot="avatar-badge"]') as HTMLElement
    expect(badge.className).toContain('text-error-emphasis')
  })

  it('forwards className on the Root', () => {
    const { container } = render(
      <Avatar className="my-avatar">
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    )

    const root = container.querySelector('[data-slot="avatar"]') as HTMLElement
    expect(root.className).toContain('my-avatar')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <Avatar size="md">
        <AvatarImage src="https://example.com/jane.jpg" alt="Jane Doe" />
        <AvatarFallback>JD</AvatarFallback>
        <AvatarBadge animate />
      </Avatar>,
    )

    expect(await axe(container)).toHaveNoViolations()
  })
})

describe('AvatarGroup', () => {
  it('renders a data-slot wrapper with horizontal layout and ring selectors by default', () => {
    const { container } = render(
      <AvatarGroup>
        <Avatar>
          <AvatarFallback>JD</AvatarFallback>
        </Avatar>
        <Avatar>
          <AvatarFallback>AB</AvatarFallback>
        </Avatar>
      </AvatarGroup>,
    )

    const group = container.querySelector('[data-slot="avatar-group"]') as HTMLElement
    expect(group).not.toBeNull()
    expect(group.className).toContain('flex')
    expect(group.className).toContain('space-x-[-0.2em]')
    expect(group.className).toContain('*:data-[slot=avatar]:ring-[calc(1em/12)]')
    expect(group.className).toContain('*:data-[slot=avatar]:ring-background')
  })

  it('switches to flex-col + -space-y when orientation="vertical"', () => {
    const { container } = render(
      <AvatarGroup orientation="vertical">
        <Avatar>
          <AvatarFallback>JD</AvatarFallback>
        </Avatar>
      </AvatarGroup>,
    )

    const group = container.querySelector('[data-slot="avatar-group"]') as HTMLElement
    expect(group.className).toContain('flex-col')
    expect(group.className).toContain('space-y-[-0.2em]')
    expect(group.className).not.toContain('space-x-[-0.2em]')
  })

  it('propagates size to child Avatars', () => {
    const { container } = render(
      <AvatarGroup size="lg">
        <Avatar>
          <AvatarFallback>JD</AvatarFallback>
        </Avatar>
      </AvatarGroup>,
    )

    const avatar = container.querySelector('[data-slot="avatar"]') as HTMLElement
    expect(avatar.className).toContain('text-[3rem]')
  })

  it('propagates shape to child Avatars', () => {
    const { container } = render(
      <AvatarGroup shape="rounded">
        <Avatar>
          <AvatarFallback>JD</AvatarFallback>
        </Avatar>
      </AvatarGroup>,
    )

    const avatar = container.querySelector('[data-slot="avatar"]') as HTMLElement
    expect(avatar.className).toContain(ROUNDED_RADIUS_CLASS)
    expect(avatar.className).not.toContain('rounded-full')
  })

  it('lets an explicit prop on an inner Avatar override the group default', () => {
    const { container } = render(
      <AvatarGroup size="lg" shape="rounded">
        <Avatar size="sm" shape="circle" data-testid="overridden">
          <AvatarFallback>JD</AvatarFallback>
        </Avatar>
        <Avatar data-testid="inherits">
          <AvatarFallback>AB</AvatarFallback>
        </Avatar>
      </AvatarGroup>,
    )

    const overridden = container.querySelector('[data-testid="overridden"]') as HTMLElement
    expect(overridden.className).toContain('text-[2rem]')
    expect(overridden.className).toContain('rounded-full')
    expect(overridden.className).not.toContain(ROUNDED_RADIUS_CLASS)

    const inherits = container.querySelector('[data-testid="inherits"]') as HTMLElement
    expect(inherits.className).toContain('text-[3rem]')
    expect(inherits.className).toContain(ROUNDED_RADIUS_CLASS)
  })

  it('merges caller className on the wrapper', () => {
    const { container } = render(
      <AvatarGroup className="my-group">
        <Avatar>
          <AvatarFallback>JD</AvatarFallback>
        </Avatar>
      </AvatarGroup>,
    )

    const group = container.querySelector('[data-slot="avatar-group"]') as HTMLElement
    expect(group.className).toContain('my-group')
  })

  it('passes non-Avatar children through without injecting size/shape', () => {
    const { container } = render(
      <AvatarGroup size="lg">
        <div data-testid="passthrough">extra</div>
        <Avatar>
          <AvatarFallback>JD</AvatarFallback>
        </Avatar>
      </AvatarGroup>,
    )

    const passthrough = container.querySelector('[data-testid="passthrough"]') as HTMLElement
    expect(passthrough.getAttribute('size')).toBeNull()
    expect(passthrough.getAttribute('shape')).toBeNull()
    expect(passthrough.textContent).toBe('extra')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <AvatarGroup size="md">
        <Avatar>
          <AvatarImage src="https://example.com/jane.jpg" alt="Jane Doe" />
          <AvatarFallback>JD</AvatarFallback>
        </Avatar>
        <Avatar>
          <AvatarFallback>AB</AvatarFallback>
        </Avatar>
      </AvatarGroup>,
    )

    expect(await axe(container)).toHaveNoViolations()
  })
})
