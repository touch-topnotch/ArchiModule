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
#include "ProjectContextWindow.h"


using namespace std;

DEF_STD_CMD_A(CmdProjectContext)

CmdProjectContext::CmdProjectContext()
    : Command("Archi_ProjectContext")
{
    sAppModule = "Archi";
    sGroup = QT_TR_NOOP("Archi");
    sMenuText = QT_TR_NOOP("Add Project Context...");
    sToolTipText = QT_TR_NOOP("Add Project Context (experimental!)");
    sWhatsThis = "Archi_ProjectContext";
    sStatusTip = sToolTipText;
    sPixmap = "Archi_ProjectContext";
}
void CmdProjectContext::activated(int)
{
    Gui::Document* pcDoc = Gui::Application::Instance->activeDocument();
    if (pcDoc) {
        // print to console
        Base::Console().Message("Project Context activated\n");
        // create project context window
        auto* projectContextWindow = ProjectContextWindow::instance(Gui::getMainWindow());
        //adjust the window to the right side of screen
        projectContextWindow->move(Gui::getMainWindow()->pos().x() + Gui::getMainWindow()->width(), Gui::getMainWindow()->pos().y());
        projectContextWindow->show();

    }
}
bool CmdProjectContext::isActive()
{
    return (hasActiveDocument() && !Gui::Control().activeDialog());
}

DEF_STD_CMD_A(CmdFloorPlaner)

CmdFloorPlaner::CmdFloorPlaner()
    : Command("Archi_FloorPlaner")
{
    sAppModule = "Archi";
    sGroup = QT_TR_NOOP("Archi");
    sMenuText = QT_TR_NOOP("Create Floor Planer...");
    sToolTipText = QT_TR_NOOP("Create Floor Planer (experimental!)");
    sWhatsThis = "Archi_FloorPlaner";
    sStatusTip = sToolTipText;
    sPixmap = "Archi_FloorPlaner";
}
void CmdFloorPlaner::activated(int)
{
    Gui::Document* pcDoc = Gui::Application::Instance->activeDocument();
    if (pcDoc) {
        // print to console
        Base::Console().Message("Floor Planer activated\n");
    }
}
bool CmdFloorPlaner::isActive()
{
    return (hasActiveDocument() && !Gui::Control().activeDialog());
}

DEF_STD_CMD_A(CmdArchiSimulate)

void CmdArchiSimulate::activated(int)
{
    Gui::Document* pcDoc = Gui::Application::Instance->activeDocument();
    if (pcDoc) {
        //pcDoc->openTransaction("Simulate Archi");
        //pcDoc->commitTransaction();
    }
}

bool CmdArchiSimulate::isActive()
{
    return (hasActiveDocument() && !Gui::Control().activeDialog());
}

void CreateArchiCommands()
{
    Gui::CommandManager &rcCmdMgr = Gui::Application::Instance->commandManager();
    //rcCmdMgr.addCommand(new CmdArchiSimulate());
    rcCmdMgr.addCommand(new CmdProjectContext());
    rcCmdMgr.addCommand(new CmdFloorPlaner());

}
