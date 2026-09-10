import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { Alert, AlertAction, AlertDescription, AlertIcon, AlertTitle } from './alert'

const TITLE = 'System message'
const DESCRIPTION = 'This is a short informational message.'

function renderAlert(props: Partial<React.ComponentProps<typeof Alert>> = {}) {
  return render(
    <Alert {...props}>
      <AlertIcon>
        <span data-testid="icon">i</span>
      </AlertIcon>
      <AlertTitle>{TITLE}</AlertTitle>
      <AlertDescription>{DESCRIPTION}</AlertDescription>
      <AlertAction>
        <button type="button">Action</button>
      </AlertAction>
    </Alert>,
  )
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Alert', () => {
  it('renders with role="alert" and tags root with data-slot', () => {
    renderAlert()
    const root = screen.getByRole('alert')
    expect(root).toHaveAttribute('data-slot', 'alert')
    expect(root).toHaveAttribute('data-layout', 'block')
  })

  it('renders all sub-component slots', () => {
    renderAlert()
    expect(screen.getByTestId('icon')).toBeInTheDocument()
    expect(screen.getByText(TITLE)).toHaveAttribute('data-slot', 'alert-title')
    expect(screen.getByText(DESCRIPTION)).toHaveAttribute('data-slot', 'alert-description')
    expect(screen.getByRole('button', { name: 'Action' }).parentElement).toHaveAttribute('data-slot', 'alert-action')
  })

  it('applies variant + layout classes', () => {
    renderAlert({ variant: 'success', layout: 'inline' })
    const root = screen.getByRole('alert')
    expect(root.className).toContain('bg-success-subtle')
    expect(root.className).toContain('border-success-soft')
    expect(root).toHaveAttribute('data-layout', 'inline')
  })

  it.each([
    ['default', 'text-foreground-intense'],
    ['primary', 'text-primary'],
    ['secondary', 'text-secondary-emphasis'],
    ['error', 'text-error-emphasis'],
    ['success', 'text-success-emphasis'],
    ['warning', 'text-warning-emphasis'],
    ['info', 'text-info-emphasis'],
  ] as const)('AlertIcon picks up %s color from variant', (variant, expected) => {
    renderAlert({ variant })
    const icon = screen.getByTestId('icon').parentElement
    expect(icon).toHaveAttribute('data-slot', 'alert-icon')
    expect(icon?.className).toContain(expected)
  })

  it('does not render the close button unless dismissible', () => {
    renderAlert()
    expect(screen.queryByRole('button', { name: 'Dismiss' })).toBeNull()
  })

  it('renders the close button when dismissible and removes the alert on click', async () => {
    const user = userEvent.setup()
    renderAlert({ dismissible: true })

    const close = screen.getByRole('button', { name: 'Dismiss' })
    expect(close).toHaveAttribute('data-slot', 'alert-close')

    await user.click(close)
    await waitFor(() => {
      expect(screen.queryByRole('alert')).toBeNull()
    })
  })

  it('honors a custom closeLabel', () => {
    renderAlert({ dismissible: true, closeLabel: 'Close banner' })
    expect(screen.getByRole('button', { name: 'Close banner' })).toBeInTheDocument()
  })

  it('fires onOpenChange(false) when dismissed', async () => {
    const onOpenChange = vi.fn()
    const user = userEvent.setup()
    renderAlert({ dismissible: true, onOpenChange })

    await user.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('respects controlled `open` prop', async () => {
    const onOpenChange = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(
      <Alert dismissible open onOpenChange={onOpenChange}>
        <AlertTitle>{TITLE}</AlertTitle>
      </Alert>,
    )

    await user.click(screen.getByRole('button', { name: 'Dismiss' }))
    // Controlled: still visible because parent didn't flip `open`.
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(onOpenChange).toHaveBeenCalledWith(false)

    rerender(
      <Alert dismissible open={false} onOpenChange={onOpenChange}>
        <AlertTitle>{TITLE}</AlertTitle>
      </Alert>,
    )
    await waitFor(() => {
      expect(screen.queryByRole('alert')).toBeNull()
    })
  })

  it('persists dismissal via persistKey across remounts (localStorage)', async () => {
    const user = userEvent.setup()
    const { unmount } = renderAlert({ dismissible: true, persistKey: 'test-banner' })

    // Mounted alerts wait one tick for hydration before becoming interactive.
    const close = await screen.findByRole('button', { name: 'Dismiss' })
    await user.click(close)
    await waitFor(() => {
      expect(screen.queryByRole('alert')).toBeNull()
    })

    unmount()
    renderAlert({ dismissible: true, persistKey: 'test-banner' })

    // Storage says dismissed → alert should not appear after hydration tick.
    await new Promise((r) => setTimeout(r, 10))
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('does not persist when persistKey is omitted', async () => {
    const user = userEvent.setup()
    const { unmount } = renderAlert({ dismissible: true })

    await user.click(screen.getByRole('button', { name: 'Dismiss' }))
    await waitFor(() => {
      expect(screen.queryByRole('alert')).toBeNull()
    })

    unmount()
    renderAlert({ dismissible: true })
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('forwards className on root and sub-components', () => {
    render(
      <Alert className="root-extra" variant="error">
        <AlertIcon className="icon-extra">i</AlertIcon>
        <AlertTitle className="title-extra">{TITLE}</AlertTitle>
        <AlertDescription className="desc-extra">{DESCRIPTION}</AlertDescription>
        <AlertAction className="action-extra">
          <button type="button">A</button>
        </AlertAction>
      </Alert>,
    )

    expect(screen.getByRole('alert').className).toContain('root-extra')
    expect(screen.getByText('i').className).toContain('icon-extra')
    expect(screen.getByText(TITLE).className).toContain('title-extra')
    expect(screen.getByText(DESCRIPTION).className).toContain('desc-extra')
    expect(screen.getByRole('button', { name: 'A' }).parentElement?.className).toContain('action-extra')
  })

  it.each(['default', 'primary', 'secondary', 'error', 'success', 'warning', 'info'] as const)(
    '%s variant has no accessibility violations',
    async (variant) => {
      const { container } = renderAlert({ variant, dismissible: true })
      expect(await axe(container)).toHaveNoViolations()
    },
  )
})
