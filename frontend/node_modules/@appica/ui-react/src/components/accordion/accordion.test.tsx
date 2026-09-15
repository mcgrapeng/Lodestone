import * as React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from './accordion'

function Basic({
  defaultValue,
  disabled,
  multiple,
  itemDisabled,
}: {
  defaultValue?: string[]
  disabled?: boolean
  multiple?: boolean
  itemDisabled?: boolean
} = {}) {
  return (
    <Accordion defaultValue={defaultValue} disabled={disabled} multiple={multiple}>
      <AccordionItem value="one" disabled={itemDisabled}>
        <AccordionTrigger>First</AccordionTrigger>
        <AccordionContent>
          <p>First body</p>
        </AccordionContent>
      </AccordionItem>
      <AccordionItem value="two">
        <AccordionTrigger>Second</AccordionTrigger>
        <AccordionContent>
          <p>Second body</p>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}

describe('Accordion', () => {
  it('renders trigger with data-slot', () => {
    render(<Basic />)
    const trigger = screen.getByRole('button', { name: 'First' })
    expect(trigger).toHaveAttribute('data-slot', 'accordion-trigger')
  })

  it('defaults closed: panels not in the DOM', () => {
    render(<Basic />)
    expect(screen.queryByText('First body')).toBeNull()
    expect(screen.queryByText('Second body')).toBeNull()
  })

  it('opens on trigger click and closes on a second click', async () => {
    const user = userEvent.setup()
    render(<Basic />)
    const trigger = screen.getByRole('button', { name: 'First' })

    await user.click(trigger)
    const panel = await screen.findByText('First body')
    expect(panel.closest('[data-slot="accordion-content"]')).not.toBeNull()
    expect(trigger).toHaveAttribute('data-panel-open')

    await user.click(trigger)
    await waitFor(() => {
      expect(screen.queryByText('First body')).toBeNull()
    })
  })

  it('respects defaultValue', () => {
    render(<Basic defaultValue={['two']} />)
    expect(screen.getByText('Second body')).toBeInTheDocument()
    expect(screen.queryByText('First body')).toBeNull()
  })

  it('disabled root prevents toggling and reflects data-disabled', async () => {
    const user = userEvent.setup()
    render(<Basic disabled />)
    const trigger = screen.getByRole('button', { name: 'First' })
    expect(trigger.getAttribute('data-disabled')).not.toBeNull()
    await user.click(trigger)
    expect(screen.queryByText('First body')).toBeNull()
  })

  it('disabled item prevents toggling for that item only', async () => {
    const user = userEvent.setup()
    render(<Basic itemDisabled />)
    const first = screen.getByRole('button', { name: 'First' })
    const second = screen.getByRole('button', { name: 'Second' })
    expect(first.getAttribute('data-disabled')).not.toBeNull()
    await user.click(first)
    expect(screen.queryByText('First body')).toBeNull()
    await user.click(second)
    await screen.findByText('Second body')
  })

  it('single mode: opening a second item closes the first', async () => {
    const user = userEvent.setup()
    render(<Basic />)
    await user.click(screen.getByRole('button', { name: 'First' }))
    await screen.findByText('First body')
    await user.click(screen.getByRole('button', { name: 'Second' }))
    await screen.findByText('Second body')
    await waitFor(() => {
      expect(screen.queryByText('First body')).toBeNull()
    })
  })

  it('multiple mode: both panels can be open at once', async () => {
    const user = userEvent.setup()
    render(<Basic multiple />)
    await user.click(screen.getByRole('button', { name: 'First' }))
    await user.click(screen.getByRole('button', { name: 'Second' }))
    await screen.findByText('First body')
    await screen.findByText('Second body')
  })

  it('controlled mode: onValueChange fires with the next value array', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn()

    function Controlled() {
      const [value, setValue] = React.useState<string[]>([])
      return (
        <Accordion
          value={value}
          onValueChange={(next, details) => {
            onValueChange(next, details)
            setValue(next as string[])
          }}
        >
          <AccordionItem value="one">
            <AccordionTrigger>Toggle</AccordionTrigger>
            <AccordionContent>
              <p>Panel body</p>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      )
    }

    render(<Controlled />)
    await user.click(screen.getByRole('button', { name: 'Toggle' }))
    expect(onValueChange).toHaveBeenCalledTimes(1)
    expect(onValueChange).toHaveBeenLastCalledWith(['one'], expect.anything())
    await screen.findByText('Panel body')
  })

  it('forwards className on each part', async () => {
    const user = userEvent.setup()
    render(
      <Accordion className="root-cls">
        <AccordionItem value="one" className="item-cls">
          <AccordionTrigger className="trigger-cls">Toggle</AccordionTrigger>
          <AccordionContent className="content-cls">
            <p>Panel body</p>
          </AccordionContent>
        </AccordionItem>
      </Accordion>,
    )

    const root = screen.getByRole('button', { name: 'Toggle' }).closest('[data-slot="accordion"]') as HTMLElement
    expect(root.className).toContain('root-cls')

    const item = screen.getByRole('button', { name: 'Toggle' }).closest('[data-slot="accordion-item"]') as HTMLElement
    expect(item.className).toContain('item-cls')

    const trigger = screen.getByRole('button', { name: 'Toggle' })
    expect(trigger.className).toContain('trigger-cls')
    expect(trigger.className).toContain('cursor-pointer')

    await user.click(trigger)
    const panel = (await screen.findByText('Panel body')).closest('[data-slot="accordion-content"]') as HTMLElement
    expect(panel.className).toContain('content-cls')
    expect(panel.className).toContain('overflow-hidden')
  })

  it('icon={false} renders no icon SVG', () => {
    render(
      <Accordion icon={false}>
        <AccordionItem value="one">
          <AccordionTrigger>No icon</AccordionTrigger>
          <AccordionContent>body</AccordionContent>
        </AccordionItem>
      </Accordion>,
    )
    const trigger = screen.getByRole('button', { name: 'No icon' })
    expect(trigger.querySelector('[data-slot="accordion-icon"]')).toBeNull()
  })

  it('iconVariant="icon-box" wraps the icon in a styled box', () => {
    render(
      <Accordion iconVariant="icon-box">
        <AccordionItem value="one">
          <AccordionTrigger>Boxed</AccordionTrigger>
          <AccordionContent>body</AccordionContent>
        </AccordionItem>
      </Accordion>,
    )
    const trigger = screen.getByRole('button', { name: 'Boxed' })
    const box = trigger.querySelector('[data-slot="accordion-trigger-icon-box"]')
    expect(box).not.toBeNull()
    expect(box?.querySelector('[data-slot="accordion-icon"]')).not.toBeNull()
  })

  it('iconPosition="start" renders the icon before the children', () => {
    render(
      <Accordion iconPosition="start">
        <AccordionItem value="one">
          <AccordionTrigger>Label</AccordionTrigger>
          <AccordionContent>body</AccordionContent>
        </AccordionItem>
      </Accordion>,
    )
    const trigger = screen.getByRole('button', { name: 'Label' })
    const firstChild = trigger.firstElementChild
    expect(firstChild?.querySelector('[data-slot="accordion-icon"]')).not.toBeNull()
  })

  it('has no a11y violations when open', async () => {
    const { container } = render(<Basic defaultValue={['one']} />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
