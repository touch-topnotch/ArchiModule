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

# Define all Python source files with their relative paths
set(Archi_Python_SRCS
    tools/full_view.py
    tools/image_viewer.py
    tools/models.py
    tools/log.py
    tools/master_api.py
    tools/__init__.py
    tools/gallery_utils.py
    tools/exporting.py
    tools/project_context/project_context_command.py
    tools/project_context/__init__.py
    tools/project_context/pipelines/download_model_behaviour.py
    tools/project_context/pipelines/form_window.py
    tools/project_context/pipelines/__init__.py
    tools/project_context/pipelines/gen_2d_behaviour.py
    tools/project_context/pipelines/prepare_for_2d_gen.py
    tools/project_context/pipelines/prepare_for_3d_gen.py
    tools/project_context/utils/image_utils.py
    tools/project_context/utils/__init__.py
    tools/project_context/utils/widgets.py
    tools/project_context/utils/project_behaviour_base.py
    tools/project_context/project_context_window.py
    tools/authentication.py
    tools/ProjectContext_OLD.py
    tools/floor_planner.py
    tools/view_3d.py
    tools/convert_png.py
)

# Create custom target for Python sources
ADD_CUSTOM_TARGET(ArchiModulesPython ALL SOURCES ${Archi_Python_SRCS})

# Copy Python sources to build directory maintaining directory structure
fc_target_copy_resource(ArchiModulesPython
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_BINARY_DIR}/Mod/ArchiModule
        ${Archi_Python_SRCS})

# Install main scripts
INSTALL(
        FILES
        ${Archi_Scripts}
        DESTINATION
        Mod/ArchiModule
)

# Install Python sources maintaining directory structure
INSTALL(
        DIRECTORY
        tools
        DESTINATION
        Mod/ArchiModule
)

if (DEFINED Archi_Resources)
    INSTALL(
        DIRECTORY
            Lib
        DESTINATION
            Mod/ArchiModule
        PATTERN "Makefile*" EXCLUDE
        PATTERN "*.pdf" EXCLUDE
        PATTERN "testprog.*" EXCLUDE
    )
endif()
