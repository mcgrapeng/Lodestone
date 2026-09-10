import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import { axe } from 'vitest-axe'
import { Toolbar, ToolbarButton, ToolbarGroup, ToolbarSeparator, ToolbarLink } from './toolbar'
import { Button } from '../button/button'

function renderToolbar(props: React.ComponentProps<typeof Toolbar> = {}) {
  return render(
    <Toolbar aria-label="Formatting" {...props}>
      <ToolbarGroup aria-label="Text style">
        <ToolbarButton render={<Button variant="ghost">Bold</Button>} />
        <ToolbarButton render={<Button variant="ghost">Italic</Button>} />
      </ToolbarGroup>
      <ToolbarSeparator />
      <ToolbarLink href="#help">Help</ToolbarLink>
    </Toolbar>,
  )
}

describe('Toolbar', () => {
  it('renders a toolbar with its items', () => {
    renderToolbar()
    const toolbar = screen.getByRole('toolbar', { name: 'Formatting' })
    expect(toolbar).toHaveAttribute('data-slot', 'toolbar')
    expect(screen.getByRole('group', { name: 'Text style' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Bold' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Help' })).toHaveAttribute('href', '#help')
  })

  it('composes ToolbarButton with Button via render', () => {
    renderToolbar()
    const bold = screen.getByRole('button', { name: 'Bold' })
    expect(bold.tagName).toBe('BUTTON')
    expect(bold.className).toContain('text-foreground-emphasis')
  })

  it('renders a separator flipped perpendicular to the toolbar', () => {
    renderToolbar()
    // Horizontal toolbar → vertical separator
    expect(screen.getByRole('separator')).toHaveAttribute('data-orientation', 'vertical')
  })

  it('moves focus between items with arrow keys (roving tabindex)', async () => {
    const user = userEvent.setup()
    renderToolbar()

    const bold = screen.getByRole('button', { name: 'Bold' })
    bold.focus()
    expect(bold).toHaveFocus()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('button', { name: 'Italic' })).toHaveFocus()
  })

  it('applies vertical orientation', () => {
    renderToolbar({ orientation: 'vertical' })
    const toolbar = screen.getByRole('toolbar', { name: 'Formatting' })
    expect(toolbar).toHaveAttribute('data-orientation', 'vertical')
    expect(toolbar.className).toContain('data-[orientation=vertical]:flex-col')
    // Vertical toolbar → horizontal separator
    expect(screen.getByRole('separator')).toHaveAttribute('data-orientation', 'horizontal')
  })

  it('disables items when the toolbar is disabled', () => {
    renderToolbar({ disabled: true })
    expect(screen.getByRole('button', { name: 'Bold' })).toHaveAttribute('data-disabled')
  })

  it('forwards className to the root', () => {
    renderToolbar({ className: 'custom-class' })
    expect(screen.getByRole('toolbar', { name: 'Formatting' }).className).toContain('custom-class')
  })

  it('has no accessibility violations', async () => {
    const { container } = renderToolbar()
    expect(await axe(container)).toHaveNoViolations()
  })
})
