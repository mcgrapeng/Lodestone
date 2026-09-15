import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'
import { Button } from '../button/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './tooltip'

function renderTooltip(
  content = 'Add to library',
  { side, delay }: { side?: 'top' | 'bottom' | 'left' | 'right'; delay?: number } = {},
) {
  return render(
    <TooltipProvider delay={delay ?? 0}>
      <Tooltip>
        <TooltipTrigger render={<Button variant="outline">Hover</Button>} />
        <TooltipContent side={side}>
          <p>{content}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>,
  )
}

describe('Tooltip', () => {
  it('renders the trigger and tags it with data-slot', () => {
    renderTooltip()
    const trigger = screen.getByRole('button', { name: 'Hover' })
    expect(trigger.getAttribute('data-slot')).toBe('tooltip-trigger')
  })

  it('does not render content before hover', () => {
    renderTooltip('Hidden until hover')
    expect(screen.queryByText('Hidden until hover')).toBeNull()
  })

  it('shows content on hover and hides on unhover', async () => {
    const user = userEvent.setup()
    renderTooltip('Add to library')

    await user.hover(screen.getByRole('button', { name: 'Hover' }))
    const content = await screen.findByText('Add to library')
    expect(content).toBeTruthy()
    const popup = content.closest('[data-slot="tooltip-content"]') as HTMLElement
    expect(popup).not.toBeNull()
    expect(popup.className).toContain('bg-background-inverse')
    expect(popup.className).toContain('text-foreground-inverse')
    expect(popup.className).toContain('rounded-xs')
    expect(popup.className).toContain('text-xs')

    await user.unhover(screen.getByRole('button', { name: 'Hover' }))
    await waitFor(() => {
      expect(screen.queryByText('Add to library')).toBeNull()
    })
  })

  it('renders the arrow inside the popup with rotated-square classes', async () => {
    const user = userEvent.setup()
    renderTooltip()
    await user.hover(screen.getByRole('button', { name: 'Hover' }))

    await screen.findByText('Add to library')
    // Popup is portaled - query at document level.
    const arrow = document.querySelector('[data-slot="tooltip-arrow"]') as HTMLElement | null
    expect(arrow).not.toBeNull()
    expect(arrow!.className).toContain('size-2.5')
    expect(arrow!.className).toContain('rotate-45')
    expect(arrow!.className).toContain('bg-background-inverse')
  })

  it('omits the arrow when arrow is false', async () => {
    const user = userEvent.setup()
    render(
      <TooltipProvider delay={0}>
        <Tooltip>
          <TooltipTrigger render={<Button variant="outline">Hover</Button>} />
          <TooltipContent arrow={false}>
            <p>No arrow here.</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    )

    await user.hover(screen.getByRole('button', { name: 'Hover' }))
    await screen.findByText('No arrow here.')

    expect(document.querySelector('[data-slot="tooltip-arrow"]')).toBeNull()
  })

  it('shows on focus (keyboard)', async () => {
    const user = userEvent.setup()
    renderTooltip('Keyboard-visible')
    await user.tab()
    expect(await screen.findByText('Keyboard-visible')).toBeTruthy()
  })

  it('has no accessibility violations (closed state)', async () => {
    const { container } = renderTooltip()
    expect(await axe(container)).toHaveNoViolations()
  })
})
