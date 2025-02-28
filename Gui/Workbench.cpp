/***************************************************************************
*   Copyright (c) 2008 Werner Mayer <werner.wm.mayer@gmx.de>              *
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
#include <QDir>
#include <QFileInfo>
#include <QMessageBox>
#include <qobject.h>
#endif

#include <App/Application.h>
#include <Gui/Control.h>
#include <Gui/MainWindow.h>
#include <Gui/MenuManager.h>
#include <Gui/TaskView/TaskView.h>
#include <Gui/TaskView/TaskWatcher.h>
#include <Gui/ToolBarManager.h>
#include <Gui/WaitCursor.h>

#include "Workbench.h"


using namespace ArchiGui;

#if 0  // needed for Qt's lupdate utility
   qApp->translate("Workbench", "Archi");
   qApp->translate("Workbench", "Insert Archis");
   qApp->translate("Workbench", "&Archi");
   qApp->translate("Workbench", "Export trajectory");
   qApp->translate("Gui::TaskView::TaskWatcherCommands", "Trajectory tools");
   qApp->translate("Gui::TaskView::TaskWatcherCommands", "Archi tools");
   qApp->translate("Gui::TaskView::TaskWatcherCommands", "Insert Archi");
#endif

/// @namespace ArchiGui @class Workbench
TYPESYSTEM_SOURCE(ArchiGui::Workbench, Gui::StdWorkbench)

Workbench::Workbench() = default;

Workbench::~Workbench() = default;

void Workbench::activated()
{
   std::string res = App::Application::getResourceDir();

   Gui::Workbench::activated();
//
//
//   std::vector<Gui::TaskView::TaskWatcher*> Watcher;
//
//
//   Gui::Control().showTaskView();
}


void Workbench::deactivated()
{
   Gui::Workbench::deactivated();
}


Gui::ToolBarItem* Workbench::setupToolBars() const
{
   Gui::ToolBarItem* root = StdWorkbench::setupToolBars();
   Gui::ToolBarItem* part = new Gui::ToolBarItem(root);
   part->setCommand("Archi");
   *part    << "Archi_ProjectContext"
            << "Archi_FloorPlaner";
   return root;
}

Gui::MenuItem* Workbench::setupMenuBar() const
{
   Gui::MenuItem* root = StdWorkbench::setupMenuBar();
   Gui::MenuItem* item = root->findItem("&Windows");
   Gui::MenuItem* Archi = new Gui::MenuItem;
   root->insertItem(item, Archi);

   // analyze
   Gui::MenuItem* AiTools = new Gui::MenuItem;
   AiTools->setCommand("AI Tools");
   *AiTools << "Archi_ProjectContext"
            << "Archi_FloorPlaner"
            << "Archi_Authentication";
   return root;
}
