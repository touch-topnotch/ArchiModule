#add ArchiGui here

# Find Qt6 with Multimedia support
find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets Multimedia MultimediaWidgets)

include_directories(
        ${CMAKE_BINARY_DIR}
        ${CMAKE_SOURCE_DIR}/src
        ${CMAKE_CURRENT_BINARY_DIR}
        ${Boost_INCLUDE_DIRS}
        ${COIN3D_INCLUDE_DIRS}
        ${ZLIB_INCLUDE_DIR}
        ${OCC_INCLUDE_DIR}
        ${EIGEN3_INCLUDE_DIR}
        ${PYTHON_INCLUDE_DIRS}
        ${XercesC_INCLUDE_DIRS}
)
link_directories(${OCC_LIBRARY_DIR})
set(ArchiGui_LIBS
        ArchiModule
        FreeCADGui
        Qt6::Multimedia
        Qt6::MultimediaWidgets
)


set (Archi_TR_QRC ${CMAKE_CURRENT_BINARY_DIR}/Resources/Archi_translation.qrc)
qt_find_and_add_translation(QM_SRCS "Resources/translations/*_*.ts" ${CMAKE_CURRENT_BINARY_DIR}/Resources/translations)
qt_create_resource_file(${Archi_TR_QRC} ${QM_SRCS})

qt_add_resources(ArchiResource_SRCS Resources/Archi.qrc ${Archi_TR_QRC})
SOURCE_GROUP("Resources" FILES ${ArchiResource_SRCS})



SET(ArchiGui_SRCS_Module
        ArchiGui.cpp
        ArchiGuiPy.cpp
        Resources/Archi.qrc
        PreCompiled.cpp
        PreCompiled.h
        # Workbench.cpp
        # Workbench.h
)
SOURCE_GROUP("Module" FILES ${ArchiGui_SRCS_Module})

SET(ArchiGui_SRCS_Commands
        Command.cpp
)

SET(ArchiGui_SRCS_Widgets
        VideoPlayerWidget.cpp
        VideoPlayerWidget.h
)
SOURCE_GROUP("Commands" FILES ${ArchiGui_SRCS_Commands})


SET(ArchiGui_SRCS
        ${ArchiGui_UIC_HDRS}
        ${ArchiResource_SRCS}
        ${ArchiGui_SRCS_Module}
        ${ArchiGui_SRCS_Commands}
        ${ArchiGui_SRCS_Widgets}
)

if(FREECAD_USE_PCH)
    add_definitions(-D_PreComp_)
    GET_MSVC_PRECOMPILED_SOURCE("PreCompiled.cpp" PCH_SRCS ${ArchiGui_SRCS})
    ADD_MSVC_PRECOMPILED_HEADER(ArchiGui PreCompiled.h PreCompiled.cpp PCH_SRCS)
endif(FREECAD_USE_PCH)

SET(ArchiGuiIcon_SVG
        Resources/icons/Archi_Workbench.svg
)
SET(ArchiGuiAnims_SVG
        Resources/anims/Archi_Preloader.svg
)
SET(ArchiGenerations3d_GLTF
        Resources/3d/scene.gltf
)

add_library(ArchiGui SHARED ${ArchiGui_SRCS} ${ArchiGuiIcon_SVG} ${ArchiGuiAnims_SVG} ${ArchiGenerations3d_GLTF})
target_link_libraries(ArchiGui ${ArchiGui_LIBS})
if (FREECAD_WARN_ERROR)
    target_compile_warn_error(ArchiGui)
endif()

unset(_flag_found CACHE)
check_cxx_compiler_flag("-Wno-deprecated-copy" _flag_found)
if (_flag_found)
    target_compile_options(ArchiGui PRIVATE -Wno-deprecated-copy)
endif ()


SET_BIN_DIR(ArchiGui ArchiGui /Mod/ArchiModule)
SET_PYTHON_PREFIX_SUFFIX(ArchiGui)

fc_copy_sources(ArchiGui "${CMAKE_BINARY_DIR}/${CMAKE_INSTALL_DATADIR}/Mod/ArchiModule" ${ArchiGuiIcon_SVG})
file(GLOB copied_files "${CMAKE_BINARY_DIR}/${CMAKE_INSTALL_DATADIR}/Mod/ArchiModule/*")


fc_copy_sources(ArchiGui "${CMAKE_BINARY_DIR}/${CMAKE_INSTALL_DATADIR}/Mod/ArchiModule" ${ArchiGuiAnims_SVG})
file(GLOB copied_files "${CMAKE_BINARY_DIR}/${CMAKE_INSTALL_DATADIR}/Mod/ArchiModule/*")


fc_copy_sources(ArchiGui "${CMAKE_BINARY_DIR}/${CMAKE_INSTALL_DATADIR}/Mod/ArchiModule" ${ArchiGenerations3d_GLTF})
file(GLOB copied_files "${CMAKE_BINARY_DIR}/${CMAKE_INSTALL_DATADIR}/Mod/ArchiModule/*")


