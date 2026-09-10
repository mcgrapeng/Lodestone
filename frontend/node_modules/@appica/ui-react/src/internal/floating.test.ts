import { describe, expect, it } from 'vitest'
import { splitFloatingProps } from './floating'

describe('splitFloatingProps', () => {
  it('routes positioner, portal, and popup props to the right bucket', () => {
    const { positioner, portal, popup } = splitFloatingProps({
      side: 'top',
      collisionPadding: 8,
      sticky: true,
      container: 'node',
      keepMounted: true,
      id: 'popup-1',
      role: 'dialog',
    })

    expect(positioner).toEqual({ side: 'top', collisionPadding: 8, sticky: true })
    expect(portal).toEqual({ container: 'node', keepMounted: true })
    expect(popup).toEqual({ id: 'popup-1', role: 'dialog' })
  })

  it('merges escape-hatch objects, with flat props winning over them', () => {
    const { positioner, portal } = splitFloatingProps({
      side: 'bottom',
      positionerProps: { side: 'top', style: { zIndex: 1 } },
      portalProps: { container: 'a' },
      keepMounted: true,
    })

    // flat `side` overrides positionerProps.side; non-flat keys are preserved
    expect(positioner).toEqual({ side: 'bottom', style: { zIndex: 1 } })
    expect(portal).toEqual({ container: 'a', keepMounted: true })
  })

  it('drops undefined flat props so defaults set before the spread survive', () => {
    const { positioner } = splitFloatingProps({ side: undefined, align: 'start' })

    expect('side' in positioner).toBe(false)
    expect(positioner).toEqual({ align: 'start' })
  })
})
