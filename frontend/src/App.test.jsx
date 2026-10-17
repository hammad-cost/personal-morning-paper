import { render, screen } from '@testing-library/react'
import App from './App'

describe('App', () => {
  it('renders the paper title', () => {
    render(<App />)
    expect(
      screen.getByRole('heading', { name: /the personal morning paper/i }),
    ).toBeInTheDocument()
  })
})