INSTALL(TARGETS ArchiGui DESTINATION ${CMAKE_INSTALL_LIBDIR})


INSTALL(FILES ${ArchiGuiIcon_SVG} DESTINATION "${CMAKE_INSTALL_DATADIR}/Mod/ArchiModule/Resources/icons")
INSTALL(FILES ${ArchiGuiAnims_SVG} DESTINATION "${CMAKE_INSTALL_DATADIR}/Mod/ArchiModule/Resources/anims")
INSTALL(FILES ${ArchiGenerations3d_GLTF} DESTINATION "${CMAKE_INSTALL_DATADIR}/Mod/ArchiModule/Resources/generations3d")
INSTALL(FILES ${AtchiPanels_UI} DESTINATION "${CMAKE_INSTALL_DATADIR}/Mod/ArchiModule/Resources/panels")

# Install PySide6-Addons if needed
if(PYTHON_EXECUTABLE)

          message(STATUS "Checking PySide6 version...")

        # Get the installed PySide6 version
        execute_process(
                COMMAND ${PYTHON_EXECUTABLE} -c "import PySide6; print(PySide6.__version__)"
                OUTPUT_VARIABLE PYSIDE6_VERSION
                OUTPUT_STRIP_TRAILING_WHITESPACE
                ERROR_VARIABLE PYSIDE6_VERSION_ERROR
        )


        if(PYSIDE6_VERSION)
                message(STATUS "Detected PySide6 version: ${PYSIDE6_VERSION}")

                # Upgrade pip (optional but recommended)
                execute_process(
                COMMAND ${PYTHON_EXECUTABLE} -m pip install --upgrade pip
                        RESULT_VARIABLE pip_upgrade_result
                        OUTPUT_VARIABLE pip_upgrade_output
                        ERROR_VARIABLE pip_upgrade_error
                )
                if(NOT pip_upgrade_result EQUAL 0)
                        message(WARNING "pip upgrade failed: ${pip_upgrade_error}")
                endif()

                # List of modules to install at the detected version
                set(PYSIDE6_ADDONS_MODULES
                        "PySide6-Addons==${PYSIDE6_VERSION}"
                )

                foreach(module ${PYSIDE6_ADDONS_MODULES})
                message(STATUS "Installing Python module: ${module}")
                execute_process(
                        COMMAND ${PYTHON_EXECUTABLE} -m pip install --no-cache-dir ${module}
                        RESULT_VARIABLE pip_install_result
                        OUTPUT_VARIABLE pip_install_output
                        ERROR_VARIABLE pip_install_error
                )
                if(NOT pip_install_result EQUAL 0)
                        message(FATAL_ERROR "Failed to install ${module}:\n${pip_install_error}")
                endif()
                endforeach()
        endif()

endif()

# Create PySide compatibility modules
file(WRITE ${CMAKE_BINARY_DIR}/Ext/PySide/Qt3DCore.py "from PySide${PYSIDE_MAJOR_VERSION}.Qt3DCore import *\n")
file(WRITE ${CMAKE_BINARY_DIR}/Ext/PySide/Qt3DExtras.py "from PySide${PYSIDE_MAJOR_VERSION}.Qt3DExtras import *\n")
file(WRITE ${CMAKE_BINARY_DIR}/Ext/PySide/Qt3DRender.py "from PySide${PYSIDE_MAJOR_VERSION}.Qt3DRender import *\n")
file(WRITE ${CMAKE_BINARY_DIR}/Ext/PySide/QtPrintSupport.py "from PySide${PYSIDE_MAJOR_VERSION}.QtPrintSupport import *\n")

# Create QtSvg compatibility module to fix CAM module import error
if(PYSIDE_MAJOR_VERSION LESS 6)
    file(WRITE ${CMAKE_BINARY_DIR}/Ext/PySide/QtSvg.py "from PySide${PYSIDE_MAJOR_VERSION}.QtSvg import *\n")
    file(WRITE ${CMAKE_BINARY_DIR}/Ext/PySide/QtSvgWidgets.py "from PySide${PYSIDE_MAJOR_VERSION}.QtSvg import QGraphicsSvgItem\nfrom PySide${PYSIDE_MAJOR_VERSION}.QtSvg import QSvgWidget\n")
else()
    file(WRITE ${CMAKE_BINARY_DIR}/Ext/PySide/QtSvg.py "from PySide${PYSIDE_MAJOR_VERSION}.QtSvg import *\n")
    file(WRITE ${CMAKE_BINARY_DIR}/Ext/PySide/QtSvgWidgets.py "from PySide${PYSIDE_MAJOR_VERSION}.QtSvgWidgets import *\n")
endif()