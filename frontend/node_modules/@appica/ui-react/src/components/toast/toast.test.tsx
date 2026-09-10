import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'
import {
  Toast,
  ToastAction,
  ToastActions,
  ToastClose,
  ToastDescription,
  ToastIcon,
  ToastProgress,
  ToastProvider,
  ToastTitle,
  ToastViewport,
  Toaster,
  useToastManager,
  type ToastPosition,
} from './toast'

afterEach(() => {
  vi.restoreAllMocks()
})

type AddOptions = Parameters<ReturnType<typeof useToastManager<{ icon?: React.ReactNode }>>['add']>[0]

function Trigger({ options, label = 'Show toast' }: { options: AddOptions; label?: string }) {
  const { add } = useToastManager<{ icon?: React.ReactNode }>()
  return (
    <button type="button" onClick={() => add(options)}>
      {label}
    </button>
  )
}

function renderToasterSandbox({
  options,
  position,
  progress,
}: {
  options: AddOptions
  position?: ToastPosition
  progress?: boolean
}) {
  // Spread props only when defined - passing an explicit `undefined`
  // violates exactOptionalPropertyTypes (enabled in the root tsconfig).
  const toasterProps = {
    ...(position !== undefined ? { position } : {}),
    ...(progress !== undefined ? { progress } : {}),
  }
  return render(
    <ToastProvider>
      <Trigger options={options} />
      <Toaster {...toasterProps} />
    </ToastProvider>,
  )
}

async function showToast(user: ReturnType<typeof userEvent.setup>, label = 'Show toast') {
  await user.click(screen.getByRole('button', { name: label }))
}

