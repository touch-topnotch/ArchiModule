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
        ${CMAKE_BINARY_DIR}/Mod/ArchiModule
        ${Archi_Scripts})

if (DEFINED Archi_Resources)
    fc_target_copy_resource(ArchiScripts
            ${CMAKE_CURRENT_SOURCE_DIR}
            ${CMAKE_BINARY_DIR}/${CMAKE_INSTALL_DATADIR}/Mod/ArchiModule
            ${Archi_Resources})
endif()

INSTALL(
        FILES
        ${Archi_Scripts}
        DESTINATION
        Mod/ArchiModule
)

if (DEFINED Archi_Resources)
    INSTALL(
        DIRECTORY
            Lib
        DESTINATION
            ${CMAKE_INSTALL_DATADIR}/Mod/ArchiModule
        PATTERN "Makefile*" EXCLUDE
        PATTERN "*.pdf" EXCLUDE
        PATTERN "testprog.*" EXCLUDE
    )
endif()
set(ModulesPython_SRCS
        Tools
)
foreach(module_dir IN LISTS ModulesPython_SRCS)
    file(GLOB_RECURSE _module_files
         RELATIVE ${CMAKE_CURRENT_SOURCE_DIR}
         "${module_dir}/*"
    )
    list(APPEND ToolsPython_SRCS ${_module_files})
endforeach()
set(AllScriptsPython_SRCS
        ${ToolsPython_SRCS}
)

ADD_CUSTOM_TARGET(ArchiModulesPython ALL SOURCES ${AllScriptsPython_SRCS})
fc_target_copy_resource(ArchiModulesPython
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_BINARY_DIR}/Mod/ArchiModule
        ${AllScriptsPython_SRCS})

INSTALL(
        FILES
        ${AllScriptsPython_SRCS}
        DESTINATION
        Mod/ArchiModule/
)
