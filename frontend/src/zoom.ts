/**
 * The app does not zoom like a page: index.html sets maximum-scale=1, which also keeps iOS from
 * zooming in on a focused field with text under 16 px. iOS ignores it for pinching, so pinch
 * gestures are cancelled here as well (SPEC 11, Zoom).
 */
export function blockPageZoom(): void {
  document.addEventListener(
    'gesturestart',
    (event) => {
      // A page that is somehow zoomed in already can still be zoomed back out.
      if ((window.visualViewport?.scale ?? 1) <= 1) event.preventDefault()
    },
    { passive: false },
  )
}
