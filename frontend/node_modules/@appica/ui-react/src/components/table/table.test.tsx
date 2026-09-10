import * as React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { axe } from 'vitest-axe'
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from './table'

function Demo(props: React.ComponentProps<typeof Table> = {}) {
  return (
    <Table {...props}>
      <TableCaption>Recent transactions</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>Date</TableHead>
          <TableHead>Description</TableHead>
          <TableHead className="text-end">Amount</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell>Aug 30</TableCell>
          <TableCell>Salary</TableCell>
          <TableCell className="text-end">+ $4,150.00</TableCell>
        </TableRow>
        <TableRow highlighted>
          <TableCell>Aug 24</TableCell>
          <TableCell>Netflix</TableCell>
          <TableCell className="text-end">- $20.00</TableCell>
        </TableRow>
        <TableRow>
          <TableCell>Aug 17</TableCell>
          <TableCell>Electricity</TableCell>
          <TableCell className="text-end">- $186.35</TableCell>
        </TableRow>
      </TableBody>
    </Table>
  )
}

describe('Table', () => {
  it('renders the full semantic composition', () => {
    render(<Demo />)
    const table = screen.getByRole('table')
    expect(table).toHaveAttribute('data-slot', 'table')
    expect(screen.getAllByRole('columnheader')).toHaveLength(3)
    expect(screen.getAllByRole('row')).toHaveLength(4) // header + 3 body rows
    expect(screen.getAllByRole('cell')).toHaveLength(9)
  })

  it('applies size padding via parent descendant selectors', () => {
    const { rerender } = render(<Demo size="sm" />)
    expect(screen.getByRole('table').className).toContain('[&_td]:p-3')
    expect(screen.getByRole('table').className).toContain('p-1 ')

    rerender(<Demo size="md" />)
    expect(screen.getByRole('table').className).toContain('[&_td]:p-3.5')

    rerender(<Demo size="lg" />)
    expect(screen.getByRole('table').className).toContain('[&_td]:p-4')
    expect(screen.getByRole('table').className).toContain('p-1.5')
  })

  it('applies dashed border style on body cells via parent selector', () => {
    render(<Demo borderStyle="dashed" />)
    const className = screen.getByRole('table').className
    expect(className).toContain('[&_td]:border-dashed')
    expect(className).toContain('[&_td]:border-border-strong')
  })

  it('strips cell borders when borderStyle="none"', () => {
    render(<Demo borderStyle="none" />)
    const className = screen.getByRole('table').className
    expect(className).toContain('[&_td]:border-b-0')
    expect(className).toContain('[&>tbody_th]:border-b-0')
  })

  it('toggles data-highlighted on the row when highlighted prop is set', () => {
    render(<Demo />)
    const rows = screen.getAllByRole('row')
    // header (idx 0), then three body rows; idx 2 is highlighted
    expect(rows[2]).toHaveAttribute('data-highlighted', '')
    expect(rows[1]).not.toHaveAttribute('data-highlighted')
    expect(rows[3]).not.toHaveAttribute('data-highlighted')
  })

  it('opts into striped rows only when stripedRows is set', () => {
    const { rerender } = render(<Demo />)
    expect(screen.getByRole('table').className).not.toContain('[&>tbody>tr:nth-child(2n)]:bg-background-subtle')

    rerender(<Demo stripedRows />)
    expect(screen.getByRole('table').className).toContain('[&>tbody>tr:nth-child(2n)]:bg-background-subtle')
  })

  it('opts into striped columns only when stripedColumns is set', () => {
    const { rerender } = render(<Demo />)
    expect(screen.getByRole('table').className).not.toContain('[&>tbody>tr>:nth-child(2n)]:bg-background-subtle')

    rerender(<Demo stripedColumns />)
    expect(screen.getByRole('table').className).toContain('[&>tbody>tr>:nth-child(2n)]:bg-background-subtle')
  })

  it('opts into row hover styling only when hoverableRows is set', () => {
    const { rerender } = render(<Demo />)
    expect(screen.getByRole('table').className).not.toContain('[&>tbody>tr:hover]:bg-background-subtle')

    rerender(<Demo hoverableRows />)
    expect(screen.getByRole('table').className).toContain('[&>tbody>tr:hover]:bg-background-subtle')
  })

  it('applies bottom inner-radius classes to last body row cells', () => {
    render(<Demo size="md" />)
    const className = screen.getByRole('table').className
    expect(className).toContain('[&>tbody:last-of-type>tr:last-child>:first-child]:rounded-es-md')
    expect(className).toContain('[&>tbody:last-of-type>tr:last-child>:last-child]:rounded-ee-md')
  })

  it('keeps top inner-radius classes ready for the no-header case', () => {
    // The classes are always present on the table; CSS :not(:has(thead)) handles
    // whether they actually apply at paint time. Verify the literal class is emitted.
    render(<Demo size="md" />)
    const className = screen.getByRole('table').className
    expect(className).toContain('[&:not(:has(thead))>tbody:first-of-type>tr:first-child>:first-child]:rounded-ss-md')
  })

  it('applies header pill background and corner classes', () => {
    render(<Demo size="md" />)
    const className = screen.getByRole('table').className
    expect(className).toContain('[&>thead>tr>th]:bg-background-muted')
    expect(className).toContain('[&>thead>tr:first-child>th:first-child]:rounded-ss-md')
    expect(className).toContain('[&>thead>tr:last-child>th:last-child]:rounded-ee-md')
  })

  it('renders <th scope="row"> inside <tbody> as a row-header cell', () => {
    render(
      <Table>
        <TableBody>
          <TableRow>
            <TableHead scope="row">Monday</TableHead>
            <TableCell>Standup</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    )
    expect(screen.getByRole('rowheader', { name: 'Monday' })).toBeInTheDocument()
  })

  it('places the caption above when position="top"', () => {
    render(
      <Table>
        <TableCaption position="top">Title</TableCaption>
        <TableBody>
          <TableRow>
            <TableCell>cell</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    )
    const caption = screen.getByText('Title')
    expect(caption.tagName).toBe('CAPTION')
    expect(caption.className).toContain('caption-top')
  })

  it('emits data-slot on each sub-component', () => {
    render(<Demo />)
    expect(screen.getByRole('table')).toHaveAttribute('data-slot', 'table')
    expect(screen.getByText('Recent transactions')).toHaveAttribute('data-slot', 'table-caption')
    expect(screen.getAllByRole('columnheader')[0]).toHaveAttribute('data-slot', 'table-head')
    expect(screen.getAllByRole('cell')[0]).toHaveAttribute('data-slot', 'table-cell')
    expect(screen.getAllByRole('row')[1]).toHaveAttribute('data-slot', 'table-row')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<Demo />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
