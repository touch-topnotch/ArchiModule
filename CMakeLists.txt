# add subdirectories App and Gui
add_subdirectory(App)
add_subdirectory(Gui)

set(Archi_Scripts
        Init.py
)
if(BUILD_GUI)
    list (APPEND Archi_Scripts
            InitGui.py
    )
endif(BUILD_GUI)

add_custom_target(ArchiScripts ALL
        SOURCES ${Archi_Scripts}
)
fc_target_copy_resource(ArchiScripts
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_BINARY_DIR}/Mod/Archi
        ${Archi_Scripts})

if (DEFINED Archi_Resources)
    fc_target_copy_resource(ArchiScripts
            ${CMAKE_CURRENT_SOURCE_DIR}
            ${CMAKE_BINARY_DIR}/${CMAKE_INSTALL_DATADIR}/Mod/Archi
            ${Archi_Resources})
endif()

INSTALL(
        FILES
        ${Archi_Scripts}
        DESTINATION
        Mod/Archi
)

if (DEFINED Archi_Resources)
    INSTALL(
        DIRECTORY
            Lib
        DESTINATION
            ${CMAKE_INSTALL_DATADIR}/Mod/Archi
        PATTERN "Makefile*" EXCLUDE
        PATTERN "*.pdf" EXCLUDE
        PATTERN "testprog.*" EXCLUDE
    )
endif()

set(ToolsPython_SRCS
        Tools/__init__.py
        Tools/ProjectContext.py
        Tools/Authentication.py
        Tools/MasterAPI.py
        Tools/Models.py
        Tools/View3d.py
        Tools/GalleryUtils.py
        Tools/Exporting.py
        Tools/FullView.py
        Tools/ConvertPNG.py
)
set(AllScriptsPython_SRCS
        ${ToolsPython_SRCS}
)

ADD_CUSTOM_TARGET(ArchiModulesPython ALL SOURCES ${AllScriptsPython_SRCS})
fc_target_copy_resource(ArchiModulesPython
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_BINARY_DIR}/Mod/Archi
        ${AllScriptsPython_SRCS})

INSTALL(
        FILES
        ${AllScriptsPython_SRCS}
        DESTINATION
        Mod/Archi/
)
