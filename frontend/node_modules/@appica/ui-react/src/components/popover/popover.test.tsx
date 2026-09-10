import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'
import { Button } from '../button/button'
import { Popover, PopoverClose, PopoverContent, PopoverDescription, PopoverTitle, PopoverTrigger } from './popover'

function renderPopover({
  side,
  title = 'Notifications',
  description = 'You are all caught up.',
}: {
  side?: 'top' | 'bottom' | 'left' | 'right'
  title?: string
  description?: string
} = {}) {
  return render(
    <Popover>
      <PopoverTrigger render={<Button variant="outline">Open</Button>} />
      <PopoverContent side={side}>
        <PopoverTitle>{title}</PopoverTitle>
        <PopoverDescription>{description}</PopoverDescription>
        <PopoverClose render={<Button>Dismiss</Button>} />
      </PopoverContent>
    </Popover>,
  )
}

describe('Popover', () => {
  it('renders the trigger and tags it with data-slot', () => {
    renderPopover()
    const trigger = screen.getByRole('button', { name: 'Open' })
    expect(trigger.getAttribute('data-slot')).toBe('popover-trigger')
  })

  it('does not render content before being opened', () => {
    renderPopover({ description: 'Hidden until click' })
    expect(screen.queryByText('Hidden until click')).toBeNull()
  })

  it('keeps the content mounted while closed when keepMounted is set', () => {
    render(
      <Popover>
        <PopoverTrigger render={<Button variant="outline">Open</Button>} />
        <PopoverContent keepMounted>
          <PopoverDescription>Always in the DOM</PopoverDescription>
        </PopoverContent>
      </Popover>,
    )
    // Never opened, yet present in the DOM (hidden) so a consumer's animated
    // content doesn't re-mount - and re-animate - on every open.
    expect(document.querySelector('[data-slot="popover-content"]')).not.toBeNull()
    expect(screen.getByText('Always in the DOM')).toBeInTheDocument()
  })

  it('opens on click and closes on outside click', async () => {
    const user = userEvent.setup()
    renderPopover()

    await user.click(screen.getByRole('button', { name: 'Open' }))
    const description = await screen.findByText('You are all caught up.')
    expect(description).toBeTruthy()

    const popup = description.closest('[data-slot="popover-content"]') as HTMLElement
    expect(popup).not.toBeNull()
    expect(popup.className).toContain('bg-background')
    expect(popup.className).toContain('rounded-xl')
    expect(popup.className).toContain('border-border-overlay')

    await user.click(document.body)
    await waitFor(() => {
      expect(screen.queryByText('You are all caught up.')).toBeNull()
    })
  })

  it('closes when PopoverClose is clicked', async () => {
    const user = userEvent.setup()
    renderPopover()

    await user.click(screen.getByRole('button', { name: 'Open' }))
    await screen.findByText('You are all caught up.')

    await user.click(screen.getByRole('button', { name: 'Dismiss' }))
    await waitFor(() => {
      expect(screen.queryByText('You are all caught up.')).toBeNull()
    })
  })

  it('renders the title with intense foreground styles', async () => {
    const user = userEvent.setup()
    renderPopover({ title: 'Heading' })
    await user.click(screen.getByRole('button', { name: 'Open' }))

    const title = await screen.findByText('Heading')
    expect(title.getAttribute('data-slot')).toBe('popover-title')
    expect(title.className).toContain('text-foreground-intense')
    expect(title.className).toContain('font-semibold')
  })

  it('renders the arrow svg inside the popup', async () => {
    const user = userEvent.setup()
    renderPopover()
    await user.click(screen.getByRole('button', { name: 'Open' }))
    await screen.findByText('You are all caught up.')

    const arrow = document.querySelector('[data-slot="popover-arrow"]') as HTMLElement | null
    expect(arrow).not.toBeNull()
    expect(arrow!.querySelector('svg')).not.toBeNull()
  })

  it('omits the arrow and the thicker side border when arrow is false', async () => {
    const user = userEvent.setup()
    render(
      <Popover>
        <PopoverTrigger render={<Button variant="outline">Open</Button>} />
        <PopoverContent arrow={false}>
          <PopoverDescription>No arrow here.</PopoverDescription>
        </PopoverContent>
      </Popover>,
    )

    await user.click(screen.getByRole('button', { name: 'Open' }))
    const description = await screen.findByText('No arrow here.')

    expect(document.querySelector('[data-slot="popover-arrow"]')).toBeNull()

    const popup = description.closest('[data-slot="popover-content"]') as HTMLElement
    expect(popup.className).not.toMatch(/border-[a-z]-2/)
  })

  it('has no accessibility violations (closed state)', async () => {
    const { container } = renderPopover()
    expect(await axe(container)).toHaveNoViolations()
  })
})
