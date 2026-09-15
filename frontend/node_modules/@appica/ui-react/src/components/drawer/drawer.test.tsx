import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'
import { Button } from '../button/button'
import {
  Drawer,
  DrawerBody,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from './drawer'

function renderDrawer({
  side,
  title = 'Edit profile',
  description = 'Update your details below.',
  closeButton,
  backdrop,
  frame,
  contentClassName,
}: {
  side?: 'top' | 'bottom' | 'left' | 'right'
  title?: string
  description?: string
  closeButton?: boolean
  backdrop?: boolean
  frame?: boolean
  contentClassName?: string
} = {}) {
  return render(
    <Drawer {...(side !== undefined ? { side } : {})}>
      <DrawerTrigger render={<Button>Open drawer</Button>} />
      <DrawerContent
        className={contentClassName}
        {...(closeButton !== undefined ? { closeButton } : {})}
        {...(backdrop !== undefined ? { backdrop } : {})}
        {...(frame !== undefined ? { frame } : {})}
      >
        <DrawerHeader>
          <DrawerTitle>{title}</DrawerTitle>
          <DrawerDescription>{description}</DrawerDescription>
        </DrawerHeader>
        <DrawerBody>Body content</DrawerBody>
        <DrawerFooter>
          <DrawerClose render={<Button variant="outline">Cancel</Button>} />
          <Button>Save</Button>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>,
  )
}

describe('Drawer', () => {
  it('tags the trigger with data-slot', () => {
    renderDrawer()
    expect(screen.getByRole('button', { name: 'Open drawer' }).getAttribute('data-slot')).toBe('drawer-trigger')
  })

  it('does not render content before being opened', () => {
    renderDrawer()
    expect(screen.queryByText('Body content')).toBeNull()
  })

  it('opens on trigger click and exposes a labeled dialog', async () => {
    const user = userEvent.setup()
    renderDrawer()

    await user.click(screen.getByRole('button', { name: 'Open drawer' }))

    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveAccessibleName('Edit profile')
    expect(dialog).toHaveAccessibleDescription('Update your details below.')

    const title = screen.getByText('Edit profile')
    expect(title.getAttribute('data-slot')).toBe('drawer-title')
    expect(title.className).toContain('text-foreground-intense')
  })

  it('forwards className to the content popup', async () => {
    const user = userEvent.setup()
    renderDrawer({ contentClassName: 'w-200' })

    await user.click(screen.getByRole('button', { name: 'Open drawer' }))
    const dialog = await screen.findByRole('dialog')

    expect(dialog.getAttribute('data-slot')).toBe('drawer-popup')
    expect(dialog.className).toContain('w-200')
  })

  it('closes when the built-in close button is clicked', async () => {
    const user = userEvent.setup()
    renderDrawer()

    await user.click(screen.getByRole('button', { name: 'Open drawer' }))
    await screen.findByRole('dialog')

    await user.click(screen.getByRole('button', { name: 'Close' }))
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull()
    })
  })

  it('closes when a DrawerClose action is clicked', async () => {
    const user = userEvent.setup()
    renderDrawer()

    await user.click(screen.getByRole('button', { name: 'Open drawer' }))
    await screen.findByRole('dialog')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull()
    })
  })

  it('hides the built-in close button when closeButton is false', async () => {
    const user = userEvent.setup()
    renderDrawer({ closeButton: false })

    await user.click(screen.getByRole('button', { name: 'Open drawer' }))
    await screen.findByRole('dialog')

    expect(screen.queryByRole('button', { name: 'Close' })).toBeNull()
  })

  it('omits the backdrop when backdrop is false', async () => {
    const user = userEvent.setup()
    renderDrawer({ backdrop: false })

    await user.click(screen.getByRole('button', { name: 'Open drawer' }))
    await screen.findByRole('dialog')

    expect(document.querySelector('[data-slot="drawer-backdrop"]')).toBeNull()
  })

  it('renders a backdrop only for the outermost drawer when nested', async () => {
    const user = userEvent.setup()
    render(
      <Drawer>
        <DrawerTrigger render={<Button>Open outer</Button>} />
        <DrawerContent>
          <DrawerHeader>
            <DrawerTitle>Outer</DrawerTitle>
          </DrawerHeader>
          <DrawerBody>
            <Drawer>
              <DrawerTrigger render={<Button>Open nested</Button>} />
              <DrawerContent>
                <DrawerHeader>
                  <DrawerTitle>Nested</DrawerTitle>
                </DrawerHeader>
              </DrawerContent>
            </Drawer>
          </DrawerBody>
        </DrawerContent>
      </Drawer>,
    )

    await user.click(screen.getByRole('button', { name: 'Open outer' }))
    await screen.findByText('Outer')
    await user.click(screen.getByRole('button', { name: 'Open nested' }))
    await screen.findByText('Nested')

    // Outermost drawer keeps its backdrop; the nested one auto-omits it.
    expect(document.querySelectorAll('[data-slot="drawer-backdrop"]')).toHaveLength(1)
    // The frame needs a backdrop, so only the outermost drawer is framed.
    expect(document.querySelectorAll('[data-slot="drawer-popup"][data-frame]')).toHaveLength(1)
  })

  it('frames the popup by default and drops the frame when frame is false', async () => {
    const user = userEvent.setup()
    const { unmount } = renderDrawer()

    await user.click(screen.getByRole('button', { name: 'Open drawer' }))
    await screen.findByRole('dialog')
    expect(document.querySelector('[data-slot="drawer-popup"]')).toHaveAttribute('data-frame')

    unmount()
    renderDrawer({ frame: false })

    await user.click(screen.getByRole('button', { name: 'Open drawer' }))
    await screen.findByRole('dialog')
    expect(document.querySelector('[data-slot="drawer-popup"]')).not.toHaveAttribute('data-frame')
  })

  it('drops the frame when the backdrop is off, even if frame is set', async () => {
    const user = userEvent.setup()
    renderDrawer({ backdrop: false, frame: true })

    await user.click(screen.getByRole('button', { name: 'Open drawer' }))
    await screen.findByRole('dialog')

    expect(document.querySelector('[data-slot="drawer-popup"]')).not.toHaveAttribute('data-frame')
  })

  it('positions on the requested side', async () => {
    const user = userEvent.setup()
    renderDrawer({ side: 'right' })

    await user.click(screen.getByRole('button', { name: 'Open drawer' }))
    const dialog = await screen.findByRole('dialog')

    // right-side drawer is full-height and slides in from the inline-end edge
    expect(dialog.className).toContain('h-full')
    expect(dialog.className).toContain('ps-4')
  })

  it('has no accessibility violations when open', async () => {
    const user = userEvent.setup()
    renderDrawer()

    await user.click(screen.getByRole('button', { name: 'Open drawer' }))
    const dialog = await screen.findByRole('dialog')

    expect(await axe(dialog)).toHaveNoViolations()
  })
})
