# Phantom Spider RE for the web: the game built with Emscripten (Rust's wasm32-unknown-emscripten target), with its
# files, to be run by a web page.
#
#     emcmake cmake -S web -B build -DPHANTOM_SPIDER_JAR=<Phantom_Spider_s40v2.jar> -DPHANTOM_SPIDER_SOUNDFONT=<.sf2>
#     cmake --build build
#
# Writes, at the top of the build folder, PhantomSpider.js, PhantomSpider.wasm and PhantomSpider.data, and
# PhantomSpider.png, a 256x256 icon. The .data holds the JAR and the SoundFont, at / (where the game looks for them: see
# exe_dir in src/main.rs); on its first start, the game unpacks the JAR into its folder, /home/web_user/phantom-spider
# (src/paths.rs), which the page keeps in the browser's storage, with the saves and settings.
#
# The page starts the game with callMain, and keeps that folder in IndexedDB (IDBFS): see the link options below.
# Needs rustup, with the wasm32-unknown-emscripten target, and Python with Pillow (for the icon).

cmake_minimum_required(VERSION 3.20)
project(phantom_spider_web NONE)

if(NOT EMSCRIPTEN)
	message(FATAL_ERROR "This is the web build: configure it with emcmake")
endif()

set(PHANTOM_SPIDER_JAR "" CACHE FILEPATH "Phantom_Spider_s40v2.jar, the original game")
set(PHANTOM_SPIDER_SOUNDFONT "" CACHE FILEPATH "A General MIDI SoundFont (.sf2) for the music")
foreach(file PHANTOM_SPIDER_JAR PHANTOM_SPIDER_SOUNDFONT)
	if(NOT EXISTS "${${file}}")
		message(FATAL_ERROR "Set ${file} to the file (it's '${${file}}')")
	endif()
endforeach()
get_filename_component(SOUNDFONT_NAME "${PHANTOM_SPIDER_SOUNDFONT}" NAME)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
# rustup's own cargo and rustc, which have its targets (a cargo installed otherwise may come first on the PATH)
find_program(RUSTUP rustup REQUIRED)
foreach(tool cargo rustc)
	execute_process(COMMAND "${RUSTUP}" which ${tool} OUTPUT_VARIABLE ${tool}_path OUTPUT_STRIP_TRAILING_WHITESPACE
	                COMMAND_ERROR_IS_FATAL ANY)
endforeach()

set(SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/..")
set(TARGET wasm32-unknown-emscripten)
set(CARGO_OUT "${CMAKE_BINARY_DIR}/target/${TARGET}/release")

# For the page: it starts the game (callMain), which exits with the game (calling the page's onExit), and it keeps the
# game's folder in IndexedDB (IDBFS). The JAR and the SoundFont are preloaded. (build.rs adds what the game needs:
# Emscripten's SDL3, and its JavaScript.)
set(LINK_OPTIONS
	-sINVOKE_RUN=0
	-sEXIT_RUNTIME
	-sEXPORTED_RUNTIME_METHODS=callMain,FS,IDBFS,addRunDependency,removeRunDependency
	-lidbfs.js
	"--preload-file=${PHANTOM_SPIDER_JAR}@/Phantom_Spider_s40v2.jar"
	"--preload-file=${PHANTOM_SPIDER_SOUNDFONT}@/${SOUNDFONT_NAME}"
)
# Passed to cargo as CARGO_ENCODED_RUSTFLAGS: the flags separated by ASCII 0x1f, so that paths may have spaces
string(ASCII 31 SEPARATOR)
set(RUSTFLAGS "")
foreach(option ${LINK_OPTIONS})
	if(RUSTFLAGS)
		string(APPEND RUSTFLAGS "${SEPARATOR}")
	endif()
	string(APPEND RUSTFLAGS "-Clink-arg=${option}")
endforeach()

# Cargo knows what to rebuild, so it runs on every build; the files it makes are then copied under the game's name
add_custom_target(phantom_spider ALL
	COMMAND "${CMAKE_COMMAND}" -E env "RUSTC=${rustc_path}" "CARGO_TARGET_DIR=${CMAKE_BINARY_DIR}/target"
	        "CARGO_ENCODED_RUSTFLAGS=${RUSTFLAGS}"
	        "${cargo_path}" build --release --target ${TARGET} --manifest-path "${SOURCE}/Cargo.toml"
	COMMAND "${CMAKE_COMMAND}" -E copy_if_different "${CARGO_OUT}/phantom-spider.js" "${CMAKE_BINARY_DIR}/PhantomSpider.js"
	# (the .wasm is named after the crate, with an underscore)
	COMMAND "${CMAKE_COMMAND}" -E copy_if_different "${CARGO_OUT}/phantom_spider.wasm" "${CMAKE_BINARY_DIR}/PhantomSpider.wasm"
	# (cargo leaves the .data where the linker wrote it)
	COMMAND "${CMAKE_COMMAND}" -E copy_if_different "${CARGO_OUT}/deps/phantom_spider.data" "${CMAKE_BINARY_DIR}/PhantomSpider.data"
	USES_TERMINAL
	VERBATIM
)

add_custom_command(
	OUTPUT "${CMAKE_BINARY_DIR}/PhantomSpider.png"
	COMMAND Python3::Interpreter "${CMAKE_CURRENT_SOURCE_DIR}/icon.py" "${SOURCE}/docs/images/phantom-spider-icon.png"
	        "${CMAKE_BINARY_DIR}/PhantomSpider.png"
	DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/icon.py" "${SOURCE}/docs/images/phantom-spider-icon.png"
	VERBATIM
)
add_custom_target(phantom_spider_icon ALL DEPENDS "${CMAKE_BINARY_DIR}/PhantomSpider.png")
