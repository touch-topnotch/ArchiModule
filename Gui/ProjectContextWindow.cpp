
#include "PreCompiled.h"
#ifndef _PreComp_
#include <QMessageBox>
#include "QVBoxLayout"
#include "QFormLayout"
#include "QGroupBox"
#include "QLabel"
#include "QLineEdit"
#include "QDoubleSpinBox"
#include "QSlider"
#include "QScrollArea"
#include "QTimer"
#include "QFileDialog"
#include "QString"
#include "QPainter"
#include "QPainterPath"
#include "QPixmap"
#include "QPushButton"
#include "QDockWidget"
#include "QApplication"
#include "QMainWindow"
#include "QMenu"
#include "QAction"
#include "QThread"

#include <qobject.h>

#endif

#include "ProjectContextWindow.h"
#include "Base/PyObjectBase.h"

#include <Inventor/nodes/SoSeparator.h>
#include <Inventor/nodes/SoCube.h>
#include <Inventor/nodes/SoTranslation.h>
#include <Inventor/Qt/viewers/SoQtExaminerViewer.h>






// ImageStyle structure
struct ImageStyle {
    int number_of_cols;
    int gap;
    QVBoxLayout* main_layout;
    QWidget* parent_class;
};


// Rounded QLabel subclass
class RoundedLabel : public QLabel {
public:
    explicit RoundedLabel(QWidget* parent = nullptr) : QLabel(parent) {}
    
protected:
    void paintEvent(QPaintEvent* event) override {
        QPainter painter(this);
        painter.setRenderHints(QPainter::Antialiasing | QPainter::SmoothPixmapTransform);

        QPainterPath path;
        path.addRoundedRect(rect(), 10, 10);
        painter.setClipPath(path);

        // Explicitly request the pixmap by-value using Qt::ReturnByValue
        QPixmap pm = pixmap(Qt::ReturnByValue);
        painter.drawPixmap(0, 0, pm);
    }
};

// ImageData class
class ImageData : public QWidget {
    Q_OBJECT
public:
    ImageData
        (
        const QString& labelText,
        const QString& buttonText,
        ImageStyle style,
        int height = 200,
        QWidget* parent = nullptr
        )
        : QWidget(parent) {

        QLabel* header = new QLabel(labelText);
        header->setStyleSheet(QLatin1String("font-size: 14pt; font-weight: bold;"));
        style.main_layout->addWidget(header);

        QScrollArea* scrollArea = new QScrollArea;
        QWidget* content = new QWidget;
        QHBoxLayout* hLayout = new QHBoxLayout(content);
        hLayout->setAlignment(Qt::AlignTop | Qt::AlignLeft);
        hLayout->setContentsMargins(0, 0, 0, 0);
        hLayout->setSpacing(style.gap);

        for (int i = 0; i < style.number_of_cols; ++i) {
            QVBoxLayout* vLayout = new QVBoxLayout;
            vLayout->setAlignment(Qt::AlignTop);
            vLayout->setSpacing(style.gap);
            m_layouts.append(vLayout);
            hLayout->addLayout(vLayout);
        }

        scrollArea->setWidget(content);
        scrollArea->setWidgetResizable(true);
        scrollArea->setMaximumHeight(height);
        style.main_layout->addWidget(scrollArea);

        QPushButton* addButton = new QPushButton(buttonText);
        connect(addButton, &QPushButton::clicked, this, &ImageData::selectAndAddImages);
        style.main_layout->addWidget(addButton);
    }

private slots:
    void selectAndAddImages() {

        QStringList files = QFileDialog::getOpenFileNames(m_style.parent_class, QLatin1String("Select Images"), QLatin1String(""),
                                                          QLatin1String("Images (*.png *.jpg *.jpeg *.bmp *.gif)"));

        for (const QString& file : files) {
            QPixmap pixmap(file);
            if (pixmap.isNull()) continue;

            pixmap = pixmap.scaledToWidth(200, Qt::SmoothTransformation);

            RoundedLabel* label = new RoundedLabel;
            label->setPixmap(pixmap);
            label->setToolTip(file);

            int col = std::distance(m_heights.begin(), std::min_element(m_heights.begin(), m_heights.end()));
            m_layouts[col]->insertWidget(0, label);
            m_heights[col] += pixmap.height() + m_style.gap;
        }
    }

private:
    ImageStyle m_style{};
    QList<QVBoxLayout*> m_layouts;
    QList<int> m_heights;
};

