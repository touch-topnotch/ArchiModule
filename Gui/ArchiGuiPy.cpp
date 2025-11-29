/***************************************************************************
 *   Copyright (c) 2025 Dmitry Tetkin                                     *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
 *                                                                         *
 ***************************************************************************/

#include "PreCompiled.h"

#include <Python.h>
#include <CXX/Extensions.hxx>
#include <Base/Interpreter.h>

#include "VideoPlayerWidget.h"

namespace ArchiGui {

// Python wrapping for VideoPlayerWidget
class VideoPlayerWidgetPy : public Py::PythonExtension<VideoPlayerWidgetPy>
{
public:
    static void init_type();
    static PyObject* PyMake(PyTypeObject* type, PyObject* args, PyObject* kwds);

    VideoPlayerWidgetPy(VideoPlayerWidget* widget = nullptr);
    ~VideoPlayerWidgetPy() override;

    Py::Object repr() override;
    
    Py::Object loadVideo(const Py::Tuple& args);
    Py::Object play(const Py::Tuple& args);
    Py::Object pause(const Py::Tuple& args);
    Py::Object stop(const Py::Tuple& args);
    Py::Object setPosition(const Py::Tuple& args);
    Py::Object setVolume(const Py::Tuple& args);
    Py::Object setControlsVisible(const Py::Tuple& args);
    Py::Object controlsVisible(const Py::Tuple& args);
    Py::Object setAutoLoop(const Py::Tuple& args);
    Py::Object autoLoop(const Py::Tuple& args);
    Py::Object position(const Py::Tuple& args);
    Py::Object getWidget(const Py::Tuple& args);
    
    VideoPlayerWidget* getPlayerWidget() { return m_widget; }

private:
    VideoPlayerWidget* m_widget;
    bool m_ownWidget;
};

// Initialize Python type
void VideoPlayerWidgetPy::init_type()
{
    behaviors().name("VideoPlayerWidget");
    behaviors().doc("Native C++ video player widget using Qt Multimedia");
    behaviors().set_tp_new(PyMake);
    behaviors().supportRepr();
    behaviors().supportGetattr();
    behaviors().supportSetattr();
    
    add_varargs_method("loadVideo", &VideoPlayerWidgetPy::loadVideo,
                       "loadVideo(path) -- Load video from file path");
    add_varargs_method("play", &VideoPlayerWidgetPy::play,
                       "play() -- Start or resume playback");
    add_varargs_method("pause", &VideoPlayerWidgetPy::pause,
                       "pause() -- Pause playback");
    add_varargs_method("stop", &VideoPlayerWidgetPy::stop,
                       "stop() -- Stop playback");
    add_varargs_method("setPosition", &VideoPlayerWidgetPy::setPosition,
                       "setPosition(ms) -- Set playback position in milliseconds");
    add_varargs_method("setVolume", &VideoPlayerWidgetPy::setVolume,
                       "setVolume(volume) -- Set volume (0-100)");
    add_varargs_method("setControlsVisible", &VideoPlayerWidgetPy::setControlsVisible,
                       "setControlsVisible(visible) -- Show or hide playback controls");
    add_varargs_method("controlsVisible", &VideoPlayerWidgetPy::controlsVisible,
                       "controlsVisible() -- Return True if controls are visible");
    add_varargs_method("setAutoLoop", &VideoPlayerWidgetPy::setAutoLoop,
                       "setAutoLoop(loop) -- Enable or disable automatic looping");
    add_varargs_method("autoLoop", &VideoPlayerWidgetPy::autoLoop,
                       "autoLoop() -- Return True if auto looping is enabled");
    add_varargs_method("position", &VideoPlayerWidgetPy::position,
                       "position() -- Get current playback position in milliseconds");
    add_varargs_method("getWidget", &VideoPlayerWidgetPy::getWidget,
                       "getWidget() -- Get the Qt widget pointer as integer");

    behaviors().readyType();  // Finalize type registration
}

PyObject* VideoPlayerWidgetPy::PyMake(PyTypeObject* /*type*/, PyObject* /*args*/, PyObject* /*kwds*/)
{
    return new VideoPlayerWidgetPy();
}

VideoPlayerWidgetPy::VideoPlayerWidgetPy(VideoPlayerWidget* widget)
    : m_widget(widget)
    , m_ownWidget(widget == nullptr)
{
    if (!m_widget) {
        m_widget = new VideoPlayerWidget();
    }
}

VideoPlayerWidgetPy::~VideoPlayerWidgetPy()
{
    if (m_ownWidget && m_widget) {
        delete m_widget;
    }
}

Py::Object VideoPlayerWidgetPy::repr()
{
    std::string s = "<ArchiGui.VideoPlayerWidget>";
    return Py::String(s);
}

Py::Object VideoPlayerWidgetPy::loadVideo(const Py::Tuple& args)
{
    char* path;
    if (!PyArg_ParseTuple(args.ptr(), "s", &path)) {
        throw Py::Exception();
    }
    
    if (m_widget) {
        m_widget->loadVideo(QString::fromUtf8(path));
    }
    
    return Py::None();
}

Py::Object VideoPlayerWidgetPy::play(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    
    if (m_widget) {
        m_widget->play();
    }
    
    return Py::None();
}

Py::Object VideoPlayerWidgetPy::pause(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    
    if (m_widget) {
        m_widget->pause();
    }
    
    return Py::None();
}

Py::Object VideoPlayerWidgetPy::stop(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    
    if (m_widget) {
        m_widget->stop();
    }
    
    return Py::None();
}

Py::Object VideoPlayerWidgetPy::setPosition(const Py::Tuple& args)
{
    long long position;
    if (!PyArg_ParseTuple(args.ptr(), "L", &position)) {
        throw Py::Exception();
    }
    
    if (m_widget) {
        m_widget->setPosition(position);
    }
    
    return Py::None();
}

Py::Object VideoPlayerWidgetPy::setVolume(const Py::Tuple& args)
{
    int volume;
    if (!PyArg_ParseTuple(args.ptr(), "i", &volume)) {
        throw Py::Exception();
    }
    
    if (m_widget) {
        m_widget->setVolume(volume);
    }
    
    return Py::None();
}

Py::Object VideoPlayerWidgetPy::setControlsVisible(const Py::Tuple& args)
{
    int visible;
    if (!PyArg_ParseTuple(args.ptr(), "p", &visible)) {
        throw Py::Exception();
    }

    if (m_widget) {
        m_widget->setControlsVisible(visible != 0);
    }

    return Py::None();
}

Py::Object VideoPlayerWidgetPy::controlsVisible(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }

