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
    tools/exporting.py
    tools/project_context/project_context_command.py
    tools/project_context/__init__.py
    tools/project_context/pipelines/form_window.py
    tools/project_context/pipelines/__init__.py
    tools/project_context/pipelines/gen_2d/__init__.py
    tools/project_context/pipelines/gen_2d/prepare.py
    tools/project_context/pipelines/gen_2d/behaviour.py
    tools/project_context/pipelines/gen_3d/__init__.py
    tools/project_context/pipelines/gen_3d/prepare.py
    tools/project_context/pipelines/gen_3d/behaviour.py
    tools/project_context/pipelines/gen_video/__init__.py
    tools/project_context/pipelines/gen_video/prepare.py
    tools/project_context/pipelines/gen_video/behaviour.py
    tools/project_context/utils/image_utils.py
    tools/project_context/utils/__init__.py
    tools/project_context/utils/widgets.py
    tools/project_context/utils/project_behaviour_base.py
    tools/project_context/utils/gallery_utils.py
    tools/project_context/utils/multiview_widgets.py
    tools/project_context/project_context_window.py
    tools/authentication/__init__.py
    tools/authentication/authentication.py
    tools/authentication/authentication_window.py
    tools/view_3d.py
    tools/video_player.py
    tools/convert_png.py
)

# Create custom target for Python sources
ADD_CUSTOM_TARGET(ArchiModulesPython ALL SOURCES ${Archi_Python_SRCS})

# Copy Python sources to build directory maintaining directory structure
fc_target_copy_resource(ArchiModulesPython
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_BINARY_DIR}/Mod/ArchiModule
        ${Archi_Python_SRCS})

# Copy requirements.txt to build directory
configure_file(${CMAKE_CURRENT_SOURCE_DIR}/requirements.txt
               ${CMAKE_BINARY_DIR}/Mod/ArchiModule/requirements.txt COPYONLY)



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

# Install requirements.txt
INSTALL(
        FILES
        requirements.txt
        DESTINATION
        Mod/ArchiModule
)

# Install Python dependencies from requirements.txt
if(PYTHON_EXECUTABLE)
    message(STATUS "Installing ArchiModule Python dependencies...")
    
    # Read requirements.txt using Python script
    set(REQUIREMENTS_FILE "${CMAKE_CURRENT_SOURCE_DIR}/requirements.txt")
    if(EXISTS ${REQUIREMENTS_FILE})
        message(STATUS "Found requirements.txt: ${REQUIREMENTS_FILE}")
        
        # Use Python to read the file properly
        execute_process(
            COMMAND ${PYTHON_EXECUTABLE} -c "
import sys
requirements = []
with open('${REQUIREMENTS_FILE}', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            requirements.append(line)
print(';'.join(requirements))
"
            OUTPUT_VARIABLE REQUIREMENTS_CONTENT
            OUTPUT_STRIP_TRAILING_WHITESPACE
            ERROR_VARIABLE REQUIREMENTS_ERROR
        )
        
        if(REQUIREMENTS_ERROR)
            message(FATAL_ERROR "Failed to read requirements.txt: ${REQUIREMENTS_ERROR}")
        endif()
        
        # Split the requirements
        string(REPLACE ";" ";" CLEAN_REQUIREMENTS_LIST "${REQUIREMENTS_CONTENT}")
        message(STATUS "ArchiModule requirements to install: ${CLEAN_REQUIREMENTS_LIST}")
        
        # Install each requirement
        foreach(module ${CLEAN_REQUIREMENTS_LIST})
            message(STATUS "Installing ArchiModule Python module: ${module}")
            execute_process(
                COMMAND ${PYTHON_EXECUTABLE} -m pip install ${module}
                RESULT_VARIABLE pip_install_result
                OUTPUT_VARIABLE pip_install_output
                ERROR_VARIABLE pip_install_error
            )
            if(NOT pip_install_result EQUAL 0)
                message(WARNING "Failed to install ${module}: ${pip_install_error}")
                message(STATUS "Trying to install with --user flag...")
                execute_process(
                    COMMAND ${PYTHON_EXECUTABLE} -m pip install --user ${module}
                    RESULT_VARIABLE pip_install_user_result
                    OUTPUT_VARIABLE pip_install_user_output
                    ERROR_VARIABLE pip_install_user_error
                )
                if(NOT pip_install_user_result EQUAL 0)
                    message(FATAL_ERROR "Failed to install ${module} even with --user flag: ${pip_install_user_error}")
                endif()
            endif()
        endforeach()
    else()
        message(FATAL_ERROR "requirements.txt not found at ${REQUIREMENTS_FILE}")
    endif()
endif()



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