// MiniView3D class
class MiniView3D : public QWidget {
    Q_OBJECT
public:
    explicit MiniView3D(QWidget* parent = nullptr) : QWidget(parent) {
        setMinimumSize(200, 200);
        setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);

        QTimer::singleShot(100, this, &MiniView3D::initScene);
    }

private slots:
    void initScene() {
        SoSeparator* root = new SoSeparator;
        SoTranslation* trans = new SoTranslation;
        trans->translation.setValue(0, 0, 0);
        root->addChild(trans);
        root->addChild(new SoCube);

        m_viewer = new SoQtExaminerViewer(this);
        m_viewer->setSceneGraph(root);
        m_viewer->show();
    }

private:
    SoQtExaminerViewer* m_viewer = nullptr;
};
// ProjectContextWindow class


ProjectContextWindow* ProjectContextWindow::s_instance = nullptr;

ProjectContextWindow* ProjectContextWindow::instance(QWidget* parent) {
    if (!s_instance) {
        s_instance = new ProjectContextWindow(parent);
    }
    return s_instance;
}

void ProjectContextWindow::destroyInstance() {
    delete s_instance;
    s_instance = nullptr;
}

ProjectContextWindow ::ProjectContextWindow(QWidget* parent)
    : QDockWidget(QLatin1String("Project Context"), parent)
{
    QWidget* mainWidget = new QWidget;
    QVBoxLayout* mainLayout = new QVBoxLayout(mainWidget);
    
    QLabel* title = new QLabel(QLatin1String("Project Context"));

    title->setStyleSheet(QLatin1String("font-size: 18pt; font-weight: bold;"));
    mainLayout->addWidget(title);

        ImageStyle style{3, 10, mainLayout, this};

        ImageData* sketches = new ImageData(QLatin1String("Sketches"), QLatin1String("Add Sketches"), style);
        ImageData* environment = new ImageData(QLatin1String("AI Generations"), QLatin1String("Generate More"), style);

        // Parameters section
        QLabel* paramsHeader = new QLabel(QLatin1String("Parameters"));
        paramsHeader->setStyleSheet(QLatin1String("font-size: 14pt; font-weight: bold;"));
        mainLayout->addWidget(paramsHeader);

        QGroupBox* paramsGroup = new QGroupBox;
        QFormLayout* form = new QFormLayout(paramsGroup);

        form->addRow(QLatin1String("Height (m):"), new QDoubleSpinBox);
        form->addRow(QLatin1String("Realism:"), new QSlider(Qt::Horizontal));
        form->addRow(QLatin1String("Other:"), new QLineEdit);

        mainLayout->addWidget(paramsGroup);

        // Visualization
        QLabel* vizHeader = new QLabel(QLatin1String("Visualization"));
        vizHeader->setStyleSheet(QLatin1String("font-size: 14pt; font-weight: bold;"));
        mainLayout->addWidget(vizHeader);

        //MiniView3D* miniView = new MiniView3D;
        //mainLayout->addWidget(miniView);

    setWidget(mainWidget);
}

ProjectContextWindow::~ProjectContextWindow() {
    s_instance = nullptr;
}




// Initialization function
//void setupProjectContext() {
//    QMainWindow* mw = FreeCADGui::getMainWindow();
//    ProjectContextWindow* dock = new ProjectContextWindow(mw);
//    mw->addDockWidget(Qt::RightDockWidgetArea, dock);
//}
#include "ProjectContextWindow.moc"