    if (m_widget) {
        return Py::Boolean(m_widget->controlsVisible());
    }

    return Py::Boolean(false);
}

Py::Object VideoPlayerWidgetPy::setAutoLoop(const Py::Tuple& args)
{
    int loop;
    if (!PyArg_ParseTuple(args.ptr(), "p", &loop)) {
        throw Py::Exception();
    }

    if (m_widget) {
        m_widget->setAutoLoop(loop != 0);
    }

    return Py::None();
}

Py::Object VideoPlayerWidgetPy::autoLoop(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }

    if (m_widget) {
        return Py::Boolean(m_widget->autoLoop());
    }

    return Py::Boolean(false);
}

Py::Object VideoPlayerWidgetPy::position(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }

    if (m_widget) {
        return Py::Long(static_cast<long long>(m_widget->position()));
    }

    return Py::Long(0);
}

Py::Object VideoPlayerWidgetPy::getWidget(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    
    if (m_widget) {
        // Return pointer as PyLong for shiboken6.wrapInstance
        PyObject* ptr = PyLong_FromVoidPtr(static_cast<void*>(m_widget));
        return Py::asObject(ptr);
    }
    
    return Py::None();
}

// Module class
class Module : public Py::ExtensionModule<Module>
{
public:
    Module() : Py::ExtensionModule<Module>("ArchiGui")
    {
        // Register VideoPlayerWidget type
        VideoPlayerWidgetPy::init_type();
        
        // Initialize module first
        initialize("This module provides C++ widgets for ArchiGui.");
        
        // Add type to module namespace AFTER initialization
        Py::Dict d(moduleDictionary());
        d["VideoPlayerWidget"] = Py::Object(reinterpret_cast<PyObject*>(VideoPlayerWidgetPy::type_object()), true);
    }

    ~Module() override = default;
};

// Module initialization
PyObject* initModule()
{
    return Base::Interpreter().addModule(new Module);
}

} // namespace ArchiGui
