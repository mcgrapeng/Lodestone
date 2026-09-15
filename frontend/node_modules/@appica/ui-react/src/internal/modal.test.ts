import { describe, expect, it } from 'vitest'
import { splitModalProps } from './modal'

describe('splitModalProps', () => {
  it('routes portal props to portal and everything else to popup', () => {
    const { portal, popup } = splitModalProps({
      container: 'node',
      keepMounted: true,
      id: 'dialog-1',
      role: 'dialog',
      initialFocus: 'ref',
    })

    expect(portal).toEqual({ container: 'node', keepMounted: true })
    expect(popup).toEqual({ id: 'dialog-1', role: 'dialog', initialFocus: 'ref' })
  })

  it('merges portalProps, with flat portal props winning over it', () => {
    const { portal } = splitModalProps({
      container: 'flat-node',
      portalProps: { container: 'object-node', keepMounted: false },
    })

    expect(portal).toEqual({ container: 'flat-node', keepMounted: false })
  })

  it('drops undefined flat portal props', () => {
    const { portal, popup } = splitModalProps({ container: undefined, keepMounted: true, id: 'x' })

    expect('container' in portal).toBe(false)
    expect(portal).toEqual({ keepMounted: true })
    expect(popup).toEqual({ id: 'x' })
  })
})
