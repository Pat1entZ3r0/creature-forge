// Fixed, non-interactive overlay: scanlines + film grain + vignette.
// Sits above all content; pointer-events disabled so it never blocks the canvas.
export function Atmosphere() {
  return (
    <>
      <div className="overlay overlay--grain" aria-hidden />
      <div className="overlay overlay--scan" aria-hidden />
      <div className="overlay overlay--vignette" aria-hidden />
    </>
  );
}
