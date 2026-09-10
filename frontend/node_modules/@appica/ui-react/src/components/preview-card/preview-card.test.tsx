import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'
import { PreviewCard, PreviewCardContent, PreviewCardTrigger } from './preview-card'

function renderPreviewCard({
  side,
  body = 'A short preview of the linked page.',
}: {
  side?: 'top' | 'bottom' | 'left' | 'right'
  body?: string
} = {}) {
  return render(
    <PreviewCard>
      <PreviewCardTrigger href="https://example.com" delay={0} closeDelay={0}>
        example.com
      </PreviewCardTrigger>
      <PreviewCardContent side={side}>
        <p>{body}</p>
      </PreviewCardContent>
    </PreviewCard>,
  )
}

describe('PreviewCard', () => {
  it('renders the trigger as a link tagged with data-slot', () => {
    renderPreviewCard()
    const trigger = screen.getByRole('link', { name: 'example.com' })
    expect(trigger.getAttribute('data-slot')).toBe('preview-card-trigger')
  })

  it('does not render content before hover', () => {
    renderPreviewCard({ body: 'Hidden until hover' })
    expect(screen.queryByText('Hidden until hover')).toBeNull()
  })

  it('shows content on hover and hides on unhover', async () => {
    const user = userEvent.setup()
    renderPreviewCard()

    const trigger = screen.getByRole('link', { name: 'example.com' })
    await user.hover(trigger)

    const body = await screen.findByText('A short preview of the linked page.')
    const popup = body.closest('[data-slot="preview-card-content"]') as HTMLElement
    expect(popup).not.toBeNull()
    expect(popup.className).toContain('bg-background')
    expect(popup.className).toContain('rounded-xl')
    expect(popup.className).toContain('border-border-overlay')

    await user.unhover(trigger)
    await waitFor(() => {
      expect(screen.queryByText('A short preview of the linked page.')).toBeNull()
    })
  })

  it('renders the arrow svg inside the popup', async () => {
    const user = userEvent.setup()
    renderPreviewCard()
    await user.hover(screen.getByRole('link', { name: 'example.com' }))
    await screen.findByText('A short preview of the linked page.')

    const arrow = document.querySelector('[data-slot="preview-card-arrow"]') as HTMLElement | null
    expect(arrow).not.toBeNull()
    expect(arrow!.querySelector('svg')).not.toBeNull()
  })

  it('omits the arrow and the thicker side border when arrow is false', async () => {
    const user = userEvent.setup()
    render(
      <PreviewCard>
        <PreviewCardTrigger href="https://example.com" delay={0} closeDelay={0}>
          link
        </PreviewCardTrigger>
        <PreviewCardContent arrow={false}>
          <p>No arrow here.</p>
        </PreviewCardContent>
      </PreviewCard>,
    )

    await user.hover(screen.getByRole('link', { name: 'link' }))
    const body = await screen.findByText('No arrow here.')

    expect(document.querySelector('[data-slot="preview-card-arrow"]')).toBeNull()

    const popup = body.closest('[data-slot="preview-card-content"]') as HTMLElement
    expect(popup.className).not.toMatch(/border-[a-z]-2/)
  })

  it('exposes createHandle for detached trigger patterns', () => {
    expect(typeof PreviewCard.createHandle).toBe('function')
  })

  it('has no accessibility violations (closed state)', async () => {
    const { container } = renderPreviewCard()
    expect(await axe(container)).toHaveNoViolations()
  })
})