describe('Toast (via Toaster)', () => {
  it('renders title and description after add()', async () => {
    const user = userEvent.setup()
    renderToasterSandbox({ options: { title: 'Hello', description: 'World' } })
    await showToast(user)
    expect(await screen.findByText('Hello')).toBeInTheDocument()
    expect(screen.getByText('World')).toBeInTheDocument()
  })

  it('tags every sub-component with a data-slot attribute', async () => {
    const user = userEvent.setup()
    renderToasterSandbox({
      options: {
        title: 'Title',
        description: 'Desc',
        data: { icon: <span data-testid="icon">i</span> },
        actionProps: { children: 'Do it' },
      },
    })
    await showToast(user)
    await screen.findByText('Title')

    expect(document.querySelector('[data-slot="toast-viewport"]')).not.toBeNull()
    expect(document.querySelector('[data-slot="toast"]')).not.toBeNull()
    expect(document.querySelector('[data-slot="toast-icon"]')).not.toBeNull()
    expect(document.querySelector('[data-slot="toast-title"]')).not.toBeNull()
    expect(document.querySelector('[data-slot="toast-description"]')).not.toBeNull()
    expect(document.querySelector('[data-slot="toast-actions"]')).not.toBeNull()
    expect(document.querySelector('[data-slot="toast-action"]')).not.toBeNull()
    expect(document.querySelector('[data-slot="toast-close"]')).not.toBeNull()
  })

  it('renders the close button by default and removes the toast on click', async () => {
    const user = userEvent.setup()
    renderToasterSandbox({ options: { title: 'Goodbye' } })
    await showToast(user)
    await screen.findByText('Goodbye')
    // Base UI sets aria-hidden on Toast.Close until the viewport is expanded
    // (focused/hovered). Query by data-slot to bypass the a11y-tree filter.
    const close = document.querySelector<HTMLButtonElement>('[data-slot="toast-close"]')
    expect(close).not.toBeNull()
    expect(close).toHaveAttribute('aria-label', 'Dismiss')

    await user.click(close!)
    await waitFor(() => {
      expect(screen.queryByText('Goodbye')).toBeNull()
    })
  })

  it('renders a progress bar when timeout > 0 and progress is enabled', async () => {
    const user = userEvent.setup()
    renderToasterSandbox({ options: { title: 'With progress', timeout: 10000 }, progress: true })
    await showToast(user)
    await screen.findByText('With progress')
    expect(document.querySelector('[data-slot="toast-progress"]')).not.toBeNull()
  })

  it('renders a progress bar for a default-timeout toast when progress is enabled', async () => {
    const user = userEvent.setup()
    renderToasterSandbox({ options: { title: 'Default timeout' }, progress: true })
    await showToast(user)
    await screen.findByText('Default timeout')
    expect(document.querySelector('[data-slot="toast-progress"]')).not.toBeNull()
  })

  it('does not render a progress bar by default (progress is opt-in)', async () => {
    const user = userEvent.setup()
    renderToasterSandbox({ options: { title: 'No bar', timeout: 10000 } })
    await showToast(user)
    await screen.findByText('No bar')
    expect(document.querySelector('[data-slot="toast-progress"]')).toBeNull()
  })

  it('omits the progress bar when timeout is 0 even if progress is enabled', async () => {
    const user = userEvent.setup()
    renderToasterSandbox({ options: { title: 'No progress', timeout: 0 }, progress: true })
    await showToast(user)
    await screen.findByText('No progress')
    expect(document.querySelector('[data-slot="toast-progress"]')).toBeNull()
  })

  it.each<ToastPosition>(['top-left', 'top-center', 'top-right', 'bottom-left', 'bottom-center', 'bottom-right'])(
    'applies position="%s" to viewport and toast root',
    async (position) => {
      const user = userEvent.setup()
      renderToasterSandbox({ options: { title: `pos-${position}` }, position })
      await showToast(user)
      await screen.findByText(`pos-${position}`)
      const viewport = document.querySelector('[data-slot="toast-viewport"]')
      const root = document.querySelector('[data-slot="toast"]')
      expect(viewport).toHaveAttribute('data-position', position)
      expect(root).toHaveAttribute('data-position', position)
    },
  )

  it('fires actionProps.onClick when ToastAction is clicked', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    renderToasterSandbox({
      options: { title: 'A', actionProps: { children: 'Run', onClick } },
    })
    await showToast(user)
    const action = await screen.findByRole('button', { name: 'Run' })
    await user.click(action)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('renders multiple toasts when add is called more than once', async () => {
    const user = userEvent.setup()
    function MultiTrigger() {
      const { add } = useToastManager()
      return (
        <button type="button" onClick={() => add({ title: `Toast ${Date.now()}` })}>
          Show toast
        </button>
      )
    }
    render(
      <ToastProvider>
        <MultiTrigger />
        <Toaster />
      </ToastProvider>,
    )
    await showToast(user)
    await showToast(user)
    await waitFor(() => {
      expect(document.querySelectorAll('[data-slot="toast"]')).toHaveLength(2)
    })
  })

  it('has no accessibility violations once a toast is shown', async () => {
    const user = userEvent.setup()
    const { container } = renderToasterSandbox({
      options: {
        title: 'Accessible',
        description: 'Body',
        actionProps: { children: 'Action' },
      },
    })
    await showToast(user)
    await screen.findByText('Accessible')
    expect(await axe(container)).toHaveNoViolations()
  })
})

describe('Toast primitives (manual composition)', () => {
  function ManualList() {
    const { toasts } = useToastManager<{ icon?: React.ReactNode }>()
    return (
      <ToastViewport position="top-left">
        {toasts.map((toast) => (
          <Toast key={toast.id} toast={toast} dismissible={false}>
            {toast.data?.icon ? <ToastIcon>{toast.data.icon}</ToastIcon> : null}
            <ToastTitle>{toast.title}</ToastTitle>
            {toast.description ? <ToastDescription>{toast.description}</ToastDescription> : null}
            <ToastActions>
              <ToastAction variant="soft">Cancel</ToastAction>
              <ToastAction variant="primary">Save</ToastAction>
            </ToastActions>
            <ToastClose closeLabel="Close" />
          </Toast>
        ))}
      </ToastViewport>
    )
  }

  it('honors explicit position on ToastViewport and renders multiple actions', async () => {
    const user = userEvent.setup()
    render(
      <ToastProvider>
        <Trigger options={{ title: 'Manual' }} />
        <ManualList />
      </ToastProvider>,
    )
    await showToast(user)
    await screen.findByText('Manual')

    expect(document.querySelector('[data-slot="toast-viewport"]')).toHaveAttribute('data-position', 'top-left')
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveAttribute('data-slot', 'toast-action')
    expect(screen.getByRole('button', { name: 'Save' })).toHaveAttribute('data-slot', 'toast-action')
    // Toast.Close is aria-hidden until the viewport is expanded; query past the a11y tree.
    const close = document.querySelector('[data-slot="toast-close"]')
    expect(close).not.toBeNull()
    expect(close).toHaveAttribute('aria-label', 'Close')
  })

  it('forwards className on root and sub-components', async () => {
    function CustomList() {
      const { toasts } = useToastManager()
      return (
        <ToastViewport className="vp-extra">
          {toasts.map((toast) => (
            <Toast key={toast.id} toast={toast} dismissible={false} className="root-extra">
              <ToastTitle className="title-extra">{toast.title}</ToastTitle>
              <ToastDescription className="desc-extra">{toast.description}</ToastDescription>
            </Toast>
          ))}
        </ToastViewport>
      )
    }
    const user = userEvent.setup()
    render(
      <ToastProvider>
        <Trigger options={{ title: 'T', description: 'D' }} />
        <CustomList />
      </ToastProvider>,
    )
    await showToast(user)
    await screen.findByText('T')
    expect(document.querySelector('[data-slot="toast-viewport"]')?.className).toContain('vp-extra')
    expect(document.querySelector('[data-slot="toast"]')?.className).toContain('root-extra')
    expect(screen.getByText('T').className).toContain('title-extra')
    expect(screen.getByText('D').className).toContain('desc-extra')
  })
})
