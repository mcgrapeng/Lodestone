import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { Pagination, PaginationList, PaginationItem, PaginationLink, PaginationEllipsis } from './pagination'

function renderBasic(props?: React.ComponentProps<typeof Pagination>) {
  return render(
    <Pagination {...props}>
      <PaginationList>
        <PaginationItem>
          <PaginationLink href="#prev" aria-label="Go to previous page">
            Prev
          </PaginationLink>
        </PaginationItem>
        <PaginationItem>
          <PaginationLink href="#1">1</PaginationLink>
        </PaginationItem>
        <PaginationItem>
          <PaginationLink href="#2" active>
            2
          </PaginationLink>
        </PaginationItem>
        <PaginationItem>
          <PaginationLink href="#3">3</PaginationLink>
        </PaginationItem>
        <PaginationItem>
          <PaginationEllipsis />
        </PaginationItem>
        <PaginationItem>
          <PaginationLink href="#next" aria-label="Go to next page">
            Next
          </PaginationLink>
        </PaginationItem>
      </PaginationList>
    </Pagination>,
  )
}

describe('Pagination', () => {
  it('renders a nav with pagination role and label', () => {
    renderBasic()
    const nav = screen.getByRole('navigation', { name: 'pagination' })
    expect(nav.tagName).toBe('NAV')
    expect(nav).toHaveAttribute('data-slot', 'pagination')
  })

  it('renders content as a ul and items as li', () => {
    renderBasic()
    const list = screen.getByRole('list')
    expect(list.tagName).toBe('UL')
    expect(list).toHaveAttribute('data-slot', 'pagination-list')
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(6)
  })

  it('marks the active link with aria-current and data-active', () => {
    renderBasic()
    const active = screen.getByRole('link', { current: 'page' })
    expect(active).toHaveTextContent('2')
    expect(active).toHaveAttribute('data-active')
  })

  it('marks disabled links with aria-disabled and data-disabled', () => {
    render(
      <Pagination>
        <PaginationList>
          <PaginationItem>
            <PaginationLink href="#" disabled aria-label="Previous">
              Prev
            </PaginationLink>
          </PaginationItem>
        </PaginationList>
      </Pagination>,
    )
    const link = screen.getByRole('link', { name: 'Previous' })
    expect(link).toHaveAttribute('aria-disabled', 'true')
    expect(link).toHaveAttribute('data-disabled')
  })

  it('forwards className alongside variant classes on the link', () => {
    render(
      <Pagination>
        <PaginationList>
          <PaginationItem>
            <PaginationLink href="#" className="my-link">
              1
            </PaginationLink>
          </PaginationItem>
        </PaginationList>
      </Pagination>,
    )
    const link = screen.getByRole('link', { name: '1' })
    expect(link.className).toContain('my-link')
  })

  it('renders link as a different element via render prop', () => {
    const onClick = vi.fn()
    render(
      <Pagination>
        <PaginationList>
          <PaginationItem>
            <PaginationLink render={<button type="button" onClick={onClick} />}>5</PaginationLink>
          </PaginationItem>
        </PaginationList>
      </Pagination>,
    )
    const el = screen.getByRole('button', { name: '5' })
    expect(el.tagName).toBe('BUTTON')
  })

  it('fires onClick on the link', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(
      <Pagination>
        <PaginationList>
          <PaginationItem>
            <PaginationLink href="#" onClick={onClick}>
              1
            </PaginationLink>
          </PaginationItem>
        </PaginationList>
      </Pagination>,
    )
    await user.click(screen.getByRole('link', { name: '1' }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('renders the ellipsis as a decorative (aria-hidden) element', () => {
    renderBasic()
    const ellipsis = document.querySelector('[data-slot="pagination-ellipsis"]')
    expect(ellipsis).not.toBeNull()
    expect(ellipsis).toHaveAttribute('aria-hidden')
  })

  it('throws when a sub-component is used outside Pagination', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<PaginationLink href="#">1</PaginationLink>)).toThrow(/must be rendered inside <Pagination>/)
    spy.mockRestore()
  })

  it('has no accessibility violations', async () => {
    const { container } = renderBasic()
    expect(await axe(container)).toHaveNoViolations()
  })
})
