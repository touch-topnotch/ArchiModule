#ifndef PROJECTCONTEXTWINDOW_H
#define PROJECTCONTEXTWINDOW_H

#include <QDockWidget>

class ProjectContextWindow : public QDockWidget {
    Q_OBJECT

public:
    static ProjectContextWindow* instance(QWidget* parent = nullptr);
    static void destroyInstance();

private:
    explicit ProjectContextWindow(QWidget* parent = nullptr);
    ~ProjectContextWindow();

    static ProjectContextWindow* s_instance;
};

#endif  // PROJECTCONTEXTWINDOW_H
