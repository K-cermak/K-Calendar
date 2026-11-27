import { describe, expect, it } from 'vitest'
import { blockPageZoom } from './zoom'

describe('blockPageZoom', () => {
  it('cancels the pinch gestures iOS starts despite maximum-scale', () => {
    blockPageZoom()
    const gesture = new Event('gesturestart', { cancelable: true })
    document.dispatchEvent(gesture)
    expect(gesture.defaultPrevented).toBe(true)
  })
})
