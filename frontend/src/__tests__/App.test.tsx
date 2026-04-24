import { render, screen } from '@testing-library/react'
import App from '../App'

test('App renders without crash', () => {
  render(<App />)
  expect(document.getElementById('root') || document.body).toBeTruthy()
})
