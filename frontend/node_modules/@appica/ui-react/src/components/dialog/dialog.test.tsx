import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'
import { Button } from '../button/button'
import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from './dialog'

function renderDialog({
  title = 'Update profile',
  description = 'Make changes to your account.',
  closeButton,
  backdrop,
  frame,
  contentClassName,
}: {
  title?: string
  description?: string
  closeButton?: boolean
  backdrop?: boolean
  frame?: boolean
  contentClassName?: string
} = {}) {
  return render(
    <Dialog>
      <DialogTrigger render={<Button>Open dialog</Button>} />
      <DialogContent
        className={contentClassName}
        {...(closeButton !== undefined ? { closeButton } : {})}
        {...(backdrop !== undefined ? { backdrop } : {})}
        {...(frame !== undefined ? { frame } : {})}
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <DialogBody>Body content</DialogBody>
        <DialogFooter>
          <DialogClose render={<Button variant="outline">Cancel</Button>} />
          <Button>Confirm</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>,
  )
}

describe('Dialog', () => {
  it('tags the trigger with data-slot', () => {
    renderDialog()
    expect(screen.getByRole('button', { name: 'Open dialog' }).getAttribute('data-slot')).toBe('dialog-trigger')
  })

  it('does not render content before being opened', () => {
    renderDialog()
    expect(screen.queryByText('Body content')).toBeNull()
  })

  it('opens on trigger click and exposes a labeled dialog', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: 'Open dialog' }))

    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveAccessibleName('Update profile')
    expect(dialog).toHaveAccessibleDescription('Make changes to your account.')

    const title = screen.getByText('Update profile')
    expect(title.getAttribute('data-slot')).toBe('dialog-title')
    expect(title.className).toContain('text-foreground-intense')
    expect(title.className).toContain('font-semibold')
  })

  it('forwards className to the content popup', async () => {
    const user = userEvent.setup()
    renderDialog({ contentClassName: 'w-200' })

    await user.click(screen.getByRole('button', { name: 'Open dialog' }))
    const dialog = await screen.findByRole('dialog')

    expect(dialog.getAttribute('data-slot')).toBe('dialog-popup')
    expect(dialog.className).toContain('w-200')
    // tailwind-merge drops the default width when overridden
    expect(dialog.className).not.toContain('w-150')
  })

  it('closes when the built-in close button is clicked', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: 'Open dialog' }))
    await screen.findByRole('dialog')

    await user.click(screen.getByRole('button', { name: 'Close' }))
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull()
    })
  })

  it('closes when a DialogClose-wrapped action is clicked', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: 'Open dialog' }))
    await screen.findByRole('dialog')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull()
    })
  })

  it('closes on Escape', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: 'Open dialog' }))
    await screen.findByRole('dialog')

    await user.keyboard('{Escape}')
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull()
    })
  })

  it('hides the built-in close button when closeButton is false', async () => {
    const user = userEvent.setup()
    renderDialog({ closeButton: false })

    await user.click(screen.getByRole('button', { name: 'Open dialog' }))
    await screen.findByRole('dialog')

    expect(screen.queryByRole('button', { name: 'Close' })).toBeNull()
  })

  it('renders a backdrop by default', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: 'Open dialog' }))
    await screen.findByRole('dialog')

    expect(document.querySelector('[data-slot="dialog-backdrop"]')).not.toBeNull()
  })

  it('omits the backdrop when backdrop is false', async () => {
    const user = userEvent.setup()
    renderDialog({ backdrop: false })

    await user.click(screen.getByRole('button', { name: 'Open dialog' }))
    await screen.findByRole('dialog')

    expect(document.querySelector('[data-slot="dialog-backdrop"]')).toBeNull()
  })

  it('frames the popup by default and drops the frame when frame is false', async () => {
    const user = userEvent.setup()
    const { unmount } = renderDialog()

    await user.click(screen.getByRole('button', { name: 'Open dialog' }))
    await screen.findByRole('dialog')
    expect(document.querySelector('[data-slot="dialog-popup"]')).toHaveAttribute('data-frame')

    unmount()
    renderDialog({ frame: false })

    await user.click(screen.getByRole('button', { name: 'Open dialog' }))
    await screen.findByRole('dialog')
    expect(document.querySelector('[data-slot="dialog-popup"]')).not.toHaveAttribute('data-frame')
  })

  it('drops the frame when the backdrop is off, even if frame is set', async () => {
    const user = userEvent.setup()
    renderDialog({ backdrop: false, frame: true })

    await user.click(screen.getByRole('button', { name: 'Open dialog' }))
    await screen.findByRole('dialog')

    expect(document.querySelector('[data-slot="dialog-popup"]')).not.toHaveAttribute('data-frame')
  })

  it('has no accessibility violations when open', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: 'Open dialog' }))
    const dialog = await screen.findByRole('dialog')

    // Scope to the dialog subtree: Base UI's focus-guard sibling spans are
    // framework internals outside our control.
    expect(await axe(dialog)).toHaveNoViolations()
  })
})
