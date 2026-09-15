import * as React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from './collapsible'

function Basic({
  defaultOpen,
  disabled,
  keepMounted,
}: { defaultOpen?: boolean; disabled?: boolean; keepMounted?: boolean } = {}) {
  return (
    <Collapsible defaultOpen={defaultOpen} disabled={disabled}>
      <CollapsibleTrigger>Toggle</CollapsibleTrigger>
      <CollapsibleContent keepMounted={keepMounted}>
        <p>Panel body</p>
      </CollapsibleContent>
    </Collapsible>
  )
}

describe('Collapsible', () => {
  it('renders trigger with data-slot', () => {
    render(<Basic />)
    const trigger = screen.getByRole('button', { name: 'Toggle' })
    expect(trigger).toHaveAttribute('data-slot', 'collapsible-trigger')
  })

  it('defaults closed: panel not in the DOM', () => {
    render(<Basic />)
    expect(screen.queryByText('Panel body')).toBeNull()
  })

  it('opens on trigger click and closes on a second click', async () => {
    const user = userEvent.setup()
    render(<Basic />)
    const trigger = screen.getByRole('button', { name: 'Toggle' })

    await user.click(trigger)
    const panel = await screen.findByText('Panel body')
    expect(panel.closest('[data-slot="collapsible-content"]')).not.toBeNull()
    expect(trigger).toHaveAttribute('data-panel-open')

    await user.click(trigger)
    await waitFor(() => {
      expect(screen.queryByText('Panel body')).toBeNull()
    })
  })

  it('respects defaultOpen', () => {
    render(<Basic defaultOpen />)
    expect(screen.getByText('Panel body')).toBeInTheDocument()
  })

  it('disabled prevents toggling', async () => {
    const user = userEvent.setup()
    render(<Basic disabled />)
    const trigger = screen.getByRole('button', { name: 'Toggle' })
    expect(trigger.getAttribute('data-disabled')).not.toBeNull()
    await user.click(trigger)
    expect(screen.queryByText('Panel body')).toBeNull()
  })

  it('keepMounted leaves the panel in the DOM when closed with data-closed', () => {
    render(<Basic keepMounted />)
    const panel = screen.getByText('Panel body').closest('[data-slot="collapsible-content"]') as HTMLElement
    expect(panel).not.toBeNull()
    expect(panel.getAttribute('data-closed')).not.toBeNull()
  })

  it('controlled mode: onOpenChange fires with the next open state', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()

    function Controlled() {
      const [open, setOpen] = React.useState(false)
      return (
        <Collapsible
          open={open}
          onOpenChange={(next, details) => {
            onOpenChange(next, details)
            setOpen(next)
          }}
        >
          <CollapsibleTrigger>Toggle</CollapsibleTrigger>
          <CollapsibleContent>
            <p>Panel body</p>
          </CollapsibleContent>
        </Collapsible>
      )
    }

    render(<Controlled />)
    await user.click(screen.getByRole('button', { name: 'Toggle' }))
    expect(onOpenChange).toHaveBeenCalledTimes(1)
    expect(onOpenChange).toHaveBeenLastCalledWith(true, expect.anything())
    await screen.findByText('Panel body')
  })

  it('forwards className on each part', async () => {
    const user = userEvent.setup()
    render(
      <Collapsible className="root-cls">
        <CollapsibleTrigger className="trigger-cls">Toggle</CollapsibleTrigger>
        <CollapsibleContent className="content-cls">
          <p>Panel body</p>
        </CollapsibleContent>
      </Collapsible>,
    )

    const trigger = screen.getByRole('button', { name: 'Toggle' })
    expect(trigger.className).toContain('trigger-cls')
    expect(trigger.className).toContain('cursor-pointer')

    await user.click(trigger)
    const panel = (await screen.findByText('Panel body')).closest('[data-slot="collapsible-content"]') as HTMLElement
    expect(panel.className).toContain('content-cls')
    expect(panel.className).toContain('overflow-hidden')
  })

  it('has no a11y violations when open', async () => {
    const { container } = render(<Basic defaultOpen />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
