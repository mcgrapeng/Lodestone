import * as React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'
import {
  Menubar,
  MenubarContent,
  MenubarItem,
  MenubarMenu,
  MenubarSeparator,
  MenubarSub,
  MenubarSubContent,
  MenubarSubTrigger,
  MenubarTrigger,
} from './menubar'

// Base UI's popup animation toggles pointer-events while entering; disable
// user-event's safety check (same as dropdown-menu / select tests).
const setupUser = () => userEvent.setup({ pointerEventsCheck: 0 })

interface BasicMenubarProps {
  variant?: 'pill' | 'line'
  size?: 'sm' | 'md' | 'lg'
  orientation?: 'horizontal' | 'vertical'
  onNew?: () => void
}

function BasicMenubar({ variant, size, orientation, onNew }: BasicMenubarProps = {}) {
  return (
    <Menubar
      {...(variant && { variant })}
      {...(size && { size })}
      {...(orientation && { orientation })}
      aria-label="Main"
    >
      <MenubarMenu>
        <MenubarTrigger>File</MenubarTrigger>
        <MenubarContent>
          <MenubarItem onClick={onNew}>New</MenubarItem>
          <MenubarItem>Open</MenubarItem>
          <MenubarItem disabled>Disabled</MenubarItem>
          <MenubarSeparator />
          <MenubarSub>
            <MenubarSubTrigger>More</MenubarSubTrigger>
            <MenubarSubContent>
              <MenubarItem>Nested</MenubarItem>
            </MenubarSubContent>
          </MenubarSub>
        </MenubarContent>
      </MenubarMenu>
      <MenubarMenu>
        <MenubarTrigger>Edit</MenubarTrigger>
        <MenubarContent>
          <MenubarItem>Copy</MenubarItem>
        </MenubarContent>
      </MenubarMenu>
    </Menubar>
  )
}

describe('Menubar', () => {
  it('renders a horizontal menubar with the expected slot and orientation', () => {
    render(<BasicMenubar />)
    const bar = screen.getByRole('menubar', { name: 'Main' })
    expect(bar.getAttribute('data-slot')).toBe('menubar')
    expect(bar.getAttribute('data-orientation')).toBe('horizontal')
  })

  it('applies flex-col styling when orientation is vertical', () => {
    render(<BasicMenubar orientation="vertical" />)
    const bar = screen.getByRole('menubar', { name: 'Main' })
    expect(bar.getAttribute('data-orientation')).toBe('vertical')
    expect(bar.className).toContain('flex-col')
  })

  it('mirrors orientation onto each trigger so the line variant selectors apply', () => {
    render(<BasicMenubar variant="line" orientation="vertical" />)
    const trigger = screen.getByRole('menuitem', { name: 'File' })
    expect(trigger.getAttribute('data-orientation')).toBe('vertical')
  })

  it('styles triggers with the pill variant by default', () => {
    render(<BasicMenubar />)
    const trigger = screen.getByRole('menuitem', { name: 'File' })
    // pill variant in navigationLinkVariants paints the background via a `before:` layer
    expect(trigger.className).toContain('before:bg-background-muted')
  })

  it('styles triggers with the line variant when requested', () => {
    render(<BasicMenubar variant="line" />)
    const trigger = screen.getByRole('menuitem', { name: 'File' })
    // line variant uses an `after:` underline rendered from a gradient
    expect(trigger.className).toContain('after:bg-no-repeat')
  })

  it('propagates size down to triggers and popup content', async () => {
    const user = setupUser()
    render(<BasicMenubar size="lg" />)
    const trigger = screen.getByRole('menuitem', { name: 'File' })
    expect(trigger.className).toContain('text-base')

    await user.click(trigger)
    const item = await screen.findByRole('menuitem', { name: 'New' })
    const popup = item.closest('[data-slot="menubar-content"]') as HTMLElement
    expect(popup).not.toBeNull()
    expect(popup.className).toContain('rounded-xl')
  })

  it('opens a menu on trigger click and shows items', async () => {
    const user = setupUser()
    render(<BasicMenubar />)
    await user.click(screen.getByRole('menuitem', { name: 'File' }))
    expect(await screen.findByRole('menuitem', { name: 'New' })).toBeInTheDocument()
  })

  it('fires item onClick and closes the menu', async () => {
    const user = setupUser()
    const onNew = vi.fn()
    render(<BasicMenubar onNew={onNew} />)
    await user.click(screen.getByRole('menuitem', { name: 'File' }))
    await user.click(await screen.findByRole('menuitem', { name: 'New' }))
    expect(onNew).toHaveBeenCalledTimes(1)
    await waitFor(() => {
      expect(screen.queryByRole('menuitem', { name: 'New' })).toBeNull()
    })
  })

  it('closes the open menu on Escape', async () => {
    const user = setupUser()
    render(<BasicMenubar />)
    await user.click(screen.getByRole('menuitem', { name: 'File' }))
    await screen.findByRole('menuitem', { name: 'New' })
    await user.keyboard('{Escape}')
    await waitFor(() => {
      expect(screen.queryByRole('menuitem', { name: 'New' })).toBeNull()
    })
  })

  it('moves focus between triggers with arrow keys', async () => {
    const user = setupUser()
    render(<BasicMenubar />)
    const file = screen.getByRole('menuitem', { name: 'File' })
    file.focus()
    expect(file).toHaveFocus()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('menuitem', { name: 'Edit' })).toHaveFocus()
  })

  it('marks disabled items with data-disabled', async () => {
    const user = setupUser()
    render(<BasicMenubar />)
    await user.click(screen.getByRole('menuitem', { name: 'File' }))
    const disabled = await screen.findByRole('menuitem', { name: 'Disabled' })
    expect(disabled.getAttribute('data-disabled')).not.toBeNull()
  })

  it('has no a11y violations in the closed state', async () => {
    const { container } = render(<BasicMenubar />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
