// The web build's JavaScript, linked in by build.rs (--js-library) for the Emscripten target.

addToLibrary({
	// The browser's next display refresh (requestAnimationFrame), waited for by suspending the program (ASYNCIFY):
	// the game's loop runs until it quits, and waiting here between frames lets the browser show each frame and
	// deliver input, with frames lined up with the screen. A hidden page (another tab) gets no refreshes: then wait a
	// frame's time instead, so the game and its sound go on (browsers don't slow down the timers of a page playing
	// sound). Hiding the page ends a wait for a refresh, which would otherwise last until the page is shown again.
	phantom_spider_next_frame__async: 'auto',
	phantom_spider_next_frame: () => new Promise((resolve) => {
		if (document.hidden) {
			setTimeout(resolve, 1000 / 60);
			return;
		}
		const done = () => {
			document.removeEventListener('visibilitychange', done);
			resolve();
		};
		requestAnimationFrame(done);
		document.addEventListener('visibilitychange', done);
	}),
});
