//! The web build (the Emscripten target), run by a web page: see web/CMakeLists.txt.

extern "C" {
    /// web/library.js
    fn phantom_spider_next_frame();
}

/// Wait for the browser's next display refresh. The game's loop calls this between frames instead of sleeping:
/// it gives the browser the time to show the frame and deliver input.
pub fn next_frame() {
    unsafe { phantom_spider_next_frame() }
}
