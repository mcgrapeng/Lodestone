import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'
import { Card, CardDescription, CardFooter, CardHeader, CardMedia, CardTitle } from './card'

const TITLE = 'Deployment ready'
const DESCRIPTION = 'Your project finished building 2 minutes ago.'

function renderCard(props: Partial<React.ComponentProps<typeof Card>> = {}) {
  return render(
    <Card {...props}>
      <CardMedia data-testid="media">
        <img src="/cover.jpg" alt="" />
      </CardMedia>
      <CardHeader>
        <CardTitle>{TITLE}</CardTitle>
        <CardDescription>{DESCRIPTION}</CardDescription>
      </CardHeader>
      <CardFooter>
        <button type="button">Deploy</button>
      </CardFooter>
    </Card>,
  )
}

function getRoot() {
  return document.querySelector('[data-slot="card"]') as HTMLElement
}

describe('Card', () => {
  it('renders the composed slots inside a content wrapper', () => {
    renderCard()

    const root = getRoot()
    const content = root.querySelector('[data-slot="card-content"]')

    expect(root).toBeInTheDocument()
    expect(content).toBeInTheDocument()
    expect(content).toContainElement(screen.getByTestId('media'))
    expect(content).toContainElement(screen.getByRole('heading', { name: TITLE }))
    expect(content).toContainElement(screen.getByRole('button', { name: 'Deploy' }))
    expect(screen.getByText(DESCRIPTION)).toBeInTheDocument()
  })

  it('renders unframed and inset by default', () => {
    renderCard()

    expect(getRoot()).toHaveAttribute('data-frame', 'none')
    expect(getRoot()).toHaveAttribute('data-inset', '')
  })

  it.each([
    [true, 'solid'],
    ['solid' as const, 'solid'],
    ['glass' as const, 'glass'],
  ])('maps frame=%s to data-frame="%s"', (frame, expected) => {
    renderCard({ frame })
    expect(getRoot()).toHaveAttribute('data-frame', expected)
  })

  it('drops data-inset when inset is false', () => {
    renderCard({ inset: false })
    expect(getRoot()).not.toHaveAttribute('data-inset')
  })

  it('forwards className to the root and contentProps to the content wrapper', () => {
    renderCard({ className: 'w-80', contentProps: { className: 'sm:flex-row', 'data-testid': 'content' } })

    expect(getRoot()).toHaveClass('w-80')
    expect(screen.getByTestId('content')).toHaveClass('sm:flex-row')
  })

  it('renders the root as another element via render', () => {
    render(
      <Card render={<article />}>
        <CardHeader>
          <CardTitle>{TITLE}</CardTitle>
        </CardHeader>
      </Card>,
    )

    expect(screen.getByRole('article')).toHaveAttribute('data-slot', 'card')
  })

  it('renders the title as h3 by default and honors the render escape hatch', () => {
    const { unmount } = render(<CardTitle>{TITLE}</CardTitle>)
    expect(screen.getByRole('heading', { level: 3, name: TITLE })).toBeInTheDocument()
    unmount()

    render(<CardTitle render={<h2 />}>{TITLE}</CardTitle>)
    expect(screen.getByRole('heading', { level: 2, name: TITLE })).toBeInTheDocument()
  })

  it('has no accessibility violations', async () => {
    const { container } = renderCard({ frame: 'glass' })
    expect(await axe(container)).toHaveNoViolations()
  })
})
