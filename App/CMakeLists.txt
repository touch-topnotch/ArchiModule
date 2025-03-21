include_directories(
        ${CMAKE_BINARY_DIR}
        ${CMAKE_SOURCE_DIR}/src
        ${CMAKE_BINARY_DIR}/src
        ${CMAKE_CURRENT_BINARY_DIR}
        ${Boost_INCLUDE_DIRS}
        ${OCC_INCLUDE_DIR}
        ${EIGEN3_INCLUDE_DIR}
        ${PYTHON_INCLUDE_DIRS}
        ${ZLIB_INCLUDE_DIR}
        ${XercesC_INCLUDE_DIRS}
)
link_directories(${OCC_LIBRARY_DIR})

set(Archi_LIBS
        Part
        ${QT_QTCORE_LIBRARY}
        FreeCADApp
)

generate_from_xml(CommandPy)

SET(Python_SRCS
#    CommandPy.xml
#    CommandPyImp.cpp
)

SET(Mod_SRCS
        AppArchi.cpp
#        PreCompiled.cpp
#        PreCompiled.h
)

if(FREECAD_USE_PCH)
    add_definitions(-D_PreComp_)
    GET_MSVC_PRECOMPILED_SOURCE("PreCompiled.cpp" PCH_SRCS ${Archi_SRCS})
    ADD_MSVC_PRECOMPILED_HEADER(Archi PreCompiled.h PreCompiled.cpp PCH_SRCS)
endif(FREECAD_USE_PCH)

SET(Archi_SRCS
#    Command.cpp
#    Command.h
    ${Mod_SRCS}
    ${Python_SRCS}
)

#endif(FREECAD_USE_EXTERNAL_KDL)

SOURCE_GROUP("Python" FILES ${Python_SRCS})
SOURCE_GROUP("Module" FILES ${Mod_SRCS})

add_library(Archi SHARED ${Archi_SRCS})
target_link_libraries(Archi ${Archi_LIBS})
if (FREECAD_WARN_ERROR)
    target_compile_warn_error(Archi)
endif()

unset(_flag_found CACHE)
check_cxx_compiler_flag("-Wno-deprecated-copy" _flag_found)
if (_flag_found)
    target_compile_options(Archi PRIVATE -Wno-deprecated-copy)
endif()


if(MINGW)
    set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,--export-all-symbols")
endif()

# Boost >= 1.75.0
if(NOT ${Boost_VERSION} LESS 107500)
    set_target_properties(Path PROPERTIES CXX_STANDARD_REQUIRED ON)
    set_target_properties(Path PROPERTIES CXX_STANDARD 14)

    # Suppress -Wc++17-extensions when using  OCCT 7.5 or newer
    if (MINGW AND CMAKE_COMPILER_IS_CLANGXX)
        unset(_flag_found CACHE)
        check_cxx_compiler_flag("-Wno-c++17-extensions" _flag_found)
        if (_flag_found)
            set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-c++17-extensions")
        endif()
    endif()
endif()

SET_BIN_DIR(Archi Archi /Mod/Archi)
SET_PYTHON_PREFIX_SUFFIX(Archi)

INSTALL(TARGETS Archi DESTINATION ${CMAKE_INSTALL_LIBDIR})
