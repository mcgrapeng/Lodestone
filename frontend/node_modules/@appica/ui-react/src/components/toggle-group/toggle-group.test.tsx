import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { ToggleGroup } from './toggle-group'
import { Toggle } from '../toggle/toggle'

function renderGroup(props: React.ComponentProps<typeof ToggleGroup> = {}) {
  return render(
    <ToggleGroup aria-label="Text alignment" {...props}>
      <Toggle value="left" aria-label="Left">
        L
      </Toggle>
      <Toggle value="center" aria-label="Center">
        C
      </Toggle>
      <Toggle value="right" aria-label="Right">
        R
      </Toggle>
    </ToggleGroup>,
  )
}

describe('ToggleGroup', () => {
  it('renders a group with its toggles', () => {
    renderGroup()
    const group = screen.getByRole('group', { name: 'Text alignment' })
    expect(group).toHaveAttribute('data-slot', 'toggle-group')
    expect(screen.getAllByRole('button')).toHaveLength(3)
  })

  it('reflects defaultValue as pressed', () => {
    renderGroup({ defaultValue: ['center'] })
    expect(screen.getByRole('button', { name: 'Center' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Left' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('single-select deselects the previous toggle', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn()
    renderGroup({ defaultValue: ['left'], onValueChange })

    await user.click(screen.getByRole('button', { name: 'Right' }))
    expect(onValueChange).toHaveBeenLastCalledWith(['right'], expect.anything())
    expect(screen.getByRole('button', { name: 'Left' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'Right' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('multiple-select keeps several toggles pressed', async () => {
    const user = userEvent.setup()
    renderGroup({ multiple: true })

    await user.click(screen.getByRole('button', { name: 'Left' }))
    await user.click(screen.getByRole('button', { name: 'Right' }))
    expect(screen.getByRole('button', { name: 'Left' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Right' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('navigates between toggles with arrow keys', async () => {
    const user = userEvent.setup()
    renderGroup()

    const left = screen.getByRole('button', { name: 'Left' })
    left.focus()
    expect(left).toHaveFocus()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('button', { name: 'Center' })).toHaveFocus()
  })

  it('disables all toggles when the group is disabled', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn()
    renderGroup({ disabled: true, onValueChange })

    await user.click(screen.getByRole('button', { name: 'Left' }))
    expect(onValueChange).not.toHaveBeenCalled()
  })

  it('applies vertical orientation', () => {
    renderGroup({ orientation: 'vertical' })
    const group = screen.getByRole('group', { name: 'Text alignment' })
    expect(group).toHaveAttribute('data-orientation', 'vertical')
    expect(group.className).toContain('data-[orientation=vertical]:flex-col')
  })

  it('forwards className', () => {
    renderGroup({ className: 'custom-class' })
    expect(screen.getByRole('group', { name: 'Text alignment' }).className).toContain('custom-class')
  })

  it('has no accessibility violations', async () => {
    const { container } = renderGroup({ defaultValue: ['left'] })
    expect(await axe(container)).toHaveNoViolations()
  })
})
