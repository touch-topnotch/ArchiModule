/***************************************************************************
*   Copyright (c) 2008 Jürgen Riegel <juergen.riegel@web.de>              *
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
#ifndef _PreComp_
#include <QMessageBox>
#endif

#include <Gui/Application.h>
#include <Gui/Command.h>
#include <Gui/Control.h>
#include <Gui/Document.h>
#include <Gui/MainWindow.h>
#include <Python.h>



using namespace std;
//
//DEF_STD_CMD_A(CmdAuthentication)
//
//CmdAuthentication::CmdAuthentication()
//    : Command("Archi_Authentication")
//{
//    sAppModule = "Archi";
//    sGroup = QT_TR_NOOP("Archi");
//    sMenuText = QT_TR_NOOP("Add Project Context...");
//    sToolTipText = QT_TR_NOOP("Add Project Context (experimental!)");
//    sWhatsThis = "Archi_Authentication";
//    sStatusTip = sToolTipText;
//    sPixmap = "Archi_Authentication";
//}
//void CmdAuthentication::activated(int)
//{
//    Gui::Document* pcDoc = Gui::Application::Instance->activeDocument();
//    if (pcDoc) {
//        // print to console
//        Base::Console().Message("Auth Window activated\n");
//        // create project context window
//        auto* AuthenticationWindow = AuthenticationWindow::instance(Gui::getMainWindow());
//        //adjust the window to the right side of screen
//        AuthenticationWindow->move(Gui::getMainWindow()->pos().x() + Gui::getMainWindow()->width(), Gui::getMainWindow()->pos().y());
//        AuthenticationWindow->show();
//
//    }
//}
//bool CmdAuthentication::isActive()
//{
//    return (hasActiveDocument() && !Gui::Control().activeDialog());
//}
//
//DEF_STD_CMD_A(CmdProjectContext)
//
//CmdProjectContext::CmdProjectContext()
//    : Command("Archi_ProjectContext")
//{
//    sAppModule = "Archi";
//    sGroup = QT_TR_NOOP("Archi");
//    sMenuText = QT_TR_NOOP("Add Project Context...");
//    sToolTipText = QT_TR_NOOP("Add Project Context (experimental!)");
//    sWhatsThis = "Archi_ProjectContext";
//    sStatusTip = sToolTipText;
//    sPixmap = "Archi_ProjectContext";
//}
//void CmdProjectContext::activated(int)
//{
//    Gui::Document* pcDoc = Gui::Application::Instance->activeDocument();
//    if (pcDoc) {
//        // print to console
//        Base::Console().Message("Project Context activated\n");
//        // create project context window using "ProjectContext.py" and function ArchiContextWindow(QDockWidget):
//        PyObject* pName = PyUnicode_DecodeFSDefault("ProjectContext");
//        Base::Console().Message("PyObject* pName = PyUnicode_DecodeFSDefault(\"ProjectContext\");\n");
//        PyObject* pModule = PyImport_Import(pName);
//        Base::Console().Message("PyObject* pModule = PyImport_Import(pName);");
//        Py_DECREF(pName);
//        Base::Console().Message("Py_DECREF(pName);");
//
//        if (pModule != nullptr) {
//            PyObject* pFunc = PyObject_GetAttrString(pModule, "ArchiContextWindow");
//            if (PyCallable_Check(pFunc)) {
//                PyObject* pArgs = PyTuple_Pack(1, Py_None);
//                PyObject* pValue = PyObject_CallObject(pFunc, pArgs);
//                Py_DECREF(pArgs);
//                if (pValue != nullptr) {
//                    // Successfully created the window
//                    Base::Console().Message("Project Context window created\n");
//                    Py_DECREF(pValue);
//                } else {
//                    Py_DECREF(pFunc);
//                    Py_DECREF(pModule);
//                    PyErr_Print();
//                    Base::Console().Error("Failed to create Project Context window\n");
//                    return;
//                }
//            } else {
//                if (PyErr_Occurred())
//                    PyErr_Print();
//                Base::Console().Error("Cannot find function 'ArchiContextWindow'\n");
//            }
//            Py_XDECREF(pFunc);
//            Py_DECREF(pModule);
//        } else {
//            PyErr_Print();
//            Base::Console().Error("Failed to load 'ProjectContext' module\n");
//            return;
//        }
//    }
//}
//bool CmdProjectContext::isActive()
//{
//    return (hasActiveDocument() && !Gui::Control().activeDialog());
//}
//
//DEF_STD_CMD_A(CmdFloorPlaner)
//
//CmdFloorPlaner::CmdFloorPlaner()
//    : Command("Archi_FloorPlaner")
//{
//    sAppModule = "Archi";
//    sGroup = QT_TR_NOOP("Archi");
//    sMenuText = QT_TR_NOOP("Create Floor Planer...");
//    sToolTipText = QT_TR_NOOP("Create Floor Planer (experimental!)");
//    sWhatsThis = "Archi_FloorPlaner";
//    sStatusTip = sToolTipText;
//    sPixmap = "Archi_FloorPlaner";
//}
//void CmdFloorPlaner::activated(int)
//{
//    Gui::Document* pcDoc = Gui::Application::Instance->activeDocument();
//    if (pcDoc) {
//        // print to console
//        Base::Console().Message("Floor Planer activated\n");
//    }
//}
//bool CmdFloorPlaner::isActive()
//{
//    return (hasActiveDocument() && !Gui::Control().activeDialog());
//}
//
//DEF_STD_CMD_A(CmdArchiSimulate)
//
//void CmdArchiSimulate::activated(int)
//{
//    Gui::Document* pcDoc = Gui::Application::Instance->activeDocument();
//    if (pcDoc) {
//        //pcDoc->openTransaction("Simulate Archi");
//        //pcDoc->commitTransaction();
//    }
//}
//
//bool CmdArchiSimulate::isActive()
//{
//    return (hasActiveDocument() && !Gui::Control().activeDialog());
//}

void CreateArchiCommands()
{
    Gui::CommandManager &rcCmdMgr = Gui::Application::Instance->commandManager();
    //rcCmdMgr.addCommand(new CmdArchiSimulate());
//    rcCmdMgr.addCommand(new CmdProjectContext());
//    rcCmdMgr.addCommand(new CmdFloorPlaner());

}